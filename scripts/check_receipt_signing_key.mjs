// Validate INFERENCE_RECEIPT_SIGNING_KEY when it is present.
// Prints only absent, invalid, or the derived public key. Never prints the seed.
import { publicKeyHexFromPrivate } from "../supabase/functions/groq-test/receipt.mjs";

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
console.log(`derived_public_key=${derived}`);
