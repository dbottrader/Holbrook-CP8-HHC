/** Read-only Testnet (Base Sepolia) panel for HHCW.

HHCW is a utility credit for verified contribution. Addresses come from
deployments/base-sepolia.json. Figures come from eth_call. Nothing here
sends a transaction.
*/

export const NETWORK_LABEL = "Testnet (Base Sepolia)";
export const CREDIT_LABEL = "utility credit for verified contribution";
export const DEPLOYMENT_PATH = "deployments/base-sepolia.json";
export const DEPLOYMENT_URL =
  "https://raw.githubusercontent.com/dbottrader/Holbrook-CP8-HHC/main/deployments/base-sepolia.json";

export const SELECTORS = {
  balanceOf: "0x70a08231",
  totalSupply: "0x18160ddd",
  anchorCount: "0x34f96c8c",
};

export function padAddress(address) {
  const hex = String(address).toLowerCase().replace(/^0x/, "");
  if (!/^[\da-f]{40}$/.test(hex)) {
    throw new Error("account must be 20 bytes");
  }
  return hex.padStart(64, "0");
}

export function balanceOfData(address) {
  return SELECTORS.balanceOf + padAddress(address);
}

export function decodeWord(hex) {
  const body = String(hex).startsWith("0x") ? String(hex).slice(2) : String(hex);
  if (!/^[\da-fA-F]+$/.test(body) || body.length === 0) {
    throw new Error("eth_call result was empty");
  }
  return BigInt(`0x${body}`);
}

export async function ethCall(rpc, to, data, fetcher = globalThis.fetch) {
  const response = await fetcher(rpc, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      jsonrpc: "2.0",
      id: 1,
      method: "eth_call",
      params: [{ to, data }, "latest"],
    }),
  });
  const payload = await response.json();
  if (payload.error) {
    throw new Error(payload.error.message || "eth_call failed");
  }
  return decodeWord(payload.result);
}

export function panelFacts(record) {
  const token = record.contracts.HHCWorkCredit;
  const settlement = record.contracts.Settlement;
  const proof = record.liveProof;
  return {
    network: NETWORK_LABEL,
    chainId: record.chainId,
    description: CREDIT_LABEL,
    rpc: record.rpc,
    token: token.address,
    tokenName: token.name,
    settlement: settlement.address,
    settleTx: proof.settleTx,
    anchorTx: proof.anchorTx,
    sourcifyToken: record.verification.sourcify.HHCWorkCredit,
    sourcifySettlement: record.verification.sourcify.Settlement,
    accounts: [
      { role: "worker", account: proof.worker },
      { role: "verifier1", account: proof.verifier1 },
      { role: "verifier2", account: proof.verifier2 },
    ],
  };
}

function basescanAddress(address) {
  return `https://sepolia.basescan.org/address/${address}`;
}

function basescanTx(hash) {
  return `https://sepolia.basescan.org/tx/${hash}`;
}

function row(label, html) {
  return `<dt>${label}</dt><dd>${html}</dd>`;
}

export function panelMarkup(facts, live) {
  const balances = (live.balances || [])
    .map((item) => row(item.role, `${item.units.toString()} units · ${item.account}`))
    .join("");
  return [
    `<p>${facts.network}. Chain ${facts.chainId}. HHCW is a ${facts.description}.</p>`,
    "<dl>",
    row("Network", `${facts.network} (${facts.chainId})`),
    row("HHCWorkCredit", `<a href="${basescanAddress(facts.token)}">${facts.token}</a>`),
    row("Settlement", `<a href="${basescanAddress(facts.settlement)}">${facts.settlement}</a>`),
    row("Settle transaction", `<a href="${basescanTx(facts.settleTx)}">${facts.settleTx}</a>`),
    row("Anchor transaction", `<a href="${basescanTx(facts.anchorTx)}">${facts.anchorTx}</a>`),
    row(
      "Sourcify",
      `<a href="${facts.sourcifyToken.url}">HHCWorkCredit ${facts.sourcifyToken.match}</a> · ` +
        `<a href="${facts.sourcifySettlement.url}">Settlement ${facts.sourcifySettlement.match}</a>`,
    ),
    row("Total units", live.totalSupply.toString()),
    row("Anchor count", live.anchorCount.toString()),
    balances,
    "</dl>",
  ].join("");
}

export async function readLive(facts, fetcher = globalThis.fetch) {
  const totalSupply = await ethCall(facts.rpc, facts.token, SELECTORS.totalSupply, fetcher);
  const anchorCount = await ethCall(facts.rpc, facts.settlement, SELECTORS.anchorCount, fetcher);
  const balances = [];
  for (const item of facts.accounts) {
    const units = await ethCall(facts.rpc, facts.token, balanceOfData(item.account), fetcher);
    balances.push({ role: item.role, account: item.account, units });
  }
  return { totalSupply, anchorCount, balances };
}

export async function mountTokenPanel(documentRef, options = {}) {
  const status = documentRef.getElementById("hhcw-status");
  const body = documentRef.getElementById("hhcw-body");
  if (!status || !body) return;
  const fetcher = options.fetcher || globalThis.fetch;
  const deploymentUrl = options.deploymentUrl || DEPLOYMENT_URL;
  try {
    const response = await fetcher(deploymentUrl);
    const record = await response.json();
    const facts = panelFacts(record);
    const live = await readLive(facts, fetcher);
    body.innerHTML = panelMarkup(facts, live);
    status.textContent = `${facts.network}. Live read finished.`;
  } catch (error) {
    status.textContent = `The testnet read did not finish. ${error.message}`;
  }
}

if (typeof document !== "undefined") {
  mountTokenPanel(document);
}
