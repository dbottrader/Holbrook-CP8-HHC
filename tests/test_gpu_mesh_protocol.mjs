import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { createMemoryStore } from "../supabase/functions/gpu-mesh/memory_store.mjs";
import {
  CHAIN,
  CLAIM_POLL_MS,
  RESULT_POLL_MS,
  handle,
  independentVerifiers,
  timingSafeEqualText,
  verifyMeshReceipt,
} from "../supabase/functions/gpu-mesh/protocol.mjs";

const COORD = "https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/gpu-mesh";

function freshSeed() {
  const bytes = crypto.getRandomValues(new Uint8Array(32));
  return [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
}

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

async function register(store, name, clock, extra = {}) {
  const { status, data } = await call(store, "/api/nodes/register", {
    method: "POST",
    body: {
      name,
      backend: "llamacpp",
      models: [{ id: "SmolLM2-360M-Instruct", resident: true, digest: "pin" }],
      gpu: { model: "cpu", vram_mb: 0 },
      ...extra,
    },
  }, {}, clock);
  assert.equal(status, 200, JSON.stringify(data));
  return data;
}

async function work(store, token, text, clock, env = {}) {
  const claimed = await call(store, "/api/nodes/jobs/claim?wait=0", { method: "POST", token }, env, clock);
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
  }, env, clock);
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
  const env = { INFERENCE_RECEIPT_SIGNING_KEY: freshSeed() };
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
  }), { store, env, clock, pollMs: 15 });

  let served = null;
  for (let i = 0; i < 20 && !served; i++) {
    served = await work(store, a.token, "MESH_OK", clock, env);
    if (!served) await new Promise((resolve) => setTimeout(resolve, 20));
  }
  assert.ok(served, "primary worker did not receive the job");
  let checked = null;
  for (let i = 0; i < 20 && !checked; i++) {
    checked = await work(store, b.token, "MESH_OK", clock, env);
    if (!checked) await new Promise((resolve) => setTimeout(resolve, 20));
  }
  assert.ok(checked, "second worker did not receive the verification");

  const response = await pending;
  const early = await response.json();
  assert.equal(response.status, 200, JSON.stringify(early));
  assert.equal(early.choices[0].message.content, "MESH_OK");
  assert.equal(early.gpumesh.worker_name, "worker-a");
  const follow = await call(store, `/v1/jobs/${early.gpumesh.job_id}`, {}, env, clock);
  const data = follow.data;
  assert.equal(follow.status, 200, JSON.stringify(data));
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
  const env = { INFERENCE_RECEIPT_SIGNING_KEY: freshSeed() };
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
    }), { store, env, clock, pollMs: 15 });
    let served = null;
    for (let i = 0; i < 20 && !served; i++) {
      served = await work(store, a.token, `same-${n}`, clock, env);
      if (!served) await new Promise((resolve) => setTimeout(resolve, 15));
    }
    let checked = null;
    for (let i = 0; i < 20 && !checked; i++) {
      checked = await work(store, b.token, `same-${n}`, clock, env);
      if (!checked) await new Promise((resolve) => setTimeout(resolve, 15));
    }
    const response = await pending;
    const early = await response.json();
    assert.equal(response.status, 200, JSON.stringify(early));
    const follow = await call(store, `/v1/jobs/${early.gpumesh.job_id}`, {}, env, clock);
    assert.equal(follow.status, 200, JSON.stringify(follow.data));
    assert.equal(follow.data.gpumesh.verdict, "agree");
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
  }), {
    store,
    env: { GROQ_API_KEY: "test-key", INFERENCE_RECEIPT_SIGNING_KEY: freshSeed() },
    fetch: fetchGroq,
    pollMs: 10,
  });
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
  assert.equal(raw.includes(data.gpumesh.receipt.signer) && data.gpumesh.receipt.signer.length === 64, true);
});

