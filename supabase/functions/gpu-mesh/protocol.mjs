/**
 * Public GPU mesh coordinator.
 *
 * Speaks the worker calls in gpumesh_node/agent.py: register, heartbeat,
 * claim, chunks, result, fail. Public callers use OpenAI /v1/chat/completions.
 * A second online worker verifies. The award is a canon-v1 inference_receipt.
 * Credits stay in hold until the worker is 7 days old and has 3 verified jobs.
 * With no online worker, Groq is the fallback when GROQ_API_KEY is set.
 */

import {
  GENESIS_PREV,
  canonDumps,
  publicFromSeed,
  sha256Text,
  signMeshReceipt,
  verifyMeshReceipt,
} from "./canon.mjs";
import {
  ENV_GROQ,
  ENV_SIGNING,
  VAULT_GROQ,
  VAULT_SIGNING,
  envGet,
  readConfiguredSecret,
} from "./secrets.mjs";

export const PUBLIC_COORDINATOR = "https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/gpu-mesh";
export const OPEN_INVITE = "open";

const MAX_TOKENS = 256;
const MAX_PROMPT = 4000;
const MAX_MESSAGES = 16;
const HEARTBEAT_TIMEOUT = 30;
const JOB_TIMEOUT = 120;
const REGISTER_PER_HOUR = 10;
const ANON_RPM = 20;
const MAX_NODES = 64;
const TRUST_AGE = 7 * 24 * 3600;
const TRUST_JOBS = 3;
const VERIFIER_PAY = 2;
const MAX_ATTEMPTS = 3;
const VERIFY_THRESHOLD = 0.82;
const REPLAY = new Set(["completed", "verifying", "verified", "disputed", "rejected", "failed", "cancelled"]);
const ACTIVE = new Set(["leased", "running"]);

const HEADERS = {
  "content-type": "application/json; charset=utf-8",
  "cache-control": "no-store",
  "access-control-allow-origin": "*",
  "access-control-allow-headers": "authorization, content-type, x-gpumesh-invite, x-gpumesh-wait-seconds, apikey",
  "access-control-allow-methods": "GET, POST, OPTIONS",
};

function mesh(status, message, code, type = "invalid_request_error") {
  const error = new Error(message);
  error.status = status;
  error.code = code;
  error.errType = type;
  return error;
}

function json(data, status = 200, extra = {}) {
  return new Response(JSON.stringify(data), { status, headers: { ...HEADERS, ...extra } });
}

function routeOf(url) {
  const parts = new URL(url).pathname.split("/").filter(Boolean);
  const at = parts.indexOf("gpu-mesh");
  const rest = at >= 0 ? parts.slice(at + 1) : parts;
  return `/${rest.join("/")}`;
}

function clientIp(req) {
  return req.headers.get("cf-connecting-ip")
    || req.headers.get("x-forwarded-for")?.split(",")[0]?.trim()
    || "unknown";
}

function clock(ctx) {
  return ctx.clock ? ctx.clock() : Date.now() / 1000;
}

function bearer(req) {
  const header = req.headers.get("authorization") || "";
  return header.toLowerCase().startsWith("bearer ") ? header.slice(7).trim() : "";
}

async function readJson(req) {
  try {
    const data = await req.json();
    if (!data || typeof data !== "object" || Array.isArray(data)) throw mesh(400, "JSON body must be an object", "invalid_json");
    return data;
  } catch (error) {
    if (error.status) throw error;
    throw mesh(400, "request body must be JSON", "invalid_json");
  }
}

function hexId(prefix, bytes) {
  const raw = crypto.getRandomValues(new Uint8Array(bytes));
  const hex = [...raw].map((b) => b.toString(16).padStart(2, "0")).join("");
  return prefix + hex;
}

function normalize(text) {
  return String(text || "").toLowerCase().split(/\s+/).filter(Boolean).join(" ");
}

function similarity(left, right) {
  const a = normalize(left);
  const b = normalize(right);
  if (a === b) return 1;
  if (!a || !b) return 0;
  const aw = a.split(" ");
  const bw = b.split(" ");
  const bag = new Map();
  for (const word of aw) bag.set(word, (bag.get(word) || 0) + 1);
  let common = 0;
  for (const word of bw) {
    const have = bag.get(word) || 0;
    if (have) {
      bag.set(word, have - 1);
      common += 1;
    }
  }
  return (2 * common) / (aw.length + bw.length);
}

function judge(parentText, childText, temperature) {
  if (!String(parentText || "").trim()) return "parent_empty";
  if (!String(childText || "").trim()) return "child_empty";
  if (similarity(parentText, childText) >= VERIFY_THRESHOLD) return "agree";
  return temperature <= 0 ? "disagree_deterministic" : "disagree_sampling";
}

function weight(node) {
  if (node.backend === "cpu" || !(node.vram_mb > 0)) return 1;
  if (node.vram_mb >= 20000) return 8;
  if (node.vram_mb >= 12000) return 4;
  return 2;
}

function serves(node, model) {
  const ids = (node.models || []).map((item) => item.id);
  if (model === "auto" || model === "mesh") return ids.length > 0;
  return ids.includes(model);
}

function freshOnline(nodes, now) {
  return nodes.filter((node) => node.status === "online" && now - (node.last_heartbeat || 0) <= HEARTBEAT_TIMEOUT);
}

function resolveModel(nodes, requested, now) {
  const online = freshOnline(nodes, now);
  if (requested !== "auto" && requested !== "mesh") {
    return online.some((node) => serves(node, requested)) ? requested : null;
  }
  const counts = new Map();
  for (const node of online) {
    for (const model of node.models || []) counts.set(model.id, (counts.get(model.id) || 0) + 1);
  }
  let best = null;
  let bestN = 0;
  for (const [id, n] of counts) {
    if (n > bestN) {
      best = id;
      bestN = n;
    }
  }
  return best;
}

