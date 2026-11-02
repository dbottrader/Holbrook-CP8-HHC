import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { createMemoryStore } from "../supabase/functions/gpu-mesh/memory_store.mjs";
import { handle, verifyMeshReceipt } from "../supabase/functions/gpu-mesh/protocol.mjs";

const COORD = "https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/gpu-mesh";

function req(path, { method = "GET", body, token, headers = {} } = {}) {
  const init = { method, headers: { ...headers } };
  if (body !== undefined) {
    init.headers["content-type"] = "application/json";
    init.body = JSON.stringify(body);
  }
  if (token) init.headers.authorization = `Bearer ${token}`;
  return new Request(`https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/gpu-mesh${path}`, init);
}

async function call(store, path, opts = {}, env = {}, clock) {
  const response = await handle(req(path, opts), { store, env, clock, pollMs: 10 });
  const data = await response.json();
  return { status: response.status, data };
}

async function register(store, name, clock) {
  const { status, data } = await call(store, "/api/nodes/register", {
    method: "POST",
    body: {
      name,
      backend: "llamacpp",
      models: [{ id: "SmolLM2-360M-Instruct", resident: true, digest: "pin" }],
      gpu: { model: "cpu", vram_mb: 0 },
    },
  }, {}, clock);
  assert.equal(status, 200, JSON.stringify(data));
  return data;
}

async function work(store, token, text, clock) {
  const claimed = await call(store, "/api/nodes/jobs/claim?wait=0", { method: "POST", token }, {}, clock);
  assert.equal(claimed.status, 200, JSON.stringify(claimed.data));
  const job = claimed.data.job;
  if (!job) return null;
  const done = await call(store, `/api/nodes/jobs/${job.job_id}/result`, {
    method: "POST",
    token,
    body: {
      output_text: text,
      prompt_tokens: 8,
      completion_tokens: 4,
      duration_ms: 30,
      finish_reason: "stop",
      fencing_token: job.fencing_token,
    },
  }, {}, clock);
  assert.equal(done.status, 200, JSON.stringify(done.data));
  return job;
}

test("canon file served to the browser matches the edge function", () => {
  const site = readFileSync(new URL("../site/mesh-receipt.js", import.meta.url));
  const edge = readFileSync(new URL("../supabase/functions/gpu-mesh/canon.mjs", import.meta.url));
  assert.deepEqual(site, edge);
});

test("no workers and no Groq key is a clear 503", async () => {
  const { status, data } = await call(createMemoryStore(), "/v1/chat/completions", {
    method: "POST",
    body: { model: "auto", messages: [{ role: "user", content: "Hello" }] },
  });
  assert.equal(status, 503);
  assert.equal(data.error.message, "no workers online");
  assert.equal(data.error.code, "no_workers");
});

test("published open invite is optional, and required only when invite mode is on", async () => {
  const open = createMemoryStore();
  const joined = await call(open, "/api/nodes/register", {
    method: "POST",
    body: { name: "stranger", backend: "cpu", models: ["mock-tiny"] },
  });
  assert.equal(joined.status, 200, JSON.stringify(joined.data));
  assert.match(joined.data.token, /^gmt_/);

  const locked = createMemoryStore();
  const denied = await call(locked, "/api/nodes/register", {
    method: "POST",
    body: { name: "stranger", backend: "cpu", models: ["mock-tiny"] },
  }, { GPU_MESH_INVITE_ONLY: "1" });
  assert.equal(denied.status, 403);
  const allowed = await call(locked, "/api/nodes/register", {
    method: "POST",
    headers: { "x-gpumesh-invite": "open" },
    body: { name: "stranger", backend: "cpu", models: ["mock-tiny"] },
  }, { GPU_MESH_INVITE_ONLY: "1" });
  assert.equal(allowed.status, 200, JSON.stringify(allowed.data));
});

