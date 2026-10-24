const page = document.body.dataset.page || "dashboard";
const banner = document.querySelector("#banner");
const live = document.querySelector("#live");
let samples = [];

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[ch]));
}

function ago(sec) {
  if (sec == null) return "never";
  if (sec < 5) return "just now";
  if (sec < 60) return `${sec}s ago`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  return `${Math.floor(min / 60)}h ago`;
}

function when(ms) {
  if (!ms) return "";
  const date = new Date(ms);
  return Number.isNaN(date.getTime()) ? "" : date.toLocaleString();
}

function pill(status) {
  const key = String(status || "unknown").toLowerCase();
  return `<span class="pill ${esc(key)}">${esc(key)}</span>`;
}

function setLive(ok) {
  live.classList.toggle("on", ok);
  live.classList.toggle("bad", !ok);
  const label = document.querySelector("#live-label");
  if (label) label.textContent = ok ? "live" : "coordinator unreachable";
}

function showError(message) {
  banner.textContent = message;
  banner.classList.add("show");
}

function clearError() {
  banner.classList.remove("show");
}

function renderDashboard(data) {
  const tiles = [
    ["Nodes online", data.online_nodes],
    ["GPUs", data.gpu_count_online],
    ["VRAM online", data.vram_mb_online ? `${data.vram_mb_online} MB` : "0"],
    ["Jobs / sec", data.jobs_per_sec],
    ["Queue", data.queue_depth],
    ["Ledger", data.ledger.length],
    ["Tokens served", (data.metering && data.metering.completion_tokens) || 0],
  ];
  document.querySelector("#stats").innerHTML = tiles
    .map(([label, value]) => `<div class="stat"><span>${esc(label)}</span><strong>${esc(value)}</strong></div>`)
    .join("");

  const models = data.models || [];
  const modelBox = document.querySelector("#models");
  if (!models.length) {
    modelBox.innerHTML = `<div class="empty">No model is advertised. A node publishes what it has loaded — Ollama, vLLM, or the CPU fallback.</div>`;
  } else {
    modelBox.innerHTML = `<ul class="model-list">${models
      .map((model) => {
        const meta = model.gpumesh || {};
        return `<li><strong class="mono">${esc(model.id)}</strong><span>${esc(meta.online_nodes)} online · ${esc((meta.backends || []).join(", ") || "unknown")}</span>${
          meta.notice ? `<div class="notice">${esc(meta.notice)}</div>` : ""
        }</li>`;
      })
      .join("")}</ul>`;
  }

  const people = data.top_contributors || [];
  const max = Math.max(1, ...people.map((node) => node.credits || 0));
  const contrib = document.querySelector("#contributors");
  if (!people.length) {
    contrib.innerHTML = `<div class="empty">No contributors yet. The first node to finish a job gets the first receipt.</div>`;
  } else {
    contrib.innerHTML = `<div class="bars">${people
      .map((node) => {
        const width = Math.round(((node.credits || 0) / max) * 100);
        return `<div class="bar-row"><span>${esc(node.name)}</span><div class="track"><span style="width:${width}%"></span></div><span class="mono">${esc(node.credits)}</span></div>`;
      })
      .join("")}</div>`;
  }

  renderJobTable(document.querySelector("#jobs"), data.recent_jobs || []);
  const modelName = models[0] ? models[0].id : "mock-tiny";
  const example = document.querySelector("#try-api");
  if (example) {
    example.textContent = `curl -s ${location.origin}/v1/chat/completions \\\n  -H 'content-type: application/json' \\\n  -d '{"model":${JSON.stringify(modelName)},"messages":[{"role":"user","content":"Say hello in one sentence."}],"temperature":0}'`;
  }
}