test("health reports configuration and does not invent a signing key", async () => {
  const store = createMemoryStore();
  const missing = await call(store, "/health");
  assert.equal(missing.status, 200);
  assert.equal(missing.data.groq_configured, false);
  assert.equal(missing.data.signer_configured, false);
  assert.equal(missing.data.public_key_hex, null);

  const seed = freshSeed();
  const present = await call(store, "/.well-known/inference-receipt-key.json", {}, {
    GROQ_API_KEY: "vault-not-used",
    INFERENCE_RECEIPT_SIGNING_KEY: seed,
  });
  assert.equal(present.status, 200);
  assert.equal(present.data.signer_configured, true);
  assert.equal(typeof present.data.public_key_hex, "string");
  assert.equal(present.data.public_key_hex.length, 64);
  assert.equal(JSON.stringify(present.data).includes(seed), false);
  assert.equal(JSON.stringify(present.data).includes("vault-not-used"), false);
});

test("Vault supplies the Groq key and the signing seed without echoing them", async () => {
  const store = createMemoryStore();
  const seed = freshSeed();
  const seen = [];
  const response = await handle(req("/health"), {
    store,
    env: {},
    readVault: async (name) => {
      seen.push(name);
      if (name === "groq_api_key") return "from-vault-groq";
      if (name === "inference_receipt_signing_key") return seed;
      return "";
    },
  });
  const data = await response.json();
  assert.equal(response.status, 200);
  assert.equal(data.groq_configured, true);
  assert.equal(data.signer_configured, true);
  assert.equal(data.public_key_hex.length, 64);
  assert.equal(data.vault_reachable, true);
  assert.deepEqual(seen.sort(), ["groq_api_key", "inference_receipt_signing_key"]);
  const raw = JSON.stringify(data);
  assert.equal(raw.includes(seed), false);
  assert.equal(raw.includes("from-vault-groq"), false);
});

test("Groq is not called when the signer is missing", async () => {
  let called = false;
  const response = await handle(req("/v1/chat/completions", {
    method: "POST",
    body: { model: "auto", messages: [{ role: "user", content: "Hello" }] },
  }), {
    store: createMemoryStore(),
    env: { GROQ_API_KEY: "test-key" },
    fetch: async () => {
      called = true;
      return new Response("{}", { status: 200 });
    },
  });
  const data = await response.json();
  assert.equal(response.status, 503);
  assert.equal(data.error.code, "signer_not_configured");
  assert.equal(called, false);
  assert.equal(JSON.stringify(data).includes("test-key"), false);
});

test("the coordinator does not store a private signing seed", () => {
  const protocol = readFileSync(new URL("../supabase/functions/gpu-mesh/protocol.mjs", import.meta.url), "utf8");
  const store = readFileSync(new URL("../supabase/functions/gpu-mesh/supabase_store.mjs", import.meta.url), "utf8");
  const sql = readFileSync(new URL("../supabase/migrations/20261102143000_gpu_mesh_coordinator.sql", import.meta.url), "utf8");
  const chain = readFileSync(new URL("../supabase/migrations/20261108013000_gpu_mesh_base_sepolia_settlement.sql", import.meta.url), "utf8");
  assert.equal(protocol.includes("private_hex"), false);
  assert.equal(store.includes("private_hex"), false);
  assert.equal(sql.includes("private_hex"), false);
  assert.equal(chain.includes("private_hex"), false);
  assert.equal(chain.includes("deployer"), true);
  assert.match(chain, /enable row level security/i);
  assert.equal(chain.includes("gpumesh_chain_settlements"), true);
  assert.equal(protocol.includes("SKIP_VERIFIER"), false);
  assert.equal(protocol.includes('ledger: "simulated"'), false);
  assert.equal(protocol.includes("GPU_MESH_SETTLER_TOKEN"), true);
  const secrets = readFileSync(new URL("../supabase/functions/gpu-mesh/secrets.mjs", import.meta.url), "utf8");
  assert.match(secrets, /export const ENV_SETTLER = "GPU_MESH_SETTLER_TOKEN"/);
  assert.match(secrets, /export const VAULT_SETTLER = "gpu_mesh_settler_token"/);
});

