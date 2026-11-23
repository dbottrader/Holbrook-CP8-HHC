import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

import {
  CREDIT_LABEL,
  DEPLOYMENT_PATH,
  DEPLOYMENT_URL,
  NETWORK_LABEL,
  SELECTORS,
  balanceOfData,
  decodeWord,
  ethCall,
  mountTokenPanel,
  panelFacts,
  panelMarkup,
  readLive,
} from "./token-panel.js";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const record = JSON.parse(readFileSync(resolve(ROOT, DEPLOYMENT_PATH), "utf8"));
const FORBIDDEN = /\b(sale|price|returns|investment|listing|launch)\b|\$HHC|clanker|dex/i;

test("facts come from deployments/base-sepolia.json", () => {
  const facts = panelFacts(record);
  assert.equal(facts.network, NETWORK_LABEL);
  assert.equal(facts.network, "Testnet (Base Sepolia)");
  assert.equal(facts.chainId, 84532);
  assert.equal(facts.description, CREDIT_LABEL);
  assert.equal(facts.token, record.contracts.HHCWorkCredit.address);
  assert.equal(facts.settlement, record.contracts.Settlement.address);
  assert.equal(facts.settleTx, record.liveProof.settleTx);
  assert.equal(facts.anchorTx, record.liveProof.anchorTx);
  assert.equal(facts.sourcifyToken.match, "exact_match");
  assert.equal(DEPLOYMENT_URL.endsWith(DEPLOYMENT_PATH), true);
});

test("panel markup names the testnet and links the recorded transactions", () => {
  const facts = panelFacts(record);
  const html = panelMarkup(facts, {
    totalSupply: 1000n,
    anchorCount: 1n,
    balances: facts.accounts.map((item) => ({ ...item, units: 0n })),
  });
  assert.match(html, /Testnet \(Base Sepolia\)/);
  assert.match(html, /utility credit for verified contribution/);
  assert.match(html, new RegExp(record.contracts.HHCWorkCredit.address));
  assert.match(html, new RegExp(record.contracts.Settlement.address));
  assert.match(html, new RegExp(record.liveProof.settleTx));
  assert.match(html, new RegExp(record.liveProof.anchorTx));
  assert.match(html, /sepolia\.basescan\.org/);
  assert.match(html, /repo\.sourcify\.dev/);
  assert.match(html, /exact_match/);
  assert.equal(FORBIDDEN.test(html), false);
  assert.equal(FORBIDDEN.test(readFileSync(new URL("./token-panel.js", import.meta.url), "utf8")), false);
});

test("balanceOf calldata pads the account", () => {
  const data = balanceOfData(record.liveProof.worker);
  assert.equal(data.startsWith(SELECTORS.balanceOf), true);
  assert.equal(data.length, 2 + 8 + 64);
  assert.equal(decodeWord("0x2a"), 42n);
});

test("a mocked eth_call is what the panel renders", async () => {
  const facts = panelFacts(record);
  const calls = [];
  const fetcher = async (url, options) => {
    if (String(url).includes(DEPLOYMENT_PATH) || String(url) === DEPLOYMENT_URL) {
      return { json: async () => record };
    }
    const body = JSON.parse(options.body);
    calls.push(body.params[0].data);
    const word = body.params[0].data.startsWith(SELECTORS.anchorCount) ? "0x1" : "0x64";
    return { json: async () => ({ result: word }) };
  };
  const live = await readLive(facts, fetcher);
  assert.equal(live.totalSupply, 100n);
  assert.equal(live.anchorCount, 1n);
  assert.equal(live.balances.length, 3);
  assert.equal(calls[0], SELECTORS.totalSupply);
  const body = { innerHTML: "" };
  const status = { textContent: "" };
  const root = {
    getElementById(id) {
      if (id === "hhcw-status") return status;
      if (id === "hhcw-body") return body;
      return null;
    },
  };
  await mountTokenPanel(root, { fetcher, deploymentUrl: DEPLOYMENT_URL });
  assert.match(body.innerHTML, /100/);
  assert.match(status.textContent, /Testnet \(Base Sepolia\)/);
});

test("live Base Sepolia eth_call reads anchorCount", async () => {
  const facts = panelFacts(record);
  const count = await ethCall(facts.rpc, facts.settlement, SELECTORS.anchorCount);
  assert.equal(typeof count, "bigint");
  assert.equal(count >= 1n, true);
});
