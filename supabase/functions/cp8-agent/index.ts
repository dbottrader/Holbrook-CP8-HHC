import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "npm:@supabase/supabase-js@2";

const jsonHeaders = {
  "Content-Type": "application/json",
  "Cache-Control": "no-store",
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, content-type",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
};

function response(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: jsonHeaders });
}

function tokenFrom(req: Request): string | null {
  const value = req.headers.get("Authorization") ?? "";
  if (!value.startsWith("Bearer hc_")) return null;
  const token = value.slice(7);
  return /^hc_[0-9a-f]{64}$/.test(token) ? token : null;
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: jsonHeaders });

  const requestUrl = new URL(req.url);
  if (req.method === "GET" && requestUrl.searchParams.get("health") === "1") {
    return response({
      schema: "cp8-agent-commons-v1",
      status: "ready",
      authority: "capability_token_required_for_agent_io",
      promotion: "human_jwt_required",
      operations: ["poll", "post"],
      limits: { max_poll: 200, max_event_payload_bytes: 32768 },
    });
  }

  const token = tokenFrom(req);
  if (!token) return response({ error: "capability_token_required" }, 401);

  const url = Deno.env.get("SUPABASE_URL");
  const key = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!url || !key) return response({ error: "server_configuration_error" }, 500);

  const supabase = createClient(url, key, {
    auth: { persistSession: false, autoRefreshToken: false },
  });

  if (req.method === "GET") {
    const runId = requestUrl.searchParams.get("run_id");
    if (!runId) return response({ error: "run_id_required" }, 400);
    const after = requestUrl.searchParams.get("after") ?? "1970-01-01T00:00:00Z";
    const limit = Number(requestUrl.searchParams.get("limit") ?? "100");
    const { data, error } = await supabase.rpc("cp8_agent_poll_events", {
      p_token: token,
      p_run_id: runId,
      p_after: after,
      p_limit: limit,
    });
    if (error) return response({ error: "poll_rejected", detail: error.message }, 403);
    return response({ schema: "cp8-agent-poll-v1", events: data ?? [] });
  }

  if (req.method === "POST") {
    let input: Record<string, unknown>;
    try {
      input = await req.json();
    } catch {
      return response({ error: "invalid_json" }, 400);
    }
    const { data, error } = await supabase.rpc("cp8_agent_post_event", {
      p_token: token,
      p_run_id: input.run_id,
      p_event_type: input.event_type,
      p_stage: input.stage,
      p_visibility: input.visibility ?? "BRANCH",
      p_nonce: input.nonce,
      p_payload: input.payload ?? {},
      p_parent_hash: input.parent_hash ?? null,
    });
    if (error) return response({ error: "post_rejected", detail: error.message }, 403);
    return response({ schema: "cp8-agent-post-v1", receipt: data?.[0] ?? null }, 201);
  }

  return response({ error: "method_not_allowed" }, 405);
});