function renderNodes(data) {
  const host = document.querySelector("#node-table");
  if (!host) return;
  const rows = data.nodes || [];
  if (!rows.length) {
    host.innerHTML = `<div class="empty">No nodes have registered. The contribute page has a one-line installer for a Linux box.</div>`;
    return;
  }
  host.innerHTML = `<div class="scroll"><table><thead><tr><th>Name</th><th>Status</th><th>GPU</th><th>VRAM</th><th>Backend</th><th>Models</th><th>Kudos</th><th>Escrow</th><th>Suspicion</th><th>Reputation</th><th>Seen</th></tr></thead><tbody>${rows
    .map(
      (node) => `<tr>
        <td>${esc(node.name)}<div class="mono">${esc(node.node_id)}</div></td>
        <td>${pill(node.status)}</td>
        <td>${esc(node.gpu)}${node.gpu_count ? ` × ${esc(node.gpu_count)}` : ""}</td>
        <td class="mono">${esc(node.vram_mb)}</td>
        <td>${esc(node.backend)}</td>
        <td class="mono">${esc((node.models || []).join(", ") || "—")}</td>
        <td class="mono">${esc(node.credits)}</td>
        <td class="mono">${esc(node.escrow_credits || 0)}${node.trusted ? "" : " · held"}</td>
        <td class="mono">${esc(node.suspicion || 0)}</td>
        <td class="mono">${esc(node.reputation)}${node.strikes ? ` · ${esc(node.strikes)} strikes` : ""}</td>
        <td>${esc(ago(node.last_seen_sec))}</td>
      </tr>`,
    )
    .join("")}</tbody></table></div>`;
}

function renderJobTable(host, jobs) {
  if (!host) return;
  if (!jobs.length) {
    host.innerHTML = `<div class="empty">No jobs yet. The public API is OpenAI-shaped: POST /v1/chat/completions.</div>`;
    return;
  }
  host.innerHTML = `<div class="scroll"><table><thead><tr><th>Job</th><th>Kind</th><th>Phase</th><th>Model</th><th>Node</th><th>Verdict</th><th>ms</th></tr></thead><tbody>${jobs
    .map(
      (job) => `<tr>
        <td class="mono">${esc(job.id)}</td>
        <td>${esc(job.kind)}</td>
        <td>${pill(job.phase || job.status)}</td>
        <td class="mono">${esc(job.model)}</td>
        <td>${esc(job.node_name || job.node_id || "—")}</td>
        <td>${job.verdict ? pill(job.verdict) : "—"}</td>
        <td class="mono">${esc(job.duration_ms || "")}</td>
      </tr>`,
    )
    .join("")}</tbody></table></div>`;
}

let openReceiptSeq = null;

function receiptDocument(entry) {
  let payload = entry.payload_obj;
  if (payload == null && typeof entry.payload === "string") {
    try {
      payload = JSON.parse(entry.payload);
    } catch {
      payload = entry.payload;
    }
  }
  return {
    seq: entry.seq,
    ts: entry.ts,
    actor: entry.actor,
    kind: entry.kind,
    amount: entry.amount,
    payload,
    prev_hash: entry.prev_hash,
    hash: entry.hash,
    canon: entry.canon,
    signature: entry.signature,
    signer: entry.signer,
  };
}

function closeReceiptRows(host) {
  host.querySelectorAll("tr.clicky").forEach((item) => item.setAttribute("aria-expanded", "false"));
  host.querySelectorAll(".detail-row").forEach((item) => item.classList.remove("is-open"));
}

function paintReceiptDetail(row, entry) {
  const detail = row.nextElementSibling;
  if (!detail) return;
  detail.classList.add("is-open");
  row.setAttribute("aria-expanded", "true");
  detail.querySelector("pre").textContent = JSON.stringify(receiptDocument(entry), null, 2);
}

function toggleReceipt(host, receipts, row) {
  const entry = receipts[Number(row.dataset.index)];
  if (!entry) return;
  const detail = row.nextElementSibling;
  const wasOpen = detail && detail.classList.contains("is-open");
  closeReceiptRows(host);
  if (wasOpen) {
    openReceiptSeq = null;
    return;
  }
  openReceiptSeq = entry.seq;
  paintReceiptDetail(row, entry);
}

