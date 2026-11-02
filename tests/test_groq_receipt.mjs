import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { handleGroqTest } from "../supabase/functions/groq-test/handler.mjs";
import {
  GROQ_TEST_MODEL,
  GROQ_TEST_PROMPT,
  PUBLISHED_PUBLIC_KEY,
  canonDumps,
  publicKeyHexFromPrivate,
  signDigest,
  verifyReceipt,
} from "../supabase/functions/groq-test/receipt.mjs";

const siteReceipt = readFileSync(new URL("../site/groq-test/receipt.js", import.meta.url), "utf8");
const fnReceipt = readFileSync(new URL("../supabase/functions/groq-test/receipt.mjs", import.meta.url), "utf8");

test("the published specimen verifies in the browser module", async () => {
  const specimen = JSON.parse(readFileSync(new URL("../site/groq-test/example-receipt.json", import.meta.url), "utf8"));
  const result = await verifyReceipt(specimen, PUBLISHED_PUBLIC_KEY);
  assert.equal(result.ok, true, result.error);
  assert.equal(specimen.signer, PUBLISHED_PUBLIC_KEY);
  assert.equal(specimen.amount, 0);
});

test("the browser verifier is the function receipt module", () => {
  assert.equal(siteReceipt, fnReceipt);
});

test("published public key matches pubkey.json", () => {
  const pub = JSON.parse(readFileSync(new URL("../site/groq-test/pubkey.json", import.meta.url), "utf8"));
  assert.equal(pub.public_key_hex, PUBLISHED_PUBLIC_KEY);
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
    assert.equal(body.max_completion_tokens, 16);
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
    publishedPublicKey: pub,
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
    publishedPublicKey: pub,
  });
  assert.equal(second.status, 200);
  assert.equal(second.body.verification.ok, false);
  assert.equal(second.body.receipt.seq, 2);
  assert.equal(second.body.receipt.prev_hash, first.body.receipt.hash);
  const again = await handleGroqTest(new Request(`https://example.test/groq-test/receipts/${second.body.ledger_receipt_id}`), {
    env: {},
    db,
    publishedPublicKey: pub,
  });
  assert.equal(again.status, 200);
  assert.equal(again.body.receipt.hash, second.body.receipt.hash);
});

test("health is 200 without secrets", async () => {
  const res = await handleGroqTest(new Request("https://example.test/groq-test/health"), {
    env: {},
    db: memoryDb(),
  });
  assert.equal(res.status, 200);
  assert.equal(res.body.ok, true);
  assert.equal(res.body.groq_configured, false);
  assert.equal(res.body.public_key_hex, PUBLISHED_PUBLIC_KEY);
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
