import { PUBLISHED_PUBLIC_KEY, verifyReceipt } from "./receipt.js";

const status = document.querySelector("#status");
const receiptEl = document.querySelector("#receipt");
const verifyEl = document.querySelector("#verify-result");
const pubkeyEl = document.querySelector("#pubkey");
pubkeyEl.textContent = PUBLISHED_PUBLIC_KEY;

let current = null;

function show(receipt) {
  current = receipt;
  receiptEl.textContent = JSON.stringify(receipt, null, 2);
}

async function verifyCurrent() {
  if (!current) {
    verifyEl.textContent = "There is no receipt to verify.";
    return;
  }
  const entry = current.receipt && current.receipt.hash ? current.receipt : current;
  const result = await verifyReceipt(entry, PUBLISHED_PUBLIC_KEY);
  verifyEl.textContent = result.ok
    ? "Signature matches the published public key."
    : `Signature check failed: ${result.error}`;
}

async function loadSample() {
  const response = await fetch("example-receipt.json");
  if (!response.ok) {
    status.textContent = "The sample receipt is not on this site.";
    return;
  }
  show(await response.json());
  await verifyCurrent();
}

document.querySelector("#verify").addEventListener("click", () => {
  verifyCurrent().catch((error) => {
    verifyEl.textContent = `Signature check failed: ${error.message || error}`;
  });
});

document.querySelector("#run").addEventListener("click", async () => {
  const base = (window.MOLTBOOK_CONFIG && window.MOLTBOOK_CONFIG.groqTestUrl) || "";
  status.textContent = "Calling the bounded Groq test…";
  try {
    const response = await fetch(base, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        apikey: window.MOLTBOOK_CONFIG.publishableKey,
        authorization: `Bearer ${window.MOLTBOOK_CONFIG.publishableKey}`,
      },
      body: "{}",
    });
    const body = await response.json();
    show(body.receipt || body);
    if (!response.ok) {
      status.textContent = body.message || body.error || `The test returned ${response.status}.`;
      verifyEl.textContent = "No signature to check on this error.";
      return;
    }
    status.textContent = body.verification && body.verification.ok
      ? `Observed. Receipt ${body.ledger_receipt_id}. Verification matched.`
      : `Observed. Receipt ${body.ledger_receipt_id}. Verification did not match. Promotion stays HOLD.`;
    await verifyCurrent();
  } catch (error) {
    status.textContent = `The test could not be reached: ${error.message || error}`;
  }
});

loadSample().catch((error) => {
  status.textContent = `The sample receipt did not load: ${error.message || error}`;
});