test("an empty environment reads the settler token from the lowercase Vault name", async () => {
  const seen = [];
  const response = await handle(req("/api/settlements/pending", { token: "vault-settler" }), {
    store: createMemoryStore(),
    env: {},
    readVault: async (name) => {
      seen.push(name);
      return name === "gpu_mesh_settler_token" ? "vault-settler" : "";
    },
  });
  const data = await response.json();
  assert.equal(response.status, 200, JSON.stringify(data));
  assert.deepEqual(data.settlements, []);
  assert.deepEqual(seen, ["gpu_mesh_settler_token"]);
  assert.equal(JSON.stringify(data).includes("vault-settler"), false);
});

test("verifier independence is two ids, neither of them the worker", async () => {
  assert.equal(independentVerifiers("worker", ["v1", "v2"]), true);
  assert.equal(independentVerifiers("worker", ["worker", "v2"]), false);
  assert.equal(independentVerifiers("worker", ["v1", "v1"]), false);
  assert.equal(independentVerifiers("worker", ["v1"]), false);
  assert.equal(await timingSafeEqualText("same-token", "same-token"), true);
  assert.equal(await timingSafeEqualText("same-token", "other-token"), false);
  assert.equal(await timingSafeEqualText("short", "much-longer-token"), false);
});

test("registration stores cuda hardware and stats lists the node", async () => {
  const store = createMemoryStore();
  const clock = () => 1_700_000_000;
  const registered = await call(store, "/api/nodes/register", {
    method: "POST",
    body: {
      name: "rig",
      backend: "ollama",
      models: [{ id: "qwen2.5:7b-instruct", resident: true, source: "ollama" }],
      gpu: {
        vendor: "nvidia",
        model: "NVIDIA GeForce RTX 4090",
        vram_mb: 24564,
        count: 1,
        driver: "550.90",
        accelerator: "cuda",
      },
    },
  }, {}, clock);
  assert.equal(registered.status, 200, JSON.stringify(registered.data));
  const nodes = await store.listNodes();
  assert.equal(nodes[0].accelerator, "cuda");
  assert.equal(nodes[0].gpu_name, "NVIDIA GeForce RTX 4090");
  assert.equal(nodes[0].vram_mb, 24564);
  assert.equal(nodes[0].backend, "ollama");
  const stats = await call(store, "/api/stats", {}, {}, clock);
  assert.equal(stats.status, 200);
  assert.equal(stats.data.nodes[0].name, "rig");
  assert.equal(stats.data.nodes[0].accelerator, "cuda");
  assert.equal(stats.data.nodes[0].vram_mb, 24564);
  const cpu = await call(store, "/api/nodes/register", {
    method: "POST",
    body: { name: "laptop", backend: "cpu", models: ["mock-tiny"], gpu: { model: "cpu", vram_mb: 0, count: 0 } },
  }, {}, clock);
  assert.equal(cpu.status, 200, JSON.stringify(cpu.data));
  const again = await store.listNodes();
  const laptop = again.find((node) => node.name === "laptop");
  assert.equal(laptop.accelerator, "cpu");
});

test("health and stats name Base Sepolia contracts", async () => {
  const store = createMemoryStore();
  const health = await call(store, "/health");
  assert.equal(health.status, 200);
  assert.equal(health.data.ledger, "base-sepolia");
  assert.equal(health.data.chain_id, 84532);
  assert.equal(health.data.hhcw, CHAIN.hhcw);
  assert.equal(health.data.settlement, CHAIN.settlement);
  assert.equal(health.data.hhcw_url, `https://sepolia.basescan.org/address/${CHAIN.hhcw}`);
  assert.equal(health.data.settlement_url, `https://sepolia.basescan.org/address/${CHAIN.settlement}`);
  const stats = await call(store, "/api/stats");
  assert.equal(stats.data.ledger, "base-sepolia");
  assert.equal(stats.data.hhcw, CHAIN.hhcw);
  assert.equal(stats.data.settlement, CHAIN.settlement);
});

