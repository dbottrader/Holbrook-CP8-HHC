// Drives the real gpu-mesh handler (in-memory store) through every flow
// scenario in formal/settlement/model_table.json and compares the end state
// with the Lean model of protocol.mjs (formal/settlement/Settlement/Flow.lean).
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { sha256Text } from "../supabase/functions/gpu-mesh/canon.mjs";
import { createMemoryStore } from "../supabase/functions/gpu-mesh/memory_store.mjs";
import { handle } from "../supabase/functions/gpu-mesh/protocol.mjs";

const table = JSON.parse(readFileSync(new URL("../formal/settlement/model_table.json", import.meta.url), "utf8"));
const WORKER_TEXT = "ALPHA";
const TEXT = { agree: WORKER_TEXT, disagree_deterministic: "BETA" };

function seed() {
  return [...crypto.getRandomValues(new Uint8Array(32))].map((b) => b.toString(16).padStart(2, "0")).join("");
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

async function call(ctx, path, opts = {}) {
  const response = await handle(req(path, opts), { ...ctx, pollMs: 10 });
  return { status: response.status, data: await response.json() };
}

async function register(ctx, name) {
  const { status, data } = await call(ctx, "/api/nodes/register", {
    method: "POST",
    body: {
      name,
      backend: "llamacpp",
      models: [{ id: "SmolLM2-360M-Instruct", resident: true, digest: "pin" }],
      gpu: { model: "cpu", vram_mb: 0 },
    },
  });
  assert.equal(status, 200, JSON.stringify(data));
  return data;
}

async function workOnce(ctx, token, text) {
  const claimed = await call(ctx, "/api/nodes/jobs/claim?wait=0", { method: "POST", token });
  assert.equal(claimed.status, 200, JSON.stringify(claimed.data));
  const job = claimed.data.job;
  if (!job) return null;
  if (job.commit_required) {
    const committed = await call(ctx, `/api/nodes/jobs/${job.job_id}/commit`, {
      method: "POST",
      token,
      body: { commitment: await sha256Text(text), fencing_token: job.fencing_token },
    });
    assert.equal(committed.status, 200, JSON.stringify(committed.data));
  }
  const done = await call(ctx, `/api/nodes/jobs/${job.job_id}/result`, {
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
  });
  assert.equal(done.status, 200, JSON.stringify(done.data));
  return job;
}

async function work(ctx, token, text) {
  for (let i = 0; i < 40; i++) {
    const job = await workOnce(ctx, token, text);
    if (job) return job;
    await new Promise((resolve) => setTimeout(resolve, 15));
  }
  return null;
}

const balance = (node) => (node.credits || 0) + (node.escrow_credits || 0);

for (const scenario of table.flow) {
  test(`Lean flow model matches protocol.mjs: ${scenario.name}`, async () => {
    const store = createMemoryStore();
    const env = { INFERENCE_RECEIPT_SIGNING_KEY: seed(), GPU_MESH_SETTLER_TOKEN: "settler-test-token" };
    const ctx = { store, env, clock: () => Date.now() / 1000 };
    const nodes = {};
    for (const name of ["a", "b", "c", "d"]) nodes[name] = await register(ctx, `node-${name}`);
    const letter = Object.fromEntries(Object.entries(nodes).map(([k, v]) => [v.node_id, k]));

    const chat = handle(req("/v1/chat/completions", {
      method: "POST",
      body: { model: "auto", messages: [{ role: "user", content: "Say alpha" }] },
      headers: { "x-gpumesh-wait-seconds": "2" },
    }), { ...ctx, pollMs: 15 });
    const parent = await work(ctx, nodes.a.token, WORKER_TEXT);
    assert.ok(parent, "worker a got no job");

    for (const [index, ev] of scenario.events.entries()) {
      const job = await work(ctx, nodes[ev.node].token, TEXT[ev.verdict]);
      assert.ok(job, `${ev.check} check by ${ev.node} found no job`);
      if (index === 0) await chat;
    }

    const row = await store.getChainSettlement(`mesh:${parent.job_id}`);
    const all = await store.listNodes();
    const byLetter = Object.fromEntries(all.map((node) => [letter[node.id], node]));
    const queued = await store.listJobs(["queued"]);
    const got = {
      status: row ? row.status : "none",
      amount: row ? row.amount || 0 : 0,
      mesh_credits: row ? row.mesh_credits || 0 : 0,
      worker_balance: balance(byLetter.a),
      verifier1: row ? letter[row.verifier1_id] || "" : "",
      verifier2: row ? letter[row.verifier2_id] || "" : "",
      tiebreak_queued: queued.some((job) => job.client_key === "verify_tiebreak"),
      checker_balance: { b: balance(byLetter.b), c: balance(byLetter.c), d: balance(byLetter.d) },
    };
    const want = {
      status: scenario.status,
      amount: scenario.amount,
      mesh_credits: scenario.mesh_credits,
      worker_balance: scenario.worker_balance,
      verifier1: scenario.verifier1,
      verifier2: scenario.verifier2,
      tiebreak_queued: scenario.tiebreak_queued,
      checker_balance: Object.fromEntries(Object.entries(scenario.checker_balance).map(([k, v]) => [k, Number(v)])),
    };
    assert.deepEqual(got, want);
    const parentJob = await store.getJob(parent.job_id);
    assert.equal(parentJob.credits_awarded || 0, scenario.credits_awarded);
  });
}