async function allow(store, bucket, limit, windowSec) {
  const now = Math.floor(Date.now() / 1000);
  const windowStart = now - (now % windowSec);
  const hits = await store.hitRate(bucket, windowStart);
  return hits <= limit;
}

function seedBytes(hex) {
  if (!/^[0-9a-f]{64}$/i.test(String(hex || ""))) return null;
  return Uint8Array.from(String(hex).match(/../g).map((part) => parseInt(part, 16)));
}

async function material(ctx) {
  if (ctx._material) return ctx._material;
  const groq = await readConfiguredSecret(ctx.env, ENV_GROQ, VAULT_GROQ, ctx.readVault);
  const signing = await readConfiguredSecret(
    ctx.env,
    [ENV_SIGNING, "GPU_MESH_SIGNING_KEY"],
    VAULT_SIGNING,
    ctx.readVault,
  );
  const seed = seedBytes(signing.value);
  const publicKey = seed ? await publicFromSeed(seed) : null;
  const vaultFlags = [groq.vaultReachable, signing.vaultReachable].filter((flag) => flag !== null);
  ctx._material = {
    groqKey: groq.value,
    groqConfigured: Boolean(groq.value),
    seed,
    publicKey,
    signerConfigured: Boolean(seed),
    signingKeyInvalid: Boolean(signing.value) && !seed,
    vaultReachable: vaultFlags.length === 0 ? null : vaultFlags.every(Boolean),
  };
  return ctx._material;
}

async function ensureSeed(store, ctx) {
  if (ctx._seed) return ctx._seed;
  const mat = await material(ctx);
  if (!mat.seed) {
    throw mesh(
      503,
      "Set INFERENCE_RECEIPT_SIGNING_KEY or Vault secret inference_receipt_signing_key before receipts can be signed.",
      "signer_not_configured",
      "server_error",
    );
  }
  ctx._seed = mat.seed;
  if (typeof store.upsertSigner === "function") {
    await store.upsertSigner({ public_hex: mat.publicKey });
  }
  if (!(await store.tip())) {
    const entry = await signMeshReceipt({
      actor: "genesis",
      kind: "genesis",
      payload: {
        network: "GPU-MESH",
        mesh: "public-edge",
        signer: mat.publicKey,
        ledger_backend: "simulated",
        note: "HHC is a work token and a utility credit for verified contribution.",
        amount: 0,
        credits: 0,
      },
      prevHash: GENESIS_PREV,
      seq: 1,
      ts: Date.now(),
      privateSeed: ctx._seed,
    });
    await store.insertLedger(entry);
  }
  return ctx._seed;
}

async function append(store, ctx, actor, kind, payload) {
  const seed = await ensureSeed(store, ctx);
  for (let attempt = 0; attempt < 6; attempt++) {
    const tip = await store.tip();
    const seq = tip ? tip.seq + 1 : 1;
    const prev = tip ? tip.hash : GENESIS_PREV;
    const entry = await signMeshReceipt({
      actor,
      kind,
      payload,
      prevHash: prev,
      seq,
      ts: Date.now(),
      privateSeed: seed,
    });
    if (await store.insertLedger(entry)) return entry;
  }
  throw mesh(409, "settlement could not be recorded", "settle_race");
}

async function maybeRelease(store, ctx, node) {
  if (node.trusted) return node;
  if (clock(ctx) - node.created_at < TRUST_AGE) return node;
  if (node.verified_jobs < TRUST_JOBS) return node;
  node.trusted = 1;
  const released = node.escrow_credits || 0;
  node.credits = (node.credits || 0) + released;
  node.escrow_credits = 0;
  await store.saveNode(node);
  if (released) {
    await append(store, ctx, node.id, "kudos_release", {
      schema: "gpumesh.kudos_release.v1",
      node_id: node.id,
      worker_id: node.id,
      amount: released,
      credits: released,
      settlement_id: `${node.id}:kudos_release:${node.verified_jobs}`,
      reason: "trusted",
    });
  }
  return node;
}

async function settle(store, ctx, { key, job, node, kind, amount, payload }) {
  const existing = await store.getSettlement(key);
  if (existing) return store.ledgerBySeq(existing.ledger_seq);
  const body = {
    ...payload,
    settlement_id: key,
    worker_id: node.id,
    node_id: node.id,
    amount,
    credits: amount,
  };
  if (amount > 0) {
    if (node.trusted) node.credits = (node.credits || 0) + amount;
    else node.escrow_credits = (node.escrow_credits || 0) + amount;
    await store.saveNode(node);
  }
  const entry = await append(store, ctx, node.id, kind, body);
  const inserted = await store.insertSettlement({
    idempotency_key: key,
    job_id: job.id,
    node_id: node.id,
    kind,
    credits: amount,
    ledger_seq: entry.seq,
  });
  if (!inserted) {
    const again = await store.getSettlement(key);
    return store.ledgerBySeq(again.ledger_seq);
  }
  if (amount > 0 && ["inference_receipt", "canary_pass", "verification_pass"].includes(kind)) {
    node.verified_jobs = (node.verified_jobs || 0) + 1;
    await store.saveNode(node);
    await maybeRelease(store, ctx, node);
  }
  return entry;
}

