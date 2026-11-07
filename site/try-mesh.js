import { verifyMeshReceipt } from "./mesh-receipt.js";

const cfg = window.MOLTBOOK_CONFIG || {};
const base = String(cfg.meshBase || "").replace(/\/$/, "");

function el(tag, text) {
  const node = document.createElement(tag);
  if (text != null) node.textContent = text;
  return node;
}

async function getJson(path, options) {
  const response = await fetch(base + path, options);
  const data = await response.json().catch(() => ({}));
  return { response, data };
}

function paintStatus(node, data, error) {
  node.textContent = "";
  if (error) {
    node.append(el("span", error));
    return;
  }
  const online = Number(data.workers_online || 0);
  const verified = Number(data.jobs_verified || 0);
  node.append(
    el("strong", `${online} worker${online === 1 ? "" : "s"} online`),
    document.createTextNode(`. ${verified} verified job${verified === 1 ? "" : "s"}. `),
    el("span", "HHC is a work token and a utility credit for verified contribution. Promotion stays HOLD.")
  );
}

async function refreshStatus() {
  const node = document.querySelector("[data-mesh-status]");
  if (!node || !base) return;
  try {
    const { response, data } = await getJson("/api/stats");
    if (!response.ok) {
      paintStatus(node, null, "The coordinator did not return mesh status.");
      return;
    }
    paintStatus(node, data, null);
  } catch {
    paintStatus(node, null, "The coordinator did not answer.");
  }
}

async function showResult(host, data) {
  host.textContent = "";
  const mesh = data.gpumesh || {};
  const answer = data.choices && data.choices[0] && data.choices[0].message
    ? data.choices[0].message.content
    : "";
  host.append(el("h3", "Answer"));
  host.append(el("p", answer || "(empty)"));
  const who = el("p");
  who.append(el("strong", "Worker: "));
  who.append(document.createTextNode(mesh.worker_name || mesh.worker_id || "unknown"));
  if (mesh.verifier_ids) {
    who.append(el("strong", " Verifier: "));
    who.append(document.createTextNode(String(mesh.verifier_ids)));
  }
  host.append(who);
  const verdict = el("p");
  verdict.append(el("strong", "Verdict: "));
  verdict.append(document.createTextNode(mesh.verdict || mesh.status || ""));
  if (mesh.credit_hold) verdict.append(document.createTextNode(". Credit is in the 7-day / 3-job hold."));
  host.append(verdict);
  const receipt = mesh.receipt;
  const line = el("p");
  if (!receipt) {
    line.textContent = "No signed receipt was attached.";
    host.append(line);
    return;
  }
  const check = await verifyMeshReceipt(receipt);
  let signerNote = "";
  try {
    const signer = await getJson("/api/signer");
    if (signer.response.ok && signer.data.public_key && signer.data.public_key !== receipt.signer) {
      signerNote = " The signer does not match the coordinator key.";
    }
  } catch {
    signerNote = "";
  }
  line.append(el("strong", check.ok ? "Signature checked in this browser." : "Signature check failed."));
  line.append(document.createTextNode(check.ok ? ` Canon v1 ${receipt.kind}.` : ` ${check.error || "mismatch"}.`));
  if (signerNote) line.append(document.createTextNode(signerNote));
  host.append(line);
  const pre = el("pre");
  pre.append(el("code", JSON.stringify(receipt, null, 2)));
  host.append(pre);
}

async function ask(form) {
  const status = document.querySelector("[data-mesh-status]");
  const host = document.querySelector("[data-mesh-result]");
  const prompt = new FormData(form).get("prompt");
  const button = form.querySelector("button");
  if (button) button.disabled = true;
  if (status) status.textContent = "Asking the mesh…";
  if (host) host.textContent = "";
  try {
    let { response, data } = await getJson("/v1/chat/completions", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        model: "auto",
        temperature: 0,
        max_tokens: 128,
        messages: [{ role: "user", content: String(prompt || "") }],
      }),
    });
    if (response.status === 202 && data.poll) {
      const deadline = Date.now() + 60000;
      while (Date.now() < deadline) {
        await new Promise((resolve) => setTimeout(resolve, 1000));
        const next = await getJson(data.poll.startsWith("/") ? data.poll : `/${data.poll}`);
        response = next.response;
        data = next.data;
        if (data.choices || data.gpumesh) break;
      }
    }
    if (!response.ok) {
      const message = data.error && data.error.message ? data.error.message : "The coordinator rejected the prompt.";
      if (status) status.textContent = message;
      return;
    }
    if (host) await showResult(host, data);
    await refreshStatus();
  } catch {
    if (status) status.textContent = "The coordinator did not answer.";
  } finally {
    if (button) button.disabled = false;
  }
}

const form = document.querySelector("[data-mesh-try]");
if (form) {
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    ask(form);
  });
}
refreshStatus();
setInterval(refreshStatus, 15000);
