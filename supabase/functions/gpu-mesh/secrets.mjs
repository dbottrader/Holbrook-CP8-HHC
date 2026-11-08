// Read a server secret from the function environment first, then from
// Supabase Vault. Callers must not log the returned value.

export const ENV_GROQ = "GROQ_API_KEY";
export const ENV_SIGNING = "INFERENCE_RECEIPT_SIGNING_KEY";
export const ENV_SETTLER = "GPU_MESH_SETTLER_TOKEN";
export const VAULT_GROQ = "groq_api_key";
export const VAULT_SIGNING = "inference_receipt_signing_key";
export const VAULT_SETTLER = "GPU_MESH_SETTLER_TOKEN";

export function envGet(env, name) {
  if (!env || !name) return "";
  const value = typeof env.get === "function" ? env.get(name) : env[name];
  return String(value || "").trim();
}

export async function readConfiguredSecret(env, envNames, vaultName, readVault) {
  const names = Array.isArray(envNames) ? envNames : [envNames];
  for (const name of names) {
    const fromEnv = envGet(env, name);
    if (fromEnv) return { value: fromEnv, source: "env", vaultReachable: null };
  }
  if (typeof readVault !== "function") {
    return { value: "", source: "missing", vaultReachable: null };
  }
  try {
    const fromVault = await readVault(vaultName);
    const value = String(fromVault ?? "").trim();
    return {
      value,
      source: value ? "vault" : "missing",
      vaultReachable: true,
    };
  } catch {
    return { value: "", source: "missing", vaultReachable: false };
  }
}
