
const currentKeys = [
  "bitcoin_status","chain","checkpoint_created_at","checkpoint_id","claim_boundary",
  "external_receipt_status","nonclaims","ots_status","previous_checkpoint_hash",
  "previous_tip_matches","promotion_state","protocol","snapshot_hash","submission_status",
  "tip","tip_format_valid","tip_kind","verification_status"
].sort();

const lookupKeys = [
  "bitcoin_status","chain","checkpoint_created_at","checkpoint_id","claim_boundary",
  "external_receipt_status","lookup_status","match_count","nonclaims","ots_status",
  "predecessor_exists","previous_checkpoint_hash","promotion_state","protocol",
  "snapshot_hash","state_hash","submission_status","tip","tip_kind","topology_valid",
  "verification_status"
].sort();

function jsonResponse(body: unknown, status = 200, head = false): Response {
  const encoded = JSON.stringify(body);
  return new Response(head ? null : encoded, {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store, max-age=0",
      "x-content-type-options": "nosniff",
      "content-length": head ? "0" : String(new TextEncoder().encode(encoded).length)
    }
  });
}

function exactKeys(value: Record<string, unknown>, expected: string[]): boolean {
  const actual = Object.keys(value).sort();
  return actual.length === expected.length && actual.every((key, i) => key === expected[i]);
}

Deno.serve(async (req: Request) => {
  const head = req.method === "HEAD";
  if (req.method !== "GET" && !head) {
    return jsonResponse({ error: "METHOD_NOT_ALLOWED" }, 405, head);
  }

  const requestedTip = new URL(req.url).searchParams.get("tip");
  if (requestedTip !== null && !/^[0-9a-f]{64}$/.test(requestedTip)) {
    return jsonResponse({ error: "INVALID_TIP" }, 400, head);
  }

  const supabaseUrl = Deno.env.get("SUPABASE_URL");
  const anonKey = Deno.env.get("SUPABASE_ANON_KEY");
  if (!supabaseUrl || !anonKey) {
    return jsonResponse({ error: "UPSTREAM_CONFIGURATION_UNAVAILABLE" }, 503, head);
  }

  const rpc = requestedTip
    ? "cp8_moltbook_external_witness_tip_lookup_v1"
    : "cp8_moltbook_external_witness_tip_v1";
  const body = requestedTip ? JSON.stringify({ p_tip: requestedTip }) : "{}";

  try {
    const upstream = await fetch(supabaseUrl + "/rest/v1/rpc/" + rpc, {
      method: "POST",
      headers: {
        "apikey": anonKey,
        "authorization": "Bearer " + anonKey,
        "content-type": "application/json"
      },
      body,
      signal: AbortSignal.timeout(8000)
    });

    if (!upstream.ok) {
      return jsonResponse({ error: "UPSTREAM_UNAVAILABLE", status: upstream.status }, 502, head);
    }

    const envelope = await upstream.json() as Record<string, unknown>;
    const commonValid =
      envelope.verification_status === "PASS" &&
      envelope.promotion_state === "HOLD" &&
      envelope.submission_status === "NOT_SUBMITTED" &&
      envelope.external_receipt_status === "NONE" &&
      envelope.ots_status === "NOT_SUBMITTED" &&
      envelope.bitcoin_status === "NOT_ANCHORED" &&
      typeof envelope.tip === "string" &&
      /^[0-9a-f]{64}$/.test(envelope.tip as string);

    const valid = requestedTip
      ? exactKeys(envelope, lookupKeys) &&
        commonValid &&
        envelope.protocol === "CP8-PUBLIC-EXTERNAL-WITNESS-TIP-LOOKUP-v1" &&
        envelope.lookup_status === "FOUND" &&
        envelope.match_count === 1 &&
        envelope.topology_valid === true &&
        envelope.tip === requestedTip
      : exactKeys(envelope, currentKeys) &&
        commonValid &&
        envelope.protocol === "CP8-PUBLIC-EXTERNAL-WITNESS-TIP-v1" &&
        envelope.tip_format_valid === true;

    if (!valid) {
      return jsonResponse({ error: "UPSTREAM_CONTRACT_VIOLATION" }, 502, head);
    }

    return jsonResponse(envelope, 200, head);
  } catch {
    return jsonResponse({ error: "UPSTREAM_FETCH_FAILED" }, 502, head);
  }
});
