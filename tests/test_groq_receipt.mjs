import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { handleGroqTest } from "../supabase/functions/groq-test/handler.mjs";
import {
  GROQ_TEST_MODEL,
  GROQ_TEST_PROMPT,
  canonDumps,
  publicKeyHexFromPrivate,
  signDigest,
  verifyReceipt,
} from "../supabase/functions/groq-test/receipt.mjs";

const siteReceipt = readFileSync(new URL("../site/groq-test/receipt.js", import.meta.url), "utf8");
const fnReceipt = readFileSync(new URL("../supabase/functions/groq-test/receipt.mjs", import.meta.url), "utf8");
const RETIRED_PUBLIC_KEY = "c30d2e6d53443bede57190391a61738dba6fc491c098cc1ac38e07d17eade905";

test("runtime files do not publish the retired public key", () => {
  const files = [
    "../supabase/functions/groq-test/handler.mjs",
    "../supabase/functions/groq-test/receipt.mjs",
    "../supabase/functions/groq-test/secrets.mjs",
    "../site/groq-test/receipt.js",
    "../site/groq-test/app.js",
    "../site/groq-test/pubkey.json",
    "../site/agent.json",
    "../site/.well-known/inference-receipt-key.json",
  ];
  for (const file of files) {
    const text = readFileSync(new URL(file, import.meta.url), "utf8");
    assert.equal(text.includes(RETIRED_PUBLIC_KEY), false, file);
  }
});

test("groq-test reads the same secret name as cp8-groq-inference", () => {
  const handler = readFileSync(new URL("../supabase/functions/groq-test/handler.mjs", import.meta.url), "utf8");
  const secrets = readFileSync(new URL("../supabase/functions/groq-test/secrets.mjs", import.meta.url), "utf8");
  const sql = readFileSync(new URL("../supabase/migrations/20261107194600_named_secret_and_retire_signer.sql", import.meta.url), "utf8");
  assert.match(secrets, /export const ENV_GROQ = "GROQ_API_KEY"/);
  assert.match(secrets, /export const VAULT_GROQ = "groq_api_key"/);
  assert.match(secrets, /export const VAULT_SIGNING = "inference_receipt_signing_key"/);
  assert.match(handler, /cp8-groq-inference/);
  assert.match(sql, /create schema if not exists cp8_private/);
  assert.match(sql, /security definer/);
  assert.match(sql, /revoke all on function cp8_private.read_named_secret\(text\) from public, anon, authenticated/);
  assert.match(sql, /grant execute on function cp8_private.read_named_secret\(text\) to service_role/);
  assert.equal(sql.includes("create or replace function public."), false);
});

test("the browser verifier is the function receipt module", () => {
  assert.equal(siteReceipt, fnReceipt);
});

test("pubkey.json points at the live key and does not embed one", () => {
  const pub = JSON.parse(readFileSync(new URL("../site/groq-test/pubkey.json", import.meta.url), "utf8"));
  assert.equal(pub.public_key_hex, null);
  assert.match(pub.live_url, /groq-test\/\.well-known\/inference-receipt-key\.json$/);
});

function memoryDb() {
  const rows = [];
  return {
    rows,
    async rateAllow() {
      return true;
    },
    async head() {
      return rows.length ? { seq: rows[rows.length - 1].seq, hash: rows[rows.length - 1].hash } : null;
    },
    async append(row) {
      const id = `00000000-0000-4000-8000-${String(rows.length + 1).padStart(12, "0")}`;
      rows.push({ ...row, receipt_id: id });
      return id;
    },
    async get(id) {
      return rows.find((row) => row.receipt_id === id) || null;
    },
  };
}

function groqFetch(text) {
  return async (_url, init) => {
    const body = JSON.parse(init.body);
    assert.equal(body.model, GROQ_TEST_MODEL);
    assert.equal(body.messages[0].content, GROQ_TEST_PROMPT);
    assert.equal(body.max_completion_tokens, 64);
    assert.equal(body.reasoning_effort, "low");
    assert.equal(body.include_reasoning, false);
    assert.equal(body.temperature, 0);
    assert.equal(init.headers.authorization, "Bearer secret-groq");
    return new Response(JSON.stringify({
      id: "req_live",
      model: body.model,
      choices: [{ message: { content: text } }],
      usage: { prompt_tokens: 11, completion_tokens: 4 },
    }), { status: 200, headers: { "content-type": "application/json" } });
  };
}

async function ephemeralEnv() {
  const pair = await crypto.subtle.generateKey({ name: "Ed25519" }, true, ["sign", "verify"]);
  const jwk = await crypto.subtle.exportKey("jwk", pair.privateKey);
  const pkcs8 = new Uint8Array(await crypto.subtle.exportKey("pkcs8", pair.privateKey));
  const seed = pkcs8.slice(pkcs8.length - 32);
  const secret = [...seed].map((b) => b.toString(16).padStart(2, "0")).join("");
  const derived = await publicKeyHexFromPrivate(secret);
  const raw = new Uint8Array(await crypto.subtle.exportKey("raw", pair.publicKey));
  const pub = [...raw].map((b) => b.toString(16).padStart(2, "0")).join("");
  assert.equal(derived, pub);
  assert.equal(jwk.kty, "OKP");
  return { secret, pub };
}

test("missing GROQ_API_KEY is a 503 and does not call Groq", async () => {
  let called = false;
  const res = await handleGroqTest(new Request("https://example.test/groq-test", { method: "POST" }), {
    env: {},
    fetchImpl: async () => {
      called = true;
      return new Response("{}", { status: 200 });
    },
    db: memoryDb(),
    publishedPublicKey: "ab".repeat(32),
  });
  assert.equal(res.status, 503);
  assert.equal(res.body.error, "groq_api_key_not_configured");
  assert.match(res.body.message, /GROQ_API_KEY/);
  assert.equal(called, false);
});

