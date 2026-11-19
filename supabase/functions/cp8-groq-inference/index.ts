import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const corsHeaders = {
  "Access-Control-Allow-Origin": "https://asin-hhc-moltbook-1gny5j.v2.appdeploy.ai",
  "Access-Control-Allow-Headers": "authorization, content-type, x-cp8-proxy-token",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Content-Type": "application/json",
};

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: corsHeaders });
}

async function sha256(value: string) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return Array.from(new Uint8Array(digest)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: corsHeaders });
  if (req.method !== "POST") return json({ ok: false, error: "method_not_allowed" }, 405);

  const proxyToken = Deno.env.get("CP8_GROQ_PROXY_TOKEN");
  const apiKey = Deno.env.get("GROQ_API_KEY");
  if (!proxyToken || !apiKey) return json({ ok: false, state: "HOLD", error: "server_secrets_not_configured" }, 503);

  const supplied = req.headers.get("x-cp8-proxy-token") || "";
  if (supplied.length !== proxyToken.length) return json({ ok: false, state: "HOLD", error: "unauthorized" }, 401);
  let mismatch = 0;
  for (let i = 0; i < supplied.length; i++) mismatch |= supplied.charCodeAt(i) ^ proxyToken.charCodeAt(i);
  if (mismatch !== 0) return json({ ok: false, state: "HOLD", error: "unauthorized" }, 401);

  let body: any;
  try { body = await req.json(); } catch { return json({ ok: false, state: "HOLD", error: "invalid_json" }, 400); }
  if (!body || !Array.isArray(body.messages) || body.messages.length < 1 || body.messages.length > 40) {
    return json({ ok: false, state: "HOLD", error: "messages_must_be_array_1_to_40" }, 400);
  }

  const messages = [];
  for (const m of body.messages) {
    if (!m || !["system", "user", "assistant"].includes(m.role) || typeof m.content !== "string") {
      return json({ ok: false, state: "HOLD", error: "invalid_message_shape" }, 400);
    }
    if (m.content.length > 20000) return json({ ok: false, state: "HOLD", error: "message_too_large" }, 413);
    messages.push({ role: m.role, content: m.content });
  }

  const model = "openai/gpt-oss-20b";
  const maxTokens = Number.isFinite(Number(body.max_completion_tokens))
    ? Math.min(Math.max(Number(body.max_completion_tokens), 1), 2000) : 800;
  const requestPayload = { model, messages, max_completion_tokens: maxTokens, temperature: 0.2 };
  const requestHash = await sha256(JSON.stringify(requestPayload));

  try {
    const upstream = await fetch("https://api.groq.com/openai/v1/chat/completions", {
      method: "POST",
      headers: { "Authorization": `Bearer ${apiKey}`, "Content-Type": "application/json" },
      body: JSON.stringify(requestPayload),
      signal: AbortSignal.timeout(45000),
    });
    const data = await upstream.json().catch(() => ({}));
    if (!upstream.ok) {
      console.error("Groq upstream error", { status: upstream.status, requestHash });
      return json({ ok: false, state: "HOLD", error: "provider_request_failed", provider_status: upstream.status, request_hash: requestHash }, 502);
    }
    const output = data?.choices?.[0]?.message?.content;
    if (typeof output !== "string") return json({ ok: false, state: "HOLD", error: "provider_response_missing_text", request_hash: requestHash }, 502);
    return json({
      ok: true, state: "OBSERVED_UNVERIFIED", promotion: "HOLD", provider: "groq",
      model: data.model || model, provider_request_id: data.id || null, output,
      usage: data.usage || null, request_hash: requestHash, output_sha256: await sha256(output),
      evidence_note: "Inference executed; output is not independently verified and grants no CP8 promotion authority."
    });
  } catch (error) {
    console.error("Groq proxy failure", { requestHash, error: String(error) });
    return json({ ok: false, state: "HOLD", error: "provider_unreachable", request_hash: requestHash }, 502);
  }
});