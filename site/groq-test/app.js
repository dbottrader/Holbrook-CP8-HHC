import { verifyReceipt } from "./receipt.js";

const status = document.querySelector("#status");
const receiptEl = document.querySelector("#receipt");
const verifyEl = document.querySelector("#verify-result");
const pubkeyEl = document.querySelector("#pubkey");

let current = null;
let livePublicKey = "";

function show(receipt) {
  current = receipt;
  receiptEl.textContent = JSON.stringify(receipt, null, 2);
}

function configBase() {
  return (window.MOLTBOOK_CONFIG && window.MOLTBOOK_CONFIG.groqTestUrl) || "";
}

async function verifyCurrent() {
  if (!current) {
    verifyEl.textContent = "There is no receipt to verify.";
    return;
  }
  const entry = current.receipt && current.receipt.hash ? current.receipt : current;
  const key = livePublicKey || entry.signer || "";
  if (!key) {
    verifyEl.textContent = "No public key is configured, so the signature cannot be checked.";
    return;
  }
  const result = await verifyReceipt(entry, key);
  if (!result.ok) {
    verifyEl.textContent = `Signature check failed: ${result.error}`;
    return;
  }
  if (livePublicKey && entry.signer === livePublicKey) {
    verifyEl.textContent = "Signature matches the live public key.";
    return;
  }
  verifyEl.textContent = livePublicKey
    ? "Signature is valid for the key inside the receipt. It does not match the live public key."
    : "Signature matches the key inside the receipt. The live signer is not configured.";
}

async function loadLiveKey() {
  const base = configBase();
  if (!base) {
    pubkeyEl.textContent = "not configured";
    return;
  }
  try {
    const response = await fetch(`${base}/.well-known/inference-receipt-key.json`, {
      headers: {
        apikey: window.MOLTBOOK_CONFIG.publishableKey,
        authorization: `Bearer ${window.MOLTBOOK_CONFIG.publishableKey}`,
      },
    });
    const body = await response.json();
    livePublicKey = body.public_key_hex || "";
    pubkeyEl.textContent = livePublicKey || "not configured";
    if (!body.signer_configured) {
      status.textContent = "The receipt signer is not configured yet. A live call cannot be signed until Dennis stores the seed.";
    }
  } catch (error) {
    pubkeyEl.textContent = "unavailable";
    status.textContent = `The live public key could not be read: ${error.message || error}`;
  }
}

document.querySelector("#verify").addEventListener("click", () => {
  verifyCurrent().catch((error) => {
    verifyEl.textContent = `Signature check failed: ${error.message || error}`;
  });
});

document.querySelector("#run").addEventListener("click", async () => {
  const base = configBase();
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
    if (body.public_key_hex) {
      livePublicKey = body.public_key_hex;
      pubkeyEl.textContent = livePublicKey;
    }
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

loadLiveKey();
