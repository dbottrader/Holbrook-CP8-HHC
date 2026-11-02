import { createClient } from "npm:@supabase/supabase-js@2";
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

Deno.serve((req) => handle(req, {
  store,
  env: {
    GROQ_API_KEY: Deno.env.get("GROQ_API_KEY") || "",
    GPU_MESH_GROQ_MODEL: Deno.env.get("GPU_MESH_GROQ_MODEL") || "",
    GPU_MESH_GROQ_VERIFY_MODEL: Deno.env.get("GPU_MESH_GROQ_VERIFY_MODEL") || "",
    GPU_MESH_SIGNING_KEY: Deno.env.get("GPU_MESH_SIGNING_KEY") || "",
    GPU_MESH_INVITE_ONLY: Deno.env.get("GPU_MESH_INVITE_ONLY") || "",
    GPU_MESH_INVITE_TOKEN: Deno.env.get("GPU_MESH_INVITE_TOKEN") || "",
  },
  fetch: globalThis.fetch,
}));
