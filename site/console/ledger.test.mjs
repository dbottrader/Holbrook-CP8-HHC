import assert from "node:assert/strict";
import { createRequire } from "node:module";
import test from "node:test";

const require = createRequire(import.meta.url);
const ledger = require("./ledger.js");

test("3000 minor splits 2700 / 150 / 150", () => {
  const split = ledger.splitPrice(3000);
  assert.equal(split.workerMinor, 2700n);
  assert.equal(split.poolMinor, 300n);
  const shares = ledger.verifierShares(split.poolMinor, ["agent:b", "agent:a"]);
  assert.deepEqual(shares.map((row) => [row.account, row.amountMinor]), [
    ["agent:a", 150n],
    ["agent:b", 150n]
  ]);
  assert.equal(split.workerMinor + shares[0].amountMinor + shares[1].amountMinor, 3000n);
});

test("1001 minor leaves the remainder with the last verifier id", () => {
  const split = ledger.splitPrice(1001);
  assert.equal(split.workerMinor, 900n);
  assert.equal(split.poolMinor, 101n);
  const shares = ledger.verifierShares(101, ["human:m", "agent:q"]);
  assert.equal(shares[0].amountMinor, 50n);
  assert.equal(shares[0].remainderMinor, 0n);
  assert.equal(shares[1].account, "human:m");
  assert.equal(shares[1].amountMinor, 51n);
  assert.equal(shares[1].remainderMinor, 1n);
  assert.equal(900n + 50n + 51n, 1001n);
});

test("display uses three decimal places, 1000 minor = 1 HHC-SIM", () => {
  assert.equal(ledger.formatMinor(0), "0.000");
  assert.equal(ledger.formatMinor(7), "0.007");
  assert.equal(ledger.formatMinor(1000), "1.000");
  assert.equal(ledger.formatMinor(1001), "1.001");
  assert.equal(ledger.formatMinor(-15), "-0.015");
  assert.equal(ledger.formatMinor("2700"), "2.700");
});

test("status buckets match the public board", () => {
  assert.equal(ledger.bucketFor("OPEN"), "open");
  assert.equal(ledger.bucketFor("DRAFT"), "open");
  assert.equal(ledger.bucketFor("CLAIMED"), "claimed");
  assert.equal(ledger.bucketFor("SUBMITTED"), "verification");
  assert.equal(ledger.bucketFor("VERIFYING"), "verification");
  assert.equal(ledger.bucketFor("VERIFIED"), "verification");
  assert.equal(ledger.bucketFor("DISPUTED"), "verification");
  assert.equal(ledger.bucketFor("SETTLED"), "settled");
  assert.equal(ledger.bucketFor("CANCELLED"), "refunded");
  assert.equal(ledger.bucketFor("EXPIRED"), "refunded");
  assert.equal(ledger.bucketFor("REJECTED"), "refunded");
  assert.equal(ledger.bucketLabel("verification"), "In verification");
});

test("a settled 1001 minor bounty conserves and orders verifier shares", () => {
  const bounty = {
    bounty_id: "b1",
    price_minor: 1001,
    worker_minor: 900,
    pool_minor: 101,
    status: "SETTLED"
  };
  const transfers = [
    { bounty_id: "b1", kind: "pending", debit_account: "human:h", credit_account: "escrow", amount_minor: 1001, code: "bounty_hold" },
    { bounty_id: "b1", kind: "post", debit_account: "escrow", credit_account: "agent:w", amount_minor: 900, code: "worker_payout" },
    { bounty_id: "b1", kind: "post", debit_account: "escrow", credit_account: "agent:a", amount_minor: 50, code: "verifier_payout" },
    { bounty_id: "b1", kind: "post", debit_account: "escrow", credit_account: "human:m", amount_minor: 51, code: "verifier_payout" }
  ];
  const report = ledger.settlementReport(bounty, transfers);
  assert.equal(report.kind, "settled");
  assert.equal(report.ok, true);
  const balances = ledger.balancesFromTransfers(transfers);
  const byAccount = Object.fromEntries(balances.map((row) => [row.account, row]));
  assert.equal(byAccount["human:h"].net, -1001n);
  assert.equal(byAccount["human:h"].settledIn, 0n);
  assert.equal(byAccount["agent:w"].settledIn, 900n);
  assert.equal(byAccount["agent:a"].settledIn, 50n);
  assert.equal(byAccount["human:m"].settledIn, 51n);
  assert.equal(byAccount.escrow.net, 0n);
});

test("a voided bounty refunds the poster and settles nothing", () => {
  const bounty = { bounty_id: "b2", price_minor: 4000, worker_minor: 3600, pool_minor: 400, status: "REJECTED" };
  const transfers = [
    { bounty_id: "b2", kind: "pending", debit_account: "human:h", credit_account: "escrow", amount_minor: 4000, code: "bounty_hold" },
    { bounty_id: "b2", kind: "void", debit_account: "escrow", credit_account: "human:h", amount_minor: 4000, code: "refund" }
  ];
  const report = ledger.settlementReport(bounty, transfers);
  assert.equal(report.kind, "refund");
  assert.equal(report.ok, true);
  const balances = ledger.balancesFromTransfers(transfers);
  const poster = balances.find((row) => row.account === "human:h");
  const escrow = balances.find((row) => row.account === "escrow");
  assert.equal(poster.net, 0n);
  assert.equal(poster.refundedIn, 4000n);
  assert.equal(poster.settledIn, 0n);
  assert.equal(escrow.net, 0n);
});

test("empty public legs produce no balances", () => {
  assert.deepEqual(ledger.balancesFromTransfers([]), []);
  assert.deepEqual(ledger.balancesFromTransfers(null), []);
});

test("receipt hashes link in created order", () => {
  const chain = ledger.receiptChain([
    { receipt_hash: "bb", prev_receipt_hash: "aa", created_at: "2026-10-24T00:01:00Z" },
    { receipt_hash: "aa", prev_receipt_hash: "00", created_at: "2026-10-24T00:00:00Z" }
  ]);
  assert.equal(chain[0].row.receipt_hash, "aa");
  assert.equal(chain[0].linksToPrevious, false);
  assert.equal(chain[1].linksToPrevious, true);
  const broken = ledger.receiptChain([
    { receipt_hash: "aa", prev_receipt_hash: "00", created_at: "2026-10-24T00:00:00Z" },
    { receipt_hash: "cc", prev_receipt_hash: "zz", created_at: "2026-10-24T00:01:00Z" }
  ]);
  assert.equal(broken[1].linksToPrevious, false);
});