function blankJob(partial) {
  return {
    temperature: 0,
    max_tokens: 256,
    seed: null,
    stop: null,
    assigned_node_id: "",
    origin_node_id: "",
    parent_job_id: "",
    excluded: [],
    attempt: 0,
    max_attempts: MAX_ATTEMPTS,
    output_text: "",
    output_hash: "",
    prompt_tokens: 0,
    completion_tokens: 0,
    duration_ms: 0,
    finish_reason: "",
    credits_awarded: 0,
    error: "",
    verdict: "",
    client_key: "",
    receipt_hash: "",
    assigned_at: 0,
    completed_at: 0,
    deadline_at: 0,
    lease_generation: 0,
    lease_expires_at: 0,
    model_digest: "",
    priority: 0,
    ...partial,
  };
}

function requeue(job, nodeId, error) {
  const excluded = new Set(job.excluded || []);
  if (nodeId) excluded.add(nodeId);
  job.excluded = [...excluded];
  job.assigned_node_id = "";
  job.assigned_at = 0;
  job.deadline_at = 0;
  job.lease_expires_at = 0;
  job.error = String(error || "").slice(0, 500);
  if (job.attempt >= job.max_attempts) {
    job.status = "failed";
    job.completed_at = Date.now() / 1000;
    return "failed";
  }
  job.status = "queued";
  return "queued";
}

async function sweep(store, now) {
  const nodes = await store.listNodes();
  const byId = new Map(nodes.map((node) => [node.id, node]));
  for (const node of nodes) {
    if (node.status === "online" && now - (node.last_heartbeat || 0) > HEARTBEAT_TIMEOUT) {
      node.status = "offline";
      node.inflight = 0;
      await store.saveNode(node);
    }
  }
  const active = await store.listJobs(["leased", "running"]);
  for (const job of active) {
    const node = byId.get(job.assigned_node_id);
    const offline = !node || node.status !== "online";
    const expired = job.lease_expires_at && now > job.lease_expires_at;
    if (!offline && !expired) continue;
    if (!offline && node) {
      node.inflight = Math.max(0, (node.inflight || 0) - 1);
      await store.saveNode(node);
    }
    requeue(job, job.assigned_node_id, offline ? "heartbeat timeout" : "lease expired");
    await store.saveJob(job);
  }
}

function cleanModels(raw, backend) {
  if (!Array.isArray(raw) || !raw.length) throw mesh(400, "advertise at least one model", "no_models");
  if (raw.length > 64) throw mesh(400, "too many models", "too_many_models");
  return raw.map((item) => {
    const model = typeof item === "string" ? { id: item } : item;
    if (!model || typeof model !== "object" || !String(model.id || "").trim()) throw mesh(400, "each model needs an id", "bad_model");
    const id = String(model.id).trim();
    if (id.length > 128) throw mesh(400, "model id is not usable", "bad_model");
    return {
      id,
      resident: Boolean(model.resident),
      source: String(model.source || backend).slice(0, 32),
      digest: String(model.digest || (backend === "cpu" ? "cpu-fallback" : "unpinned")).slice(0, 128),
    };
  });
}

function gpuOf(raw) {
  const gpu = raw && typeof raw === "object" ? raw : {};
  return {
    gpu_name: String(gpu.model || gpu.name || "cpu").slice(0, 160),
    vram_mb: Math.max(0, Number(gpu.vram_mb) || 0),
    gpu_count: Math.max(0, Number(gpu.count) || 0),
    driver: String(gpu.driver || "").slice(0, 64),
  };
}

function flatten(content) {
  if (content == null) return "";
  if (typeof content === "string") return content;
  if (Array.isArray(content)) {
    return content.map((part) => {
      if (typeof part === "string") return part;
      if (part && typeof part === "object") {
        if (["image_url", "input_image", "image"].includes(part.type)) throw mesh(400, "image inputs are not supported", "unsupported_content");
        if (part.type === "text") return String(part.text || "");
      }
      return "";
    }).join("\n");
  }
  throw mesh(400, "unsupported content", "unsupported_content");
}

function parseChat(data) {
  const requested = String(data.model || "auto").trim() || "auto";
  if (requested.length > 128) throw mesh(400, "model is required", "model_required");
  const raw = data.messages;
  if (!Array.isArray(raw) || !raw.length) throw mesh(400, "messages must be a non-empty list", "messages_required");
  if (raw.length > MAX_MESSAGES) throw mesh(400, `at most ${MAX_MESSAGES} messages`, "too_many_messages");
  if (data.n != null && data.n !== 1) throw mesh(400, "only n=1 is supported", "unsupported_n");
  let total = 0;
  const messages = raw.map((item) => {
    if (!item || typeof item !== "object") throw mesh(400, "each message must be an object", "bad_message");
    const role = String(item.role || "");
    if (!["system", "user", "assistant", "tool"].includes(role)) throw mesh(400, `unsupported role ${role}`, "bad_role");
    const content = flatten(item.content);
    total += content.length;
    return { role, content };
  });
  if (!total) throw mesh(400, "messages are empty", "empty_prompt");
  if (total > MAX_PROMPT) throw mesh(400, `prompt exceeds ${MAX_PROMPT} characters`, "prompt_too_long");
  let temperature = Number(data.temperature ?? 0.7);
  if (!Number.isFinite(temperature)) throw mesh(400, "temperature must be a number", "bad_temperature");
  temperature = Math.max(0, Math.min(2, temperature));
  let maxTokens = Number(data.max_tokens ?? data.max_completion_tokens ?? 256);
  if (!Number.isInteger(maxTokens)) throw mesh(400, "max_tokens must be an integer", "bad_max_tokens");
  if (maxTokens < 1) throw mesh(400, "max_tokens is out of range", "bad_max_tokens");
  maxTokens = Math.min(maxTokens, MAX_TOKENS);
  return { model: requested, messages, temperature, max_tokens: maxTokens, stream: Boolean(data.stream) };
}