test("payout address is optional and must be a non-zero EVM address", async () => {
  const store = createMemoryStore();
  const bad = await call(store, "/api/nodes/register", {
    method: "POST",
    body: { name: "rig", backend: "cpu", models: ["mock-tiny"], payout_address: "not-an-address" },
  });
  assert.equal(bad.status, 400);
  assert.equal(bad.data.error.code, "bad_payout_address");
  const zero = await call(store, "/api/nodes/register", {
    method: "POST",
    body: { name: "rig", backend: "cpu", models: ["mock-tiny"], payout_address: "0x" + "0".repeat(40) },
  });
  assert.equal(zero.status, 400);
  const clock = () => Date.now() / 1000;
  const joined = await register(store, "rig", clock, {
    payout_address: "0x1111111111111111111111111111111111111111",
  });
  const node = (await store.listNodes()).find((row) => row.id === joined.node_id);
  assert.equal(node.payout_address, "0x1111111111111111111111111111111111111111");
});

test("settler routes require the bearer token and record a Base tx", async () => {
  const store = createMemoryStore();
  const locked = await call(store, "/api/settlements/pending");
  assert.equal(locked.status, 503);
  const env = {
    INFERENCE_RECEIPT_SIGNING_KEY: freshSeed(),
    GPU_MESH_SETTLER_TOKEN: "settler-test-token",
  };
  const wrong = await call(store, "/api/settlements/pending", { token: "nope" }, env);
  assert.equal(wrong.status, 401);
  assert.equal(JSON.stringify(wrong.data).includes("settler-test-token"), false);

  const clock = () => Date.now() / 1000;
  const payout = {
    a: "0x1111111111111111111111111111111111111111",
    b: "0x2222222222222222222222222222222222222222",
    c: "0x3333333333333333333333333333333333333333",
  };
  const a = await register(store, "worker-a", clock, { payout_address: payout.a });
  const b = await register(store, "worker-b", clock, { payout_address: payout.b });
  const c = await register(store, "worker-c", clock, { payout_address: payout.c });
  const pendingChat = handle(req("/v1/chat/completions", {
    method: "POST",
    body: {
      model: "SmolLM2-360M-Instruct",
      temperature: 0,
      max_tokens: 16,
      messages: [{ role: "user", content: "Reply with exactly the token: MESH_OK" }],
    },
    headers: { "x-gpumesh-wait-seconds": "2" },
  }), { store, env, clock, pollMs: 15 });

  let served = null;
  for (let i = 0; i < 20 && !served; i++) {
    served = await work(store, a.token, "MESH_OK", clock, env);
    if (!served) await new Promise((resolve) => setTimeout(resolve, 20));
  }
  assert.ok(served, "primary worker did not receive the job");
  const second = await store.listJobs(["queued"]);
  assert.equal(second.some((job) => job.kind === "verification" && job.excluded.includes(a.node_id)), true);
  let checked = null;
  for (let i = 0; i < 20 && !checked; i++) {
    checked = await work(store, b.token, "MESH_OK", clock, env);
    if (!checked) await new Promise((resolve) => setTimeout(resolve, 20));
  }
  assert.ok(checked, "first verifier did not receive the check");
  const response = await pendingChat;
  const chatBody = await response.json();
  assert.equal(response.status, 200, JSON.stringify(chatBody));
  const settled = await call(store, `/v1/jobs/${chatBody.gpumesh.job_id}`, {}, env, clock);
  assert.equal(settled.status, 200, JSON.stringify(settled.data));
  assert.equal(settled.data.gpumesh.verdict, "agree");
  assert.equal(settled.data.gpumesh.receipt.amount, 4);
  const waiting = await store.listChainSettlements(["awaiting_second_verifier"]);
  assert.equal(waiting.length, 1);
  assert.equal(waiting[0].worker_id, a.node_id);
  assert.equal(waiting[0].verifier1_id, b.node_id);
  assert.notEqual(waiting[0].verifier1_id, a.node_id);
  const early = await call(store, "/api/settlements/pending", { token: "settler-test-token" }, env, clock);
  assert.equal(early.status, 200);
  assert.deepEqual(early.data.settlements, []);
  const queued = await store.listJobs(["queued"]);
  const verify2 = queued.find((job) => job.client_key === "verify2");
  assert.ok(verify2, "second duplicate check was not queued");
  assert.equal(verify2.excluded.includes(a.node_id), true);
  assert.equal(verify2.excluded.includes(b.node_id), true);

  let confirmed = null;
  for (let i = 0; i < 20 && !confirmed; i++) {
    confirmed = await work(store, c.token, "MESH_OK", clock, env);
    if (!confirmed) await new Promise((resolve) => setTimeout(resolve, 20));
  }
  assert.ok(confirmed, "second verifier did not receive the check");
  const ready = await call(store, "/api/settlements/pending", { token: "settler-test-token" }, env, clock);
  assert.equal(ready.status, 200, JSON.stringify(ready.data));
  assert.equal(ready.data.settlements.length, 1);
  const item = ready.data.settlements[0];
  assert.equal(item.worker_id, a.node_id);
  assert.deepEqual([item.verifier1_id, item.verifier2_id].sort(), [b.node_id, c.node_id].sort());
  assert.equal(item.verifier1_id === a.node_id || item.verifier2_id === a.node_id, false);
  assert.equal(item.worker_address, payout.a);
  assert.equal(item.amount, 4000);
  assert.equal(item.receipt.kind, "inference_receipt");
  assert.equal(item.receipt.amount, 4000);
  const claim = await verifyMeshReceipt(item.receipt);
  assert.equal(claim.ok, true, claim.error);
  assert.equal(claim.claim.payload.verifier_decision, "agree");
  assert.deepEqual(claim.claim.verifier_ids.split(",").sort(), [b.node_id, c.node_id].sort());

  const tx = "0x" + "ab".repeat(32);
  const posted = await call(store, "/api/settlements/result", {
    method: "POST",
    token: "settler-test-token",
    body: { id: item.id, tx_hash: tx, status: "settled" },
  }, env, clock);
  assert.equal(posted.status, 200, JSON.stringify(posted.data));
  assert.equal(posted.data.tx_url, `https://sepolia.basescan.org/tx/${tx}`);
  const again = await call(store, "/api/settlements/result", {
    method: "POST",
    token: "settler-test-token",
    body: { id: item.id, tx_hash: "0x" + "cd".repeat(32), status: "settled" },
  }, env, clock);
  assert.equal(again.status, 409);
  const job = await call(store, `/v1/jobs/${item.job_id}`);
  assert.equal(job.data.gpumesh.settlement_tx_hash, tx);
  assert.equal(job.data.gpumesh.settlement_tx_url, posted.data.tx_url);
  const receipts = await call(store, "/api/receipts?limit=50");
  assert.equal(receipts.data.receipts.some((row) => row.settlement_tx_hash === tx && row.settlement_tx_url.endsWith(tx.slice(2))), true);
  const stats = await call(store, "/api/stats", {}, env, clock);
  assert.equal(stats.data.ledger, "base-sepolia");
  assert.equal(stats.data.settlements_settled, 1);
  assert.equal(stats.data.settlement_txs[0].tx_hash, tx);
  const drained = await call(store, "/api/settlements/pending", { token: "settler-test-token" }, env, clock);
  assert.deepEqual(drained.data.settlements, []);
});

