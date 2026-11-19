import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "npm:@supabase/supabase-js@2";

const jsonHeaders = {
  "Content-Type": "application/json",
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

function response(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: jsonHeaders });
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: jsonHeaders });
  if (req.method !== "POST") return response({ error: "method_not_allowed" }, 405);

  const authorization = req.headers.get("Authorization");
  if (!authorization) return response({ error: "authentication_required" }, 401);

  const url = Deno.env.get("SUPABASE_URL");
  const key = Deno.env.get("SUPABASE_ANON_KEY");
  if (!url || !key) return response({ error: "server_configuration_error" }, 500);

  const supabase = createClient(url, key, {
    global: { headers: { Authorization: authorization } },
    auth: { persistSession: false, autoRefreshToken: false },
  });

  let input: Record<string, unknown>;
  try {
    input = await req.json();
  } catch {
    return response({ error: "invalid_json" }, 400);
  }

  const action = String(input.action ?? "");
  let rpc: string;
  let params: Record<string, unknown>;

  switch (action) {
    case "register_agent":
      rpc = "cp8_register_agent";
      params = {
        p_handle: input.handle,
        p_display_name: input.display_name,
        p_public_signing_key: input.public_signing_key ?? null,
        p_token_ttl: input.token_ttl ?? "30 days",
      };
      break;
    case "create_run":
      rpc = "cp8_create_run";
      params = {
        p_anchor: input.anchor,
        p_event_budget: input.event_budget ?? 100,
        p_branch_budget: input.branch_budget ?? 8,
        p_wall_clock_budget_seconds: input.wall_clock_budget_seconds ?? 3600,
        p_ttl: input.ttl ?? "1 day",
      };
      break;
    case "add_agent":
      rpc = "cp8_add_agent_to_run";
      params = {
        p_run_id: input.run_id,
        p_agent_id: input.agent_id,
        p_branch_id: input.branch_id,
        p_capabilities: input.capabilities ?? ["POLL", "POST_BRANCH"],
      };
      break;
    case "mark_synthesized":
      rpc = "cp8_mark_synthesized";
      params = { p_run_id: input.run_id, p_synthesis_hash: input.synthesis_hash };
      break;
    case "decide":
      rpc = "cp8_human_decide";
      params = { p_run_id: input.run_id, p_verdict: input.verdict, p_reason: input.reason };
      break;
    case "revoke_agent":
      rpc = "cp8_revoke_agent_tokens";
      params = { p_agent_id: input.agent_id };
      break;
    default:
      return response({ error: "unsupported_action" }, 400);
  }

  const { data, error } = await supabase.rpc(rpc, params);
  if (error) return response({ error: "request_rejected", detail: error.message }, 400);
  return response({ schema: "cp8-control-v1", action, data });
});