async function authNode(req, store) {
  const token = bearer(req);
  if (!token) throw mesh(401, "node token required", "node_required", "authentication_error");
  const node = await store.nodeByTokenHash(await sha256Text(token));
  if (!node) throw mesh(401, "unknown node token", "unknown_node", "authentication_error");
  if (node.status === "banned") throw mesh(403, "node banned", "banned", "permission_error");
  return node;
}

function jobForNode(job) {
  return {
    job_id: job.id,
    model: job.model,
    messages: job.messages || [],
    temperature: job.temperature,
    max_tokens: job.max_tokens,
    seed: job.seed,
    stop: job.stop ?? null,
    deadline_at: job.deadline_at,
    fencing_token: job.lease_generation,
    lease_generation: job.lease_generation,
    lease_expires_at: job.lease_expires_at,
    model_digest: job.model_digest || "",
  };
}

function resultBody(job) {
  return {
    ok: ["completed", "verifying", "verified", "disputed"].includes(job.status),
    job_id: job.id,
    status: job.status,
    receipt: job.receipt_hash,
    credits: job.credits_awarded || 0,
    verdict: job.verdict || "",
    output_hash: job.output_hash || "",
  };
}

function completion(job, receipt, extra) {
  const prompt = job.prompt_tokens || 0;
  const completionTokens = job.completion_tokens || 0;
  return {
    id: `chatcmpl-${String(job.id).replace(/^job_/, "")}`,
    object: "chat.completion",
    created: Math.floor(job.created_at || Date.now() / 1000),
    model: job.model,
    choices: [{
      index: 0,
      message: { role: "assistant", content: job.output_text || "" },
      finish_reason: job.finish_reason || "stop",
    }],
    usage: { prompt_tokens: prompt, completion_tokens: completionTokens, total_tokens: prompt + completionTokens },
    system_fingerprint: `fp_${String(receipt?.hash || job.receipt_hash || "none").slice(0, 16)}`,
    gpumesh: {
      job_id: job.id,
      worker_id: extra.worker_id || job.assigned_node_id || "",
      worker_name: extra.worker_name || "",
      verifier_ids: extra.verifier_ids || "",
      verdict: job.verdict || "",
      credits: job.credits_awarded || 0,
      credit_hold: Boolean(extra.credit_hold),
      receipt_hash: receipt?.hash || job.receipt_hash || "",
      receipt,
      status: job.status,
      promotion: "HOLD",
    },
  };
}

async function register(req, store, ctx) {
  const spec = await readJson(req);
  const ip = clientIp(req);
  if (!(await allow(store, `register:${ip}`, REGISTER_PER_HOUR, 3600))) {
    throw mesh(429, "rate limit exceeded", "register", "rate_limit_error");
  }
  const inviteOnly = envGet(ctx.env, "GPU_MESH_INVITE_ONLY") === "1";
  const presented = req.headers.get("x-gpumesh-invite") || String(spec.invite || "");
  const expected = envGet(ctx.env, "GPU_MESH_INVITE_TOKEN") || OPEN_INVITE;
  if (inviteOnly && presented !== expected) {
    throw mesh(403, "an invite is required to join this cohort", "invite_required", "permission_error");
  }
  if ((await store.countNodes()) >= MAX_NODES) throw mesh(503, "the node cohort is full", "cohort_full", "server_error");
  const name = String(spec.name || "").trim();
  if (!name || name.length > 63) throw mesh(400, "name is required (63 characters max)", "bad_name");
  const backend = String(spec.backend || "cpu");
  if (!["cpu", "ollama", "vllm", "llamacpp"].includes(backend)) throw mesh(400, "backend must be ollama, vllm, llamacpp, or cpu", "bad_backend");
  const models = cleanModels(spec.models, backend);
  const token = `gmt_${hexId("", 16)}`;
  const now = clock(ctx);
  const node = {
    id: hexId("node_", 6),
    name,
    token_hash: await sha256Text(token),
    backend,
    ...gpuOf(spec.gpu),
    models,
    status: "online",
    reputation: 100,
    strikes: 0,
    credits: 0,
    escrow_credits: 0,
    suspicion: 0,
    trusted: 0,
    verified_jobs: 0,
    consecutive_failures: 0,
    jobs_completed: 0,
    jobs_failed: 0,
    inflight: 0,
    max_inflight: 1,
    last_heartbeat: now,
    last_ip: ip.slice(0, 64),
    created_at: now,
    version: String(spec.version || "").slice(0, 32),
  };
  await store.insertNode(node);
  let receipt = null;
  const mat = await material(ctx);
  if (mat.signerConfigured) {
    const entry = await append(store, ctx, node.id, "node_register", {
      schema: "gpumesh.node_register.v1",
      node_id: node.id,
      name: node.name,
      backend: node.backend,
      gpu: node.gpu_name,
      vram_mb: node.vram_mb,
      models: models.map((model) => model.id),
      amount: 0,
      credits: 0,
    });
    receipt = entry.hash;
  }
  return json({
    node_id: node.id,
    token,
    receipt,
    status: node.status,
    signer_configured: mat.signerConfigured,
  });
}

async function heartbeat(req, store, ctx) {
  const spec = await readJson(req);
  const node = await authNode(req, store);
  if (node.status === "quarantined") return json({ ok: false, node_id: node.id, status: node.status });
  const backend = String(spec.backend || node.backend);
  node.backend = ["cpu", "ollama", "vllm", "llamacpp"].includes(backend) ? backend : node.backend;
  if (Array.isArray(spec.models) && spec.models.length) node.models = cleanModels(spec.models, node.backend);
  Object.assign(node, gpuOf(spec.gpu || { model: node.gpu_name, vram_mb: node.vram_mb, count: node.gpu_count, driver: node.driver }));
  node.last_heartbeat = clock(ctx);
  node.last_ip = clientIp(req).slice(0, 64);
  if (node.status === "offline") node.status = "online";
  node.version = String(spec.version || node.version || "").slice(0, 32);
  await store.saveNode(node);
  await sweep(store, clock(ctx));
  return json({ ok: true, node_id: node.id, status: node.status });
}