test("a settlement without payout addresses is skipped and can resume", async () => {
  const store = createMemoryStore();
  const env = {
    INFERENCE_RECEIPT_SIGNING_KEY: freshSeed(),
    GPU_MESH_SETTLER_TOKEN: "settler-test-token",
  };
  const clock = () => Date.now() / 1000;
  const a = await register(store, "worker-a", clock);
  const b = await register(store, "worker-b", clock);
  const c = await register(store, "worker-c", clock);
  const pendingChat = handle(req("/v1/chat/completions", {
    method: "POST",
    body: { model: "auto", temperature: 0, messages: [{ role: "user", content: "ping" }] },
    headers: { "x-gpumesh-wait-seconds": "2" },
  }), { store, env, clock, pollMs: 15 });
  let served = null;
  for (let i = 0; i < 20 && !served; i++) {
    served = await work(store, a.token, "same", clock, env);
    if (!served) await new Promise((resolve) => setTimeout(resolve, 15));
  }
  let checked = null;
  for (let i = 0; i < 20 && !checked; i++) {
    checked = await work(store, b.token, "same", clock, env);
    if (!checked) await new Promise((resolve) => setTimeout(resolve, 15));
  }
  const response = await pendingChat;
  assert.equal(response.status, 200);
  let confirmed = null;
  for (let i = 0; i < 20 && !confirmed; i++) {
    confirmed = await work(store, c.token, "same", clock, env);
    if (!confirmed) await new Promise((resolve) => setTimeout(resolve, 15));
  }
  assert.ok(confirmed);
  const ready = await call(store, "/api/settlements/pending", { token: "settler-test-token" }, env, clock);
  assert.equal(ready.data.settlements.length, 1);
  assert.equal(ready.data.settlements[0].worker_address, "");
  const skipped = await call(store, "/api/settlements/result", {
    method: "POST",
    token: "settler-test-token",
    body: { id: ready.data.settlements[0].id, tx_hash: "", status: "skipped_missing_payout" },
  }, env, clock);
  assert.equal(skipped.status, 200);
  const hidden = await call(store, "/api/settlements/pending", { token: "settler-test-token" }, env, clock);
  assert.deepEqual(hidden.data.settlements, []);
  const address = ["0x1111111111111111111111111111111111111111", "0x2222222222222222222222222222222222222222", "0x3333333333333333333333333333333333333333"];
  for (const [node, payout] of [[a, address[0]], [b, address[1]], [c, address[2]]]) {
    const beat = await call(store, "/api/nodes/heartbeat", {
      method: "POST",
      token: node.token,
      body: { payout_address: payout },
    }, env, clock);
    assert.equal(beat.status, 200, JSON.stringify(beat.data));
  }
  const resumed = await call(store, "/api/settlements/pending", { token: "settler-test-token" }, env, clock);
  assert.equal(resumed.status, 200, JSON.stringify(resumed.data));
  assert.equal(resumed.data.settlements.length, 1);
  assert.equal(resumed.data.settlements[0].worker_address, address[0]);
  assert.equal(resumed.data.settlements[0].status, "pending");
});

