// Bounded public Groq test. verify_jwt stays false: the route is public,
// rate-limited, and ignores the caller prompt. GROQ_API_KEY and
// INFERENCE_RECEIPT_SIGNING_KEY are read from the function environment first,
// then from Vault names groq_api_key and inference_receipt_signing_key.
// The public key is derived from that seed at runtime. It is not in git.
import { createClient } from "npm:@supabase/supabase-js@2";
import postgres from "npm:postgres@3.4.5";
import { handleGroqTest } from "./handler.mjs";

const db = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!, {
  auth: { persistSession: false, autoRefreshToken: false },
});

async function readVaultViaDatabase(secretName: string): Promise<string> {
  const dbUrl = Deno.env.get("SUPABASE_DB_URL") || "";
  if (!dbUrl) throw new Error("vault_unreachable");
  const sql = postgres(dbUrl, { prepare: false, max: 1 });
  try {
    const rows = await sql.begin(async (tx) => {
      await tx`select set_config('request.jwt.claim.role', 'service_role', true)`;
      return await tx`select cp8_private.read_named_secret(${secretName}) as secret`;
    });
    const value = rows[0]?.secret;
    return typeof value === "string" ? value : "";
  } finally {
    await sql.end({ timeout: 1 });
  }
}

async function readVault(secretName: string): Promise<string> {
  try {
    const { data, error } = await db.schema("cp8_private").rpc("read_named_secret", {
      secret_name: secretName,
    });
    if (!error) return typeof data === "string" ? data : "";
  } catch {
    // The Data API could not see cp8_private. Try the database connection below.
  }
  try {
    return await readVaultViaDatabase(secretName);
  } catch {
    throw new Error("vault_unreachable");
  }
}

const adapter = {
  async publishSigner(publicKeyHex: string) {
    const { error } = await db.from("cp8_inference_signer").upsert({
      id: 1,
      public_key_hex: publicKeyHex,
    });
    if (error) throw new Error("signer_publish_failed");
  },
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
    const done = await handleGroqTest(req, {
      env: Deno.env,
      fetchImpl: fetch,
      db: adapter,
      readVault,
    });
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