async function claimOnce(store, ctx, node) {
  await sweep(store, clock(ctx));
  const current = await store.nodeByTokenHash(node.token_hash);
  if (!current || current.status !== "online") return null;
  if ((current.inflight || 0) >= (current.max_inflight || 1)) return null;
  const ids = new Set((current.models || []).map((model) => model.id));
  const queued = (await store.listJobs(["queued"]))
    .filter((job) => ids.has(job.model))
    .sort((a, b) => (b.priority - a.priority) || (a.created_at - b.created_at));
  const now = clock(ctx);
  for (const job of queued) {
    if ((job.excluded || []).includes(current.id)) continue;
    if (job.kind === "verification" && job.origin_node_id === current.id) continue;
    const generation = (job.lease_generation || 0) + 1;
    const deadline = now + JOB_TIMEOUT;
    const model = (current.models || []).find((item) => item.id === job.model);
    const leased = await store.leaseJob(job.id, {
      assigned_node_id: current.id,
      assigned_at: now,
      deadline_at: deadline,
      lease_expires_at: deadline,
      lease_generation: generation,
      attempt: (job.attempt || 0) + 1,
      model_digest: model?.digest || "",
    });
    if (!leased) continue;
    current.inflight = (current.inflight || 0) + 1;
    await store.saveNode(current);
    return leased;
  }
  return null;
}

async function claim(req, store, ctx) {
  const node = await authNode(req, store);
  const url = new URL(req.url);
  let wait = Number(url.searchParams.get("wait") ?? "0");
  if (!Number.isFinite(wait)) throw mesh(400, "wait must be a number", "bad_wait");
  wait = Math.max(0, Math.min(wait, 20));
  const deadline = Date.now() + wait * 1000;
  let job = await claimOnce(store, ctx, node);
  while (!job && Date.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, ctx.pollMs || 400));
    job = await claimOnce(store, ctx, node);
  }
  return json({ job: job ? jobForNode(job) : null });
}

async function enqueueVerification(store, parent) {
  const job = blankJob({
    id: hexId("job_", 6),
    kind: "verification",
    status: "queued",
    model: parent.model,
    messages: parent.messages,
    temperature: 0,
    max_tokens: parent.max_tokens,
    seed: parent.temperature <= 0 && parent.seed != null ? parent.seed : 0,
    stop: parent.stop,
    origin_node_id: parent.assigned_node_id,
    parent_job_id: parent.id,
    excluded: parent.assigned_node_id ? [parent.assigned_node_id] : [],
    client_key: "verify",
    created_at: Date.now() / 1000,
    priority: 100,
  });
  await store.insertJob(job);
  return job;
}

async function finishVerification(store, ctx, node, job) {
  const parent = job.parent_job_id ? await store.getJob(job.parent_job_id) : null;
  if (!parent?.output_text) {
    job.status = "rejected";
    job.verdict = "skip";
    await store.saveJob(job);
    return;
  }
  const verdict = judge(parent.output_text, job.output_text, parent.temperature);
  const kind = verdict === "agree" ? "verification_pass" : (verdict === "disagree_sampling" ? "verification_disagree" : "verification_fail");
  const verifierReceipt = await settle(store, ctx, {
    key: `${job.id}:verifier_award`,
    job,
    node,
    kind,
    amount: verdict === "child_empty" ? 0 : VERIFIER_PAY,
    payload: {
      schema: "gpumesh.verification.v1",
      job_id: job.id,
      parent_job_id: parent.id,
      model: job.model,
      output_hash: job.output_hash,
      parent_output_hash: parent.output_hash,
      verifier_ids: node.id,
      verifier_decision: verdict,
      toploc: "unavailable",
    },
  });
  job.receipt_hash = verifierReceipt.hash;
  job.verdict = verdict;
  job.credits_awarded = verdict === "child_empty" ? 0 : VERIFIER_PAY;
  if (verdict === "agree") {
    const origin = (await store.listNodes()).find((item) => item.id === parent.assigned_node_id);
    if (origin && origin.id !== node.id) {
      const award = Math.max(1, parent.completion_tokens || 1) * weight(origin);
      const awardReceipt = await settle(store, ctx, {
        key: `${parent.id}:worker_award`,
        job: parent,
        node: origin,
        kind: "inference_receipt",
        amount: award,
        payload: {
          schema: "gpumesh.execution.v1",
          job_id: parent.id,
          lease_generation: parent.lease_generation || 0,
          node_id: origin.id,
          worker_id: origin.id,
          model: parent.model,
          model_digest: parent.model_digest || "",
          runtime: origin.backend,
          backend: origin.backend,
          temperature: parent.temperature,
          max_tokens: parent.max_tokens,
          seed: parent.seed || 0,
          prompt_tokens: parent.prompt_tokens,
          completion_tokens: parent.completion_tokens,
          duration_ms: parent.duration_ms,
          output_hash: parent.output_hash,
          verifier_decision: "agree",
          verifier_ids: node.id,
          toploc: "unavailable",
          amount: award,
          credits: award,
        },
      });
      parent.credits_awarded = award;
      parent.receipt_hash = awardReceipt.hash;
      parent.status = "verified";
      parent.verdict = "agree";
      job.status = "verified";
    } else {
      parent.status = "disputed";
      parent.verdict = "agree";
      job.status = "disputed";
    }
  } else {
    parent.status = "disputed";
    parent.verdict = verdict;
    job.status = "disputed";
  }
  await store.saveJob(parent);
  await store.saveJob(job);
}