test("deployed poll intervals stay inside a few hundred milliseconds", () => {
  assert.ok(RESULT_POLL_MS >= 250 && RESULT_POLL_MS <= 500, RESULT_POLL_MS);
  assert.ok(CLAIM_POLL_MS >= 250 && CLAIM_POLL_MS <= 500, CLAIM_POLL_MS);
});

test("a claim heartbeat touch does not reset inflight or quarantine", async () => {
  const store = createMemoryStore();
  const clock = () => Date.now() / 1000;
  const joined = await register(store, "worker", clock);
  const node = (await store.listNodes()).find((row) => row.id === joined.node_id);
  node.inflight = 3;
  node.status = "offline";
  await store.saveNode(node);
  await store.touchHeartbeat(node.id, 12345);
  const again = (await store.listNodes()).find((row) => row.id === joined.node_id);
  assert.equal(again.inflight, 3);
  assert.equal(again.last_heartbeat, 12345);
  assert.equal(again.status, "online");
  again.status = "quarantined";
  again.inflight = 2;
  await store.saveNode(again);
  await store.touchHeartbeat(again.id, 12346);
  const held = (await store.listNodes()).find((row) => row.id === joined.node_id);
  assert.equal(held.status, "quarantined");
  assert.equal(held.inflight, 2);
  assert.equal(held.last_heartbeat, 12346);
});

