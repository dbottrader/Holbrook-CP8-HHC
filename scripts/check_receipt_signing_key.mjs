// Compare INFERENCE_RECEIPT_SIGNING_KEY to the published public key.
// Prints only match, mismatch, or absent. Never prints the seed.
import { PUBLISHED_PUBLIC_KEY, publicKeyHexFromPrivate } from "../supabase/functions/groq-test/receipt.mjs";

const seed = (process.env.INFERENCE_RECEIPT_SIGNING_KEY || "").trim();
if (!seed) {
  console.log("INFERENCE_RECEIPT_SIGNING_KEY is absent; skipping the match check.");
  process.exit(0);
}
let derived = "";
try {
  derived = await publicKeyHexFromPrivate(seed);
} catch {
  console.error("INFERENCE_RECEIPT_SIGNING_KEY is not a 32-byte Ed25519 seed.");
  process.exit(1);
}
if (derived !== PUBLISHED_PUBLIC_KEY) {
  console.error("INFERENCE_RECEIPT_SIGNING_KEY does not match the published public key.");
  process.exit(1);
}
console.log("INFERENCE_RECEIPT_SIGNING_KEY matches the published public key.");