function renderReceipts(receipts) {
  const host = document.querySelector("#receipt-table");
  if (!host) return;
  if (!receipts.length) {
    host.innerHTML = `<div class="empty">The ledger is empty.</div>`;
    host.dataset.fingerprint = "";
    return;
  }
  const fingerprint = receipts.map((entry) => `${entry.seq}:${entry.hash}`).join(",");
  if (host.dataset.fingerprint === fingerprint && host.querySelector("tr.clicky")) return;
  host.dataset.fingerprint = fingerprint;
  host.innerHTML = `<div class="scroll"><table><thead><tr><th>Seq</th><th>When</th><th>Kind</th><th>Actor</th><th>Credits</th><th>Hash</th></tr></thead><tbody>${receipts
    .map((entry, index) => {
      const payload = entry.payload_obj || {};
      const credits = payload.credits ?? entry.amount ?? "";
      return `<tr class="clicky" data-index="${index}" tabindex="0" aria-expanded="false">
        <td class="mono">${esc(entry.seq)}</td>
        <td>${esc(when(entry.ts))}</td>
        <td>${esc(entry.kind)}</td>
        <td class="mono">${esc(entry.actor)}</td>
        <td class="mono">${esc(credits)}</td>
        <td class="mono">${esc(String(entry.hash).slice(0, 16))}…</td>
      </tr>
      <tr class="detail-row"><td colspan="6"><pre class="detail"></pre></td></tr>`;
    })
    .join("")}</tbody></table></div>`;
  host.querySelectorAll("tr.clicky").forEach((row) => {
    row.addEventListener("click", () => toggleReceipt(host, receipts, row));
    row.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        toggleReceipt(host, receipts, row);
      }
    });
  });
  if (openReceiptSeq != null) {
    const row = [...host.querySelectorAll("tr.clicky")].find((item) => {
      const entry = receipts[Number(item.dataset.index)];
      return entry && entry.seq === openReceiptSeq;
    });
    if (row) paintReceiptDetail(row, receipts[Number(row.dataset.index)]);
    else openReceiptSeq = null;
  }
}

async function poll() {
  try {
    const response = await fetch("/api/stats");
    if (!response.ok) throw new Error(`stats ${response.status}`);
    const data = await response.json();
    clearError();
    setLive(true);
    samples.push(data.jobs_completed);
    if (samples.length > 30) samples = samples.slice(-30);
    if (page === "dashboard") renderDashboard(data);
    if (page === "nodes") renderNodes(data);
    if (page === "receipts") {
      const ledger = await fetch("/api/receipts?limit=40");
      const body = await ledger.json();
      renderReceipts(body.receipts || []);
      const tip = document.querySelector("#tip");
      tip.textContent = data.ledger.ok
        ? `Tip checks out. ${data.ledger.length} entries. ${data.ledger.tip}`
        : `Tip check failed.`;
    }
    const count = document.querySelector("#online-count");
    if (count) count.textContent = String(data.online_nodes);
  } catch (error) {
    setLive(false);
    showError(`The board could not read the coordinator (${error.message}).`);
  }
}

function fillContribute() {
  const origin = location.origin;
  const install = `curl -fsSL ${origin}/install.sh | sudo bash -s -- --name my-rig --backend ollama --invite YOUR_INVITE`;
  const cpu = `curl -fsSL ${origin}/install.sh | sudo bash -s -- --name my-rig --allow-cpu`;
  const llamacpp = `curl -fsSL ${origin}/install.sh | sudo bash -s -- --name my-rig --backend llamacpp --invite YOUR_INVITE`;
  const installEl = document.querySelector("#install-cmd");
  const cpuEl = document.querySelector("#cpu-cmd");
  const llamacppEl = document.querySelector("#llamacpp-cmd");
  if (installEl) installEl.textContent = install;
  if (cpuEl) cpuEl.textContent = cpu;
  if (llamacppEl) llamacppEl.textContent = llamacpp;
  document.querySelectorAll("[data-copy]").forEach((button) => {
    button.addEventListener("click", async () => {
      const target = document.querySelector(button.dataset.copy);
      const text = target ? target.textContent : "";
      try {
        await navigator.clipboard.writeText(text);
        button.textContent = "Copied";
      } catch {
        button.textContent = "Select the command";
      }
      setTimeout(() => {
        button.textContent = "Copy";
      }, 1600);
    });
  });
}

const replay = document.querySelector("#replay");
if (replay) {
  replay.addEventListener("click", async () => {
    const out = document.querySelector("#replay-out");
    out.textContent = "Replaying…";
    const response = await fetch("/api/ledger/verify");
    const data = await response.json();
    out.textContent = data.ok
      ? `Chain replays clean. ${data.length} entries. Tip ${data.tip}.`
      : `Replay failed: ${(data.errors || []).join("; ") || response.status}`;
  });
}

fillContribute();
poll();
setInterval(poll, 2000);
