import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import test from "node:test";

import { publicKeyHexFromPrivate } from "../supabase/functions/groq-test/receipt.mjs";

const root = fileURLToPath(new URL("..", import.meta.url));

function run(seed) {
  return spawnSync(process.execPath, ["scripts/check_receipt_signing_key.mjs"], {
    cwd: root,
    env: { ...process.env, INFERENCE_RECEIPT_SIGNING_KEY: seed },
    encoding: "utf8",
  });
}

test("an absent signing seed skips the match check", () => {
  const result = run("");
  assert.equal(result.status, 0);
  assert.match(result.stdout, /absent/);
});

test("a valid signing seed prints only the derived public key", async () => {
  const pair = await crypto.subtle.generateKey({ name: "Ed25519" }, true, ["sign"]);
  const pkcs8 = new Uint8Array(await crypto.subtle.exportKey("pkcs8", pair.privateKey));
  const seed = [...pkcs8.slice(-32)].map((b) => b.toString(16).padStart(2, "0")).join("");
  const derived = await publicKeyHexFromPrivate(seed);
  const result = run(seed);
  assert.equal(result.status, 0);
  assert.match(result.stdout, new RegExp(`derived_public_key=${derived}`));
  assert.equal(result.stdout.includes(seed), false);
  assert.equal(result.stderr.includes(seed), false);
});

test("an invalid signing seed fails without echoing the value", () => {
  const seed = "not-a-seed";
  const result = run(seed);
  assert.equal(result.status, 1);
  assert.match(result.stderr, /not a 32-byte Ed25519 seed/);
  assert.equal(result.stdout.includes(seed), false);
  assert.equal(result.stderr.includes(seed), false);
});