test("claim long-poll checks the queue often and sweeps rarely", async () => {
  const store = createMemoryStore();
  const clock = () => Date.now() / 1000;
  const joined = await register(store, "worker", clock);
  let listed = 0;
  let queued = 0;
  let nodes = 0;
  const origJobs = store.listJobs.bind(store);
  const origQueued = store.listQueuedForClaim.bind(store);
  const origNodes = store.listNodes.bind(store);
  store.listJobs = async (...args) => {
    listed += 1;
    return origJobs(...args);
  };
  store.listQueuedForClaim = async (...args) => {
    queued += 1;
    return origQueued(...args);
  };
  store.listNodes = async (...args) => {
    nodes += 1;
    return origNodes(...args);
  };
  const started = Date.now();
  const response = await handle(req("/api/nodes/jobs/claim?wait=0.35", {
    method: "POST",
    token: joined.token,
  }), { store, clock, pollMs: 40 });
  const elapsed = Date.now() - started;
  const data = await response.json();
  assert.equal(response.status, 200, JSON.stringify(data));
  assert.equal(data.job, null);
  assert.ok(elapsed < 1000, `claim held ${elapsed}ms`);
  assert.ok(queued >= 4, `queue checks ${queued}`);
  assert.ok(nodes <= 2, `node sweeps ${nodes}`);
  assert.ok(listed <= 2, `full job lists ${listed}`);
});

test("a lone worker reply returns when the result is stored, not at the wait deadline", async () => {
  const store = createMemoryStore();
  const env = { INFERENCE_RECEIPT_SIGNING_KEY: freshSeed() };
  const clock = () => Date.now() / 1000;
  const worker = await register(store, "ollama", clock);
  const waitSec = 8;
  const started = Date.now();
  const pending = handle(req("/v1/chat/completions", {
    method: "POST",
    body: { model: "auto", messages: [{ role: "user", content: "Say hi" }] },
    headers: { "x-gpumesh-wait-seconds": String(waitSec) },
  }), { store, env, clock, pollMs: 40 });
  let served = null;
  for (let i = 0; i < 40 && !served; i++) {
    served = await work(store, worker.token, "hello-from-worker", clock, env);
    if (!served) await new Promise((resolve) => setTimeout(resolve, 20));
  }
  assert.ok(served, "worker did not receive the job");
  const postedAt = Date.now();
  const response = await pending;
  const after = Date.now() - postedAt;
  const total = Date.now() - started;
  const data = await response.json();
  assert.equal(response.status, 200, JSON.stringify(data));
  assert.equal(data.choices[0].message.content, "hello-from-worker");
  assert.equal(data.gpumesh.status, "verifying");
  assert.equal(data.gpumesh.verdict, "pending");
  assert.equal(data.gpumesh.credits, 0);
  assert.ok(after < 2000, `held ${after}ms after the worker posted`);
  assert.ok(total < 4000, `chat took ${total}ms toward a ${waitSec}s deadline`);
  const queued = await store.listJobs(["queued"]);
  assert.equal(queued.some((job) => job.kind === "verification" && job.excluded.includes(worker.node_id)), true);
  const node = (await store.listNodes()).find((row) => row.id === worker.node_id);
  assert.equal(node.credits, 0);
  assert.equal(node.escrow_credits, 0);
});
