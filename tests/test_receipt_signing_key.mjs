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

test("a different signing seed fails without echoing the seed", async () => {
  const pair = await crypto.subtle.generateKey({ name: "Ed25519" }, true, ["sign"]);
  const pkcs8 = new Uint8Array(await crypto.subtle.exportKey("pkcs8", pair.privateKey));
  const seed = [...pkcs8.slice(-32)].map((b) => b.toString(16).padStart(2, "0")).join("");
  const derived = await publicKeyHexFromPrivate(seed);
  assert.equal(derived.length, 64);
  const result = run(seed);
  assert.equal(result.status, 1);
  assert.match(result.stderr, /does not match the published public key/);
  assert.match(result.stderr, new RegExp(`derived_public_key=${derived}`));
  assert.equal(result.stdout.includes(seed), false);
  assert.equal(result.stderr.includes(seed), false);
});