test("two workers verify and the award receipt is canon v1", async () => {
  const store = createMemoryStore();
  const clock = () => Date.now() / 1000;
  const a = await register(store, "worker-a", clock);
  const b = await register(store, "worker-b", clock);
  const pending = handle(req("/v1/chat/completions", {
    method: "POST",
    body: {
      model: "SmolLM2-360M-Instruct",
      temperature: 0,
      max_tokens: 16,
      messages: [{ role: "user", content: "Reply with exactly the token: MESH_OK" }],
    },
    headers: { "x-gpumesh-wait-seconds": "2" },
  }), { store, env: {}, clock, pollMs: 15 });

  let served = null;
  for (let i = 0; i < 20 && !served; i++) {
    served = await work(store, a.token, "MESH_OK", clock);
    if (!served) await new Promise((resolve) => setTimeout(resolve, 20));
  }
  assert.ok(served, "primary worker did not receive the job");
  let checked = null;
  for (let i = 0; i < 20 && !checked; i++) {
    checked = await work(store, b.token, "MESH_OK", clock);
    if (!checked) await new Promise((resolve) => setTimeout(resolve, 20));
  }
  assert.ok(checked, "second worker did not receive the verification");

  const response = await pending;
  const data = await response.json();
  assert.equal(response.status, 200, JSON.stringify(data));
  assert.equal(data.choices[0].message.content, "MESH_OK");
  assert.equal(data.gpumesh.worker_name, "worker-a");
  assert.equal(data.gpumesh.verdict, "agree");
  assert.equal(data.gpumesh.credit_hold, true);
  const receipt = data.gpumesh.receipt;
  assert.equal(receipt.kind, "inference_receipt");
  assert.equal(receipt.canon, "v1");
  assert.equal(receipt.amount, 4);
  const check = await verifyMeshReceipt(receipt);
  assert.equal(check.ok, true, check.error);
  assert.equal(check.claim.payload.verifier_decision, "agree");
  const nodes = await store.listNodes();
  const worker = nodes.find((node) => node.name === "worker-a");
  assert.equal(worker.trusted, 0);
  assert.equal(worker.credits, 0);
  assert.equal(worker.escrow_credits, 4);
  assert.equal(data.gpumesh.worker_id, worker.id);
  assert.ok(COORD.endsWith("/gpu-mesh"));
});

test("seven days and three verified jobs release the hold", async () => {
  const store = createMemoryStore();
  let now = Date.now() / 1000 - 8 * 24 * 3600;
  const clock = () => now;
  const a = await register(store, "worker-a", clock);
  const b = await register(store, "worker-b", clock);
  now = Date.now() / 1000;
  assert.equal((await call(store, "/api/nodes/heartbeat", {
    method: "POST",
    token: a.token,
    body: { name: "worker-a", backend: "llamacpp", models: [{ id: "SmolLM2-360M-Instruct" }] },
  }, {}, clock)).status, 200);
  assert.equal((await call(store, "/api/nodes/heartbeat", {
    method: "POST",
    token: b.token,
    body: { name: "worker-b", backend: "llamacpp", models: [{ id: "SmolLM2-360M-Instruct" }] },
  }, {}, clock)).status, 200);

  for (let n = 0; n < 3; n++) {
    const pending = handle(req("/v1/chat/completions", {
      method: "POST",
      body: { model: "auto", temperature: 0, messages: [{ role: "user", content: `ping ${n}` }] },
      headers: { "x-gpumesh-wait-seconds": "2" },
    }), { store, env: {}, clock, pollMs: 15 });
    let served = null;
    for (let i = 0; i < 20 && !served; i++) {
      served = await work(store, a.token, `same-${n}`, clock);
      if (!served) await new Promise((resolve) => setTimeout(resolve, 15));
    }
    let checked = null;
    for (let i = 0; i < 20 && !checked; i++) {
      checked = await work(store, b.token, `same-${n}`, clock);
      if (!checked) await new Promise((resolve) => setTimeout(resolve, 15));
    }
    const response = await pending;
    const data = await response.json();
    assert.equal(response.status, 200, JSON.stringify(data));
    assert.equal(data.gpumesh.verdict, "agree");
  }
  const worker = (await store.listNodes()).find((node) => node.name === "worker-a");
  assert.equal(worker.trusted, 1);
  assert.equal(worker.escrow_credits, 0);
  assert.ok(worker.credits >= 4);
  assert.ok(worker.verified_jobs >= 3);
});

test("Groq fallback signs a canon receipt and does not mint", async () => {
  const store = createMemoryStore();
  const calls = [];
  const fetchGroq = async (_url, init) => {
    const body = JSON.parse(init.body);
    calls.push(body.model);
    const text = body.model.startsWith("openai/") ? "from-groq" : "from-groq";
    return new Response(JSON.stringify({
      choices: [{ message: { content: text }, finish_reason: "stop" }],
      usage: { prompt_tokens: 3, completion_tokens: 2 },
    }), { status: 200, headers: { "content-type": "application/json" } });
  };
  const response = await handle(req("/v1/chat/completions", {
    method: "POST",
    body: { model: "auto", messages: [{ role: "user", content: "Say hi" }] },
  }), { store, env: { GROQ_API_KEY: "test-key" }, fetch: fetchGroq, pollMs: 10 });
  const data = await response.json();
  assert.equal(response.status, 200, JSON.stringify(data));
  assert.equal(data.choices[0].message.content, "from-groq");
  assert.equal(data.gpumesh.worker_name, "groq-fallback");
  assert.equal(data.gpumesh.receipt.kind, "groq_inference_receipt");
  assert.equal(data.gpumesh.receipt.amount, 0);
  assert.deepEqual(calls, ["openai/gpt-oss-20b", "llama-3.1-8b-instant"]);
  const check = await verifyMeshReceipt(data.gpumesh.receipt);
  assert.equal(check.ok, true, check.error);
  const raw = JSON.stringify(data);
  assert.equal(raw.includes("test-key"), false);
});
