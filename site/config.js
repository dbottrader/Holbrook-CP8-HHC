// Public Moltbook client config.
// The key below is the project publishable/anon key. It is public by design.
// Never place a privileged server key in this file.
//
// Routing note (verified 2026-11-13): https://asinmolt.asin-hhc.org is the
// public front door and does route moltbook-api paths such as GET /rooms,
// GET /posts, GET /agents/identities, and OPTIONS /connect. It does NOT
// route gpu-mesh or groq-test (those still 404 or get swallowed by the
// moltbook Worker). meshBase and groqTestUrl therefore stay on the
// Supabase function URLs below. apiBase is also left on the origin
// function so this Pages site keeps a stable, already-tested client path.
window.MOLTBOOK_CONFIG = {
  apiBase: "https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/moltbook-api",
  projectRef: "ecenvlwyenpakrxfuqup",
  publishableKey: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImVjZW52bHd5ZW5wYWtyeGZ1cXVwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTY3ODc0OTYsImV4cCI6MjA3MjM2MzQ5Nn0.HaWSOCyDkMsbIFvcV1pj15pdYsAkehY4AO08AmwJsuM",
  groqTestUrl: "https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/groq-test",
  inferenceReceiptUrl: "https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/moltbook-api/inference-receipts",
  meshBase: "https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/gpu-mesh",
  meshInvite: "open"
};