async function submitResult(req, store, ctx, jobId) {
  const spec = await readJson(req);
  const node = await authNode(req, store);
  const job = await store.getJob(jobId);
  if (!job) throw mesh(404, "unknown job", "unknown_job");
  if (REPLAY.has(job.status) && job.assigned_node_id === node.id) return json(resultBody(job));
  if (job.assigned_node_id !== node.id) throw mesh(403, "job is not assigned to this node", "not_your_job", "permission_error");
  const fence = spec.fencing_token == null || spec.fencing_token === "" ? null : Number(spec.fencing_token);
  if (fence !== null && fence !== (job.lease_generation || 0)) throw mesh(409, "stale lease", "stale_lease");
  if (job.lease_expires_at && clock(ctx) > job.lease_expires_at) throw mesh(409, "lease expired", "lease_expired");
  if (!ACTIVE.has(job.status)) throw mesh(409, `job is ${job.status}`, "job_not_active");
  let text = String(spec.output_text ?? "");
  let finish = ["stop", "length", "error"].includes(spec.finish_reason) ? spec.finish_reason : "stop";
  if (text.length > 8000) {
    text = text.slice(0, 8000);
    finish = "length";
  }
  node.inflight = Math.max(0, (node.inflight || 0) - 1);
  if (!text.trim()) {
    node.consecutive_failures = (node.consecutive_failures || 0) + 1;
    node.jobs_failed = (node.jobs_failed || 0) + 1;
    await store.saveNode(node);
    requeue(job, node.id, "empty output");
    await store.saveJob(job);
    return json({ ok: false, status: job.status, job_id: job.id, error: "empty output" });
  }
  const completionTokens = Math.min(
    Math.max(Number(spec.completion_tokens) || 0, text.trim() ? 1 : 0),
    Math.max(job.max_tokens, 1),
    MAX_TOKENS,
  );
  job.output_text = text;
  job.output_hash = await sha256Text(text);
  job.prompt_tokens = Math.max(0, Number(spec.prompt_tokens) || 0);
  job.completion_tokens = completionTokens;
  job.duration_ms = Math.max(0, Math.min(Number(spec.duration_ms) || 0, 3_600_000));
  job.finish_reason = finish;
  job.completed_at = clock(ctx);
  job.error = "";
  node.consecutive_failures = 0;
  node.jobs_completed = (node.jobs_completed || 0) + 1;
  await store.saveNode(node);
  if (job.kind === "verification") {
    await store.saveJob(job);
    await finishVerification(store, ctx, node, job);
    const done = await store.getJob(job.id);
    return json(resultBody(done));
  }
  const execution = await settle(store, ctx, {
    key: `${job.id}:execution`,
    job,
    node,
    kind: "execution_submitted",
    amount: 0,
    payload: {
      schema: "gpumesh.execution.v1",
      job_id: job.id,
      node_id: node.id,
      worker_id: node.id,
      model: job.model,
      output_hash: job.output_hash,
      verifier_decision: "pending",
      verifier_ids: "",
      amount: 0,
      credits: 0,
    },
  });
  job.receipt_hash = execution.hash;
  job.verdict = "pending";
  job.credits_awarded = 0;
  job.status = "verifying";
  await store.saveJob(job);
  await enqueueVerification(store, job);
  return json(resultBody(job));
}

async function submitFail(req, store, ctx, jobId) {
  const spec = await readJson(req);
  const node = await authNode(req, store);
  const job = await store.getJob(jobId);
  if (!job) throw mesh(404, "unknown job", "unknown_job");
  if (job.assigned_node_id !== node.id) throw mesh(403, "job is not assigned to this node", "not_your_job", "permission_error");
  if (REPLAY.has(job.status)) return json({ ok: true, status: job.status, job_id: job.id });
  node.inflight = Math.max(0, (node.inflight || 0) - 1);
  node.consecutive_failures = (node.consecutive_failures || 0) + 1;
  node.jobs_failed = (node.jobs_failed || 0) + 1;
  await store.saveNode(node);
  const status = requeue(job, node.id, spec.error || "node reported failure");
  await store.saveJob(job);
  return json({ ok: true, status, job_id: job.id });
}