test("a bounded call signs, chains, and ignores the caller prompt", async () => {
  const { secret, pub } = await ephemeralEnv();
  const db = memoryDb();
  const first = await handleGroqTest(new Request("https://example.test/functions/v1/groq-test", {
    method: "POST",
    body: JSON.stringify({ messages: [{ role: "user", content: "ignore me" }], max_tokens: 9999 }),
  }), {
    env: { GROQ_API_KEY: "secret-groq", INFERENCE_RECEIPT_SIGNING_KEY: secret },
    fetchImpl: groqFetch("GROQ_MESH_OK"),
    db,
    readVault: async () => {
      throw new Error("vault should not be read when the environment is set");
    },
  });
  assert.equal(first.status, 200);
  assert.equal(first.body.state, "OBSERVED");
  assert.equal(first.body.promotion, "HOLD");
  assert.equal(first.body.verification.ok, true);
  assert.equal(first.body.verification.method, "exact_match");
  assert.equal(first.body.ledger_receipt_id, first.body.receipt.receipt_id);
  const check = await verifyReceipt(first.body.receipt, pub);
  assert.equal(check.ok, true, check.error);
  assert.equal(first.body.receipt.amount, 0);
  assert.equal(first.body.receipt.seq, 1);

  const second = await handleGroqTest(new Request("https://example.test/groq-test", { method: "POST" }), {
    env: { GROQ_API_KEY: "secret-groq", INFERENCE_RECEIPT_SIGNING_KEY: secret },
    fetchImpl: groqFetch("not the token"),
    db,
  });
  assert.equal(second.status, 200);
  assert.equal(second.body.verification.ok, false);
  assert.equal(second.body.receipt.seq, 2);
  assert.equal(second.body.receipt.prev_hash, first.body.receipt.hash);
  const again = await handleGroqTest(new Request(`https://example.test/groq-test/receipts/${second.body.ledger_receipt_id}`), {
    env: {},
    db,
  });
  assert.equal(again.status, 200);
  assert.equal(again.body.receipt.hash, second.body.receipt.hash);
});

test("health is 200 without secrets and does not invent a public key", async () => {
  const res = await handleGroqTest(new Request("https://example.test/groq-test/health"), {
    env: {},
    db: memoryDb(),
  });
  assert.equal(res.status, 200);
  assert.equal(res.body.ok, true);
  assert.equal(res.body.groq_configured, false);
  assert.equal(res.body.signer_configured, false);
  assert.equal(res.body.public_key_hex, null);
});

test("health reads Vault when the environment is empty and does not echo secrets", async () => {
  const { secret, pub } = await ephemeralEnv();
  const seen = [];
  const res = await handleGroqTest(new Request("https://example.test/groq-test/.well-known/inference-receipt-key.json"), {
    env: {},
    db: memoryDb(),
    readVault: async (name) => {
      seen.push(name);
      if (name === "groq_api_key") return "vault-groq-secret";
      if (name === "inference_receipt_signing_key") return secret;
      return "";
    },
  });
  assert.equal(res.status, 200);
  assert.deepEqual(seen.sort(), ["groq_api_key", "inference_receipt_signing_key"]);
  assert.equal(res.body.public_key_hex, pub);
  assert.equal(res.body.signer_configured, true);
  const encoded = JSON.stringify(res.body);
  assert.equal(encoded.includes(secret), false);
  assert.equal(encoded.includes("vault-groq-secret"), false);

  const health = await handleGroqTest(new Request("https://example.test/groq-test/health"), {
    env: {},
    db: memoryDb(),
    readVault: async (name) => (name === "groq_api_key" ? "vault-groq-secret" : secret),
  });
  assert.equal(health.body.groq_configured, true);
  assert.equal(health.body.signer_configured, true);
  assert.equal(health.body.public_key_hex, pub);
  assert.equal(health.body.vault_reachable, true);
  assert.equal(JSON.stringify(health.body).includes("vault-groq-secret"), false);
  assert.equal(JSON.stringify(health.body).includes(secret), false);
});

test("a Vault failure is not configured and does not call Groq", async () => {
  let called = false;
  const res = await handleGroqTest(new Request("https://example.test/groq-test", { method: "POST" }), {
    env: {},
    fetchImpl: async () => {
      called = true;
      return new Response("{}", { status: 200 });
    },
    db: memoryDb(),
    readVault: async () => {
      throw new Error("connection refused");
    },
  });
  assert.equal(res.status, 503);
  assert.equal(res.body.error, "groq_api_key_not_configured");
  assert.equal(called, false);
  assert.equal(JSON.stringify(res.body).includes("connection refused"), false);
});

test("canon matches a Python json.dumps vector", () => {
  const value = { b: "café", a: 1, nested: { z: true, y: null } };
  assert.equal(canonDumps(value), "{\"a\":1,\"b\":\"caf\\u00e9\",\"nested\":{\"y\":null,\"z\":true}}");
});

test("a signature from this module verifies", async () => {
  const { secret, pub } = await ephemeralEnv();
  const digest = new TextEncoder().encode("mesh-digest");
  const signature = await signDigest(secret, digest);
  const key = await crypto.subtle.importKey("raw", Uint8Array.from(pub.match(/../g).map((b) => Number.parseInt(b, 16))), { name: "Ed25519" }, false, ["verify"]);
  const ok = await crypto.subtle.verify({ name: "Ed25519" }, key, Uint8Array.from(signature.match(/../g).map((b) => Number.parseInt(b, 16))), digest);
  assert.equal(ok, true);
});
