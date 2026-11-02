// Bounded public Groq test. verify_jwt stays false: the route is public,
// rate-limited, and ignores the caller prompt. GROQ_API_KEY and
// INFERENCE_RECEIPT_SIGNING_KEY are function secrets. They are not in git.
import { createClient } from "npm:@supabase/supabase-js@2";
import { handleGroqTest } from "./handler.mjs";

const db = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!, {
  auth: { persistSession: false, autoRefreshToken: false },
});

const adapter = {
  async rateAllow(bucket: string, limit: number, windowSeconds: number) {
    const { data, error } = await db.rpc("cp8_inference_rate_allow", {
      p_bucket: bucket,
      p_limit: limit,
      p_window_seconds: windowSeconds,
    });
    if (error) throw new Error(error.message);
    return Boolean(data);
  },
  async head() {
    const { data, error } = await db
      .from("cp8_inference_receipts")
      .select("seq,hash")
      .order("seq", { ascending: false })
      .limit(1)
      .maybeSingle();
    if (error) throw new Error(error.message);
    return data;
  },
  async append(row: Record<string, unknown>) {
    const { data, error } = await db.rpc("cp8_inference_receipt_append", { p_row: row });
    if (error) throw new Error(error.message);
    return data;
  },
  async get(id: string) {
    const { data, error } = await db.from("cp8_inference_receipts").select("*").eq("receipt_id", id).maybeSingle();
    if (error) throw new Error(error.message);
    return data;
  },
};

const headers = {
  "content-type": "application/json; charset=utf-8",
  "cache-control": "no-store",
  "access-control-allow-origin": "*",
  "access-control-allow-headers": "authorization, apikey, content-type",
  "access-control-allow-methods": "GET, POST, OPTIONS",
};

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers });
  try {
    const done = await handleGroqTest(req, { env: Deno.env, fetchImpl: fetch, db: adapter });
    return new Response(JSON.stringify(done.body, null, 2), {
      status: done.status,
      headers: { ...headers, ...(done.headers || {}) },
    });
  } catch (error) {
    return new Response(JSON.stringify({
      ok: false,
      error: "server_error",
      message: String((error as Error)?.message || error),
    }), { status: 500, headers });
  }
});
