import {
  GENESIS_PREV,
  GROQ_TEST_EXPECTED,
  GROQ_TEST_MAX_TOKENS,
  GROQ_TEST_MODEL,
  GROQ_TEST_PROMPT,
  PUBLISHED_PUBLIC_KEY,
  buildSignedReceipt,
  canonAnswer,
  publicKeyHexFromPrivate,
  sha256Hex,
} from "./receipt.mjs";

// Same edge secret the live cp8-groq-inference function reads.
const GROQ_API_KEY_NAME = "GROQ_API_KEY";
const FINGERPRINT_LIMIT = 4;
const GLOBAL_LIMIT = 30;
const WINDOW_SECONDS = 3600;
const ACTOR = "groq-fallback";
const KIND = "groq_inference_receipt";

function envGet(env, name) {
  if (!env) return "";
  if (typeof env.get === "function") return env.get(name) || "";
  return env[name] || "";
}

function segments(url) {
  const parts = new URL(url).pathname.split("/").filter(Boolean);
  const marker = parts.indexOf("groq-test");
  return marker >= 0 ? parts.slice(marker + 1) : parts;
}

async function fingerprint(req) {
  const ip = req.headers.get("cf-connecting-ip")
    || req.headers.get("x-forwarded-for")?.split(",")[0]?.trim()
    || "unknown";
  const ua = req.headers.get("user-agent") || "unknown";
  return sha256Hex(`${ip}|${ua}`);
}

function result(status, body, extraHeaders) {
  return { status, body, headers: extraHeaders || {} };
}

export function receiptView(row) {
  const typed = row.typed_json || row.typed_data || null;
  return {
    receipt_id: row.receipt_id,
    seq: row.seq,
    ts: row.ts,
    actor: row.actor,
    kind: row.kind,
    payload: row.payload,
    prev_hash: row.prev_hash,
    hash: row.hash,
    canon: row.canon || "v1",
    body_json: row.body_json,
    signature: row.signature,
    signer: row.signer,
    typed_data: typed,
    amount: row.amount,
    verification: row.verification,
    output_text: row.output_text,
    output_sha256: row.output_sha256,
    request_id: row.request_id || "",
    state: "OBSERVED",
    promotion: "HOLD",
    ledger_backend: "simulated",
    settlement_note: "The default ledger is simulated. It settles to the Base work token once the on-chain backend is enabled.",
  };
}

async function signingMaterial(env, published) {
  const secret = envGet(env, "INFERENCE_RECEIPT_SIGNING_KEY").trim();
  if (!secret) {
    return {
      error: result(503, {
        ok: false,
        error: "signing_key_not_configured",
        message: "INFERENCE_RECEIPT_SIGNING_KEY is not set on this Supabase function. Dennis needs to set that secret before receipts can be signed.",
      }),
    };
  }
  let derived = "";
  try {
    derived = await publicKeyHexFromPrivate(secret);
  } catch {
    return {
      error: result(503, {
        ok: false,
        error: "signing_key_invalid",
        message: "INFERENCE_RECEIPT_SIGNING_KEY is not a 32-byte Ed25519 seed.",
      }),
    };
  }
  if (derived !== published) {
    return {
      error: result(503, {
        ok: false,
        error: "signing_key_not_published",
        message: "The signing secret does not match the published public key. Refusing to sign.",
      }),
    };
  }
  return { secret };
}

