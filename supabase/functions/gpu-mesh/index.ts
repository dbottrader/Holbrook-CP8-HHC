import { createClient } from "npm:@supabase/supabase-js@2";
import postgres from "npm:postgres@3.4.5";
import { handle } from "./protocol.mjs";
import { createSupabaseStore } from "./supabase_store.mjs";

function serviceKey(): string {
  const legacy = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
  if (legacy) return legacy;
  const raw = Deno.env.get("SUPABASE_SECRET_KEYS") || "";
  if (!raw) return "";
  try {
    const parsed = JSON.parse(raw) as Record<string, string>;
    return parsed.default || Object.values(parsed)[0] || "";
  } catch {
    return "";
  }
}

const supabase = createClient(Deno.env.get("SUPABASE_URL") || "", serviceKey(), {
  auth: { persistSession: false, autoRefreshToken: false },
});

const store = createSupabaseStore(supabase);

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
    const { data, error } = await supabase.schema("cp8_private").rpc("read_named_secret", {
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

Deno.serve((req) => handle(req, {
  store,
  env: Deno.env,
  readVault,
  fetch: globalThis.fetch,
}));