async function groqCall(ctx, model, parsed, apiKey) {
  const started = Date.now();
  const response = await (ctx.fetch || fetch)("https://api.groq.com/openai/v1/chat/completions", {
    method: "POST",
    headers: {
      authorization: `Bearer ${apiKey}`,
      "content-type": "application/json",
    },
    body: JSON.stringify({
      model,
      messages: parsed.messages,
      temperature: 0,
      max_completion_tokens: parsed.max_tokens,
    }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw mesh(502, "groq fallback failed", "groq_failed", "server_error");
  }
  const text = data?.choices?.[0]?.message?.content || "";
  return {
    text: String(text),
    prompt_tokens: Number(data?.usage?.prompt_tokens) || 0,
    completion_tokens: Number(data?.usage?.completion_tokens) || 0,
    duration_ms: Date.now() - started,
    finish_reason: data?.choices?.[0]?.finish_reason || "stop",
  };
}

async function groqFallback(store, ctx, parsed) {
  const mat = await material(ctx);
  const model = envGet(ctx.env, "GPU_MESH_GROQ_MODEL") || "openai/gpt-oss-20b";
  const verifier = envGet(ctx.env, "GPU_MESH_GROQ_VERIFY_MODEL") || "llama-3.1-8b-instant";
  const primary = await groqCall(ctx, model, parsed, mat.groqKey);
  if (!primary.text.trim()) throw mesh(502, "groq fallback failed", "groq_failed", "server_error");
  let decision = "fail";
  try {
    const second = await groqCall(ctx, verifier, parsed, mat.groqKey);
    decision = judge(primary.text, second.text, 0) === "agree" ? "agree" : "fail";
  } catch {
    decision = "fail";
  }
  const requestId = hexId("groq_", 6);
  const entry = await append(store, ctx, "groq-fallback", "groq_inference_receipt", {
    schema: "gpumesh.groq_fallback.v1",
    provider: "groq",
    runtime: "groq",
    model,
    worker_id: `groq:${model}`,
    verifier_ids: verifier,
    verifier_decision: decision,
    verification_method: "second_model",
    output_hash: await sha256Text(primary.text),
    prompt_sha256: await sha256Text(canonDumps(parsed.messages)),
    request_id: requestId,
    max_tokens: parsed.max_tokens,
    prompt_tokens: primary.prompt_tokens,
    completion_tokens: primary.completion_tokens,
    duration_ms: primary.duration_ms,
    state: "OBSERVED",
    promotion: "HOLD",
    amount: 0,
    credits: 0,
    settlement_id: `${requestId}:groq`,
    job_id: requestId,
  });
  const job = {
    id: requestId,
    model,
    output_text: primary.text,
    finish_reason: primary.finish_reason,
    prompt_tokens: primary.prompt_tokens,
    completion_tokens: primary.completion_tokens,
    created_at: Date.now() / 1000,
    verdict: decision,
    credits_awarded: 0,
    status: decision === "agree" ? "verified" : "disputed",
    receipt_hash: entry.hash,
  };
  return json(completion(job, entry, {
    worker_id: `groq:${model}`,
    worker_name: "groq-fallback",
    verifier_ids: verifier,
    credit_hold: false,
  }));
}

async function chat(req, store, ctx) {
  const parsed = parseChat(await readJson(req));
  const ip = clientIp(req);
  if (!(await allow(store, `chat:${ip}`, ANON_RPM, 60))) throw mesh(429, "rate limit exceeded", "rpm", "rate_limit_error");
  await sweep(store, clock(ctx));
  const nodes = await store.listNodes();
  const now = clock(ctx);
  const fresh = freshOnline(nodes, now);
  if (!fresh.length) {
    const mat = await material(ctx);
    if (!mat.groqConfigured) throw mesh(503, "no workers online", "no_workers", "server_error");
    if (mat.signingKeyInvalid) {
      throw mesh(503, "The receipt signing seed is not a 32-byte Ed25519 seed.", "signing_key_invalid", "server_error");
    }
    if (!mat.signerConfigured) {
      throw mesh(503, "Receipt signer is not configured.", "signer_not_configured", "server_error");
    }
    return groqFallback(store, ctx, parsed);
  }
  const model = resolveModel(nodes, parsed.model, now);
  if (!model) throw mesh(404, `model ${parsed.model} is not served by any node`, "model_not_found");
  const job = blankJob({
    id: hexId("job_", 6),
    kind: "inference",
    status: "queued",
    model,
    messages: parsed.messages,
    temperature: parsed.temperature,
    max_tokens: parsed.max_tokens,
    client_key: `ip:${ip}`.slice(0, 80),
    created_at: clock(ctx),
    priority: 0,
  });
  await store.insertJob(job);
  const header = req.headers.get("x-gpumesh-wait-seconds");
  let wait = header == null ? 45 : Number(header);
  if (!Number.isFinite(wait)) throw mesh(400, "X-GPUMesh-Wait-Seconds must be a number", "bad_wait");
  wait = Math.max(0, Math.min(wait, 55));
  const deadline = Date.now() + wait * 1000;
  let current = job;
  while (Date.now() < deadline) {
    current = await store.getJob(job.id);
    if (current && ["verified", "disputed", "failed", "rejected"].includes(current.status)) break;
    if (current?.output_text && current.status === "verifying" && Date.now() + (ctx.pollMs || 400) >= deadline) break;
    await new Promise((resolve) => setTimeout(resolve, ctx.pollMs || 400));
  }
  current = await store.getJob(job.id);
  if (!current?.output_text) {
    if (current?.status === "queued") throw mesh(503, "no node accepted the job in time", "no_capacity", "server_error");
    throw mesh(504, `job ${job.id} did not finish before the timeout`, "timeout", "server_error");
  }
  const worker = (await store.listNodes()).find((node) => node.id === current.assigned_node_id);
  const receipt = await receiptForJob(store, current);
  return json(completion(current, receipt, {
    worker_id: current.assigned_node_id,
    worker_name: worker?.name || "",
    verifier_ids: receipt ? verifierOf(receipt) : "",
    credit_hold: worker ? !worker.trusted : true,
  }));
}

function verifierOf(receipt) {
  try {
    const payload = JSON.parse(receipt.payload);
    return String(payload.verifier_ids || "");
  } catch {
    return "";
  }
}

async function receiptForJob(store, job) {
  if (!job.receipt_hash) return null;
  return store.ledgerByHash(job.receipt_hash);
}

async function models(store, ctx) {
  await sweep(store, clock(ctx));
  const online = freshOnline(await store.listNodes(), clock(ctx));
  const ids = new Set();
  for (const node of online) for (const model of node.models || []) ids.add(model.id);
  const data = [...ids].map((id) => ({ id, object: "model", owned_by: "gpumesh" }));
  return json({ object: "list", data });
}

function keyDocument(mat) {
  return {
    scheme: "ed25519",
    algorithm: "ed25519",
    public_key: mat.publicKey,
    public_key_hex: mat.publicKey,
    signer_configured: mat.signerConfigured,
    signing_key_invalid: mat.signingKeyInvalid,
    canon: "v1",
    domain: "GPU-MESH",
    hash: "sha256",
  };
}

async function stats(store, ctx) {
  await sweep(store, clock(ctx));
  const body = await store.stats();
  const mat = await material(ctx);
  return json({
    ok: true,
    ...body,
    signer: mat.publicKey || "",
    groq_configured: mat.groqConfigured,
    signer_configured: mat.signerConfigured,
    coordinator: PUBLIC_COORDINATOR,
    open_invite: OPEN_INVITE,
    invite_required: envGet(ctx.env, "GPU_MESH_INVITE_ONLY") === "1",
    max_tokens: MAX_TOKENS,
    trust_days: 7,
    trust_verified_jobs: TRUST_JOBS,
    ledger: "simulated",
    promotion: "HOLD",
  });
}

export async function handle(req, ctx) {
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: HEADERS });
  const store = ctx.store;
  const path = routeOf(req.url);
  try {
    if (req.method === "GET" && (path === "/" || path === "")) {
      return json({
        ok: true,
        service: "gpu-mesh",
        coordinator: PUBLIC_COORDINATOR,
        health: "/health",
        chat: "/v1/chat/completions",
        open_invite: OPEN_INVITE,
        promotion: "HOLD",
      });
    }
    if (req.method === "GET" && path === "/health") {
      await sweep(store, clock(ctx));
      const body = await store.stats();
      const mat = await material(ctx);
      return json({
        ok: true,
        version: "public-edge",
        nodes_online: body.workers_online,
        workers_online: body.workers_online,
        groq_configured: mat.groqConfigured,
        signer_configured: mat.signerConfigured,
        signing_key_invalid: mat.signingKeyInvalid,
        public_key_hex: mat.publicKey,
        vault_reachable: mat.vaultReachable,
        open_invite: OPEN_INVITE,
        coordinator: PUBLIC_COORDINATOR,
      });
    }
    if (req.method === "GET" && path === "/.well-known/inference-receipt-key.json") {
      return json(keyDocument(await material(ctx)));
    }
    if (req.method === "GET" && path === "/v1/models") return await models(store, ctx);
    if (req.method === "POST" && path === "/v1/chat/completions") return await chat(req, store, ctx);
    if (req.method === "GET" && path.startsWith("/v1/jobs/")) {
      const job = await store.getJob(decodeURIComponent(path.slice("/v1/jobs/".length)));
      if (!job) throw mesh(404, "unknown job", "unknown_job");
      if (!job.output_text) {
        return json({ id: job.id, object: "gpumesh.job", status: job.status, model: job.model, error: job.error, verdict: job.verdict });
      }
      const worker = (await store.listNodes()).find((node) => node.id === job.assigned_node_id);
      const receipt = await receiptForJob(store, job);
      return json(completion(job, receipt, {
        worker_id: job.assigned_node_id,
        worker_name: worker?.name || "",
        verifier_ids: receipt ? verifierOf(receipt) : "",
        credit_hold: worker ? !worker.trusted : true,
      }));
    }
    if (req.method === "GET" && path === "/api/stats") return await stats(store, ctx);
    if (req.method === "GET" && path === "/api/signer") {
      return json(keyDocument(await material(ctx)));
    }
    if (req.method === "GET" && path === "/api/receipts") {
      const url = new URL(req.url);
      const limit = Math.max(1, Math.min(Number(url.searchParams.get("limit") || 20), 50));
      const rows = await store.listLedger(limit);
      return json({
        receipts: rows.map((row) => ({
          seq: row.seq,
          ts: row.ts,
          actor: row.actor,
          kind: row.kind,
          payload: row.payload,
          prev_hash: row.prev_hash,
          hash: row.hash,
          canon: row.canon,
          amount: row.amount,
          signature: row.signature,
          signer: row.signer,
          typed_data: row.typed_data,
        })),
      });
    }
    if (req.method === "POST" && path === "/api/nodes/register") return await register(req, store, ctx);
    if (req.method === "POST" && path === "/api/nodes/heartbeat") return await heartbeat(req, store, ctx);
    if (req.method === "POST" && path === "/api/nodes/jobs/claim") return await claim(req, store, ctx);
    const chunk = path.match(/^\/api\/nodes\/jobs\/([^/]+)\/chunks$/);
    if (req.method === "POST" && chunk) {
      const spec = await readJson(req);
      const node = await authNode(req, store);
      const job = await store.getJob(decodeURIComponent(chunk[1]));
      if (!job || job.assigned_node_id !== node.id) throw mesh(403, "job is not assigned to this node", "not_your_job", "permission_error");
      await store.addChunk(job.id, Number(spec.seq), String(spec.text || "").slice(0, 8000));
      if (job.status === "leased") {
        job.status = "running";
        await store.saveJob(job);
      }
      return json({ ok: true });
    }
    const result = path.match(/^\/api\/nodes\/jobs\/([^/]+)\/result$/);
    if (req.method === "POST" && result) return await submitResult(req, store, ctx, decodeURIComponent(result[1]));
    const fail = path.match(/^\/api\/nodes\/jobs\/([^/]+)\/fail$/);
    if (req.method === "POST" && fail) return await submitFail(req, store, ctx, decodeURIComponent(fail[1]));
    return json({ error: { message: "not found", type: "invalid_request_error", code: "not_found" } }, 404);
  } catch (error) {
    if (error.status) {
      return json({ error: { message: error.message, type: error.errType || "invalid_request_error", code: error.code || null } }, error.status);
    }
    return json({ error: { message: "coordinator error", type: "server_error", code: "internal" } }, 500);
  }
}

export { verifyMeshReceipt };