export async function handleGroqTest(req, deps) {
  const published = deps.publishedPublicKey || PUBLISHED_PUBLIC_KEY;
  const parts = segments(req.url);
  if (req.method === "GET" && (parts.length === 0 || parts[0] === "health")) {
    return result(200, {
      ok: true,
      service: "groq-test",
      promotion: "HOLD",
      model: GROQ_TEST_MODEL,
      prompt: GROQ_TEST_PROMPT,
      max_tokens: GROQ_TEST_MAX_TOKENS,
      groq_configured: Boolean(envGet(deps.env, GROQ_API_KEY_NAME)),
      groq_secret_name: GROQ_API_KEY_NAME,
      signer_configured: Boolean(envGet(deps.env, "INFERENCE_RECEIPT_SIGNING_KEY")),
      public_key_hex: published,
      ledger_backend: "simulated",
      settlement_note: "The default ledger is simulated. It settles to the Base work token once the on-chain backend is enabled.",
    });
  }
  if (req.method === "GET" && parts[0] === "pubkey") {
    return result(200, {
      scheme: "ed25519",
      public_key_hex: published,
      canon: "v1",
      domain: "GPU-MESH",
    });
  }
  if (req.method === "GET" && parts[0] === "receipts" && parts[1]) {
    const row = await deps.db.get(parts[1]);
    if (!row) return result(404, { ok: false, error: "receipt_not_found" });
    return result(200, { ok: true, receipt: receiptView(row) });
  }
  if (req.method !== "POST" || parts.length > 0) {
    return result(405, { ok: false, error: "method_not_allowed" });
  }

  const apiKey = envGet(deps.env, GROQ_API_KEY_NAME).trim();
  if (!apiKey) {
    return result(503, {
      ok: false,
      error: "groq_api_key_not_configured",
      state: "HOLD",
      promotion: "HOLD",
      message: "GROQ_API_KEY is not set for this function. cp8-groq-inference reads that same secret name.",
    });
  }
  const signing = await signingMaterial(deps.env, published);
  if (signing.error) return signing.error;

  const fp = await fingerprint(req);
  const personal = await deps.db.rateAllow(`fp:${fp}`, FINGERPRINT_LIMIT, WINDOW_SECONDS);
  const globalOk = personal
    ? await deps.db.rateAllow("global", GLOBAL_LIMIT, WINDOW_SECONDS)
    : false;
  if (!personal || !globalOk) {
    return result(429, {
      ok: false,
      error: "rate_limited",
      message: "This public test allows 4 calls per hour for a client and 30 per hour overall.",
    }, { "retry-after": "3600" });
  }

  const started = Date.now();
  const fetchImpl = deps.fetchImpl || fetch;
  let upstream;
  try {
    upstream = await fetchImpl("https://api.groq.com/openai/v1/chat/completions", {
      method: "POST",
      headers: {
        authorization: `Bearer ${apiKey}`,
        "content-type": "application/json",
      },
      body: JSON.stringify({
        model: GROQ_TEST_MODEL,
        messages: [{ role: "user", content: GROQ_TEST_PROMPT }],
        max_completion_tokens: GROQ_TEST_MAX_TOKENS,
        temperature: 0,
      }),
    });
  } catch {
    return result(502, { ok: false, error: "provider_unreachable", message: "Groq did not respond." });
  }
  const data = await upstream.json().catch(() => ({}));
  if (!upstream.ok) {
    return result(502, {
      ok: false,
      error: "provider_request_failed",
      provider_status: upstream.status,
      message: "Groq refused the bounded test request.",
    });
  }
  const output = data?.choices?.[0]?.message?.content;
  if (typeof output !== "string" || !output.trim()) {
    return result(502, { ok: false, error: "provider_response_missing_text" });
  }
  const clipped = output.slice(0, 4000);
  const verified = canonAnswer(clipped) === canonAnswer(GROQ_TEST_EXPECTED);
  const requestId = String(data.id || upstream.headers?.get?.("x-request-id") || "");
  const usage = data.usage && typeof data.usage === "object" ? data.usage : {};
  const promptTokens = Number.isFinite(Number(usage.prompt_tokens)) ? Math.trunc(Number(usage.prompt_tokens)) : 0;
  const completionTokens = Number.isFinite(Number(usage.completion_tokens))
    ? Math.trunc(Number(usage.completion_tokens))
    : 0;
  const outputSha = await sha256Hex(clipped);
  const verification = {
    ok: verified,
    method: "exact_match",
    expected: GROQ_TEST_EXPECTED,
    verifier_ids: "exact-match",
  };
  const payload = {
    amount: 0,
    completion_tokens: completionTokens,
    credits: 0,
    duration_ms: Date.now() - started,
    max_tokens: GROQ_TEST_MAX_TOKENS,
    model: GROQ_TEST_MODEL,
    output_hash: outputSha,
    promotion: "HOLD",
    prompt_sha256: await sha256Hex(GROQ_TEST_PROMPT),
    prompt_tokens: promptTokens,
    provider: "groq",
    request_id: requestId,
    runtime: "groq",
    schema: "gpumesh.groq_fallback.v1",
    settlement_id: requestId ? `groq:${requestId}` : `groq:${outputSha}`,
    state: "OBSERVED",
    temperature: 0,
    verification_method: "exact_match",
    verifier_decision: verified ? "agree" : "fail",
    verifier_ids: "exact-match",
    worker_id: `groq:${GROQ_TEST_MODEL}`,
  };

  let receiptId = "";
  let signed = null;
  let lastError = "";
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const head = await deps.db.head();
    const seq = head && Number.isFinite(Number(head.seq)) ? Number(head.seq) + 1 : 1;
    const prev = head && head.hash ? head.hash : GENESIS_PREV;
    signed = await buildSignedReceipt({
      privateKeyHex: signing.secret,
      actor: ACTOR,
      kind: KIND,
      payload,
      prevHash: prev,
      seq,
      ts: Date.now(),
    });
    try {
      receiptId = await deps.db.append({
        ...signed,
        verification,
        output_text: clipped,
        output_sha256: outputSha,
        request_id: requestId,
      });
      break;
    } catch (error) {
      lastError = String(error && error.message ? error.message : error);
      if (!lastError.includes("receipt_chain_fork")) throw error;
    }
  }
  if (!receiptId) {
    return result(503, { ok: false, error: "ledger_append_failed", message: lastError || "receipt chain fork" });
  }
  const stored = await deps.db.get(String(receiptId));
  const view = stored ? receiptView(stored) : receiptView({
    ...signed,
    receipt_id: String(receiptId),
    verification,
    output_text: clipped,
    output_sha256: outputSha,
    request_id: requestId,
  });
  return result(200, {
    ok: true,
    state: "OBSERVED",
    promotion: "HOLD",
    model: data.model || GROQ_TEST_MODEL,
    output: clipped,
    output_sha256: outputSha,
    request_id: requestId,
    usage: {
      prompt_tokens: promptTokens,
      completion_tokens: completionTokens,
      total_tokens: promptTokens + completionTokens,
    },
    verification,
    ledger_receipt_id: String(receiptId),
    receipt: view,
    public_key_hex: published,
  });
}
