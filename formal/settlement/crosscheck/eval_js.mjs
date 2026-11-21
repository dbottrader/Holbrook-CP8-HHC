// Evaluates the deployed gpu-mesh edge-function code on the inputs in
// model_table.json and prints the results as JSON. Used by
// tests/test_lean_settlement_crosscheck.py.
import { readFileSync } from "node:fs";

import { SETTLED_TOPIC, checkerPay, decodeSettledLog } from "../../../supabase/functions/gpu-mesh/evidence.mjs";
import { distinctPayouts, independentVerifiers, splitsClean } from "../../../supabase/functions/gpu-mesh/protocol.mjs";

const table = JSON.parse(readFileSync(new URL("../model_table.json", import.meta.url), "utf8"));
const word = (n) => BigInt(n).toString(16).padStart(64, "0");

function settledLog(w, v1, v2, c) {
  const addr = (x) => "0".repeat(24) + x.repeat(40);
  return {
    address: "0x" + "d".repeat(40),
    topics: [SETTLED_TOPIC, "0x" + "ab".repeat(32), "0x" + addr("1")],
    data: "0x" + addr("2") + addr("3") + word(w) + word(v1) + word(v2) + word(c) + "cd".repeat(32),
  };
}

const NAMES = {
  parent_empty: "parent_empty",
  child_empty: "child_empty",
  agree: "agree",
  disagree_deterministic: "disagree_deterministic",
};

console.log(JSON.stringify({
  split: table.split.map((row) => ({
    t: row.t,
    clean: splitsClean(row.t),
  })),
  evidence_split_ok: table.evidence_split_ok.map((row) => {
    const decoded = decodeSettledLog(settledLog(row.w, row.v1, row.v2, row.c));
    return { ...row, ok: decoded ? decoded.split_ok : null };
  }),
  checker_pay: table.checker_pay.map((row) => ({ verdict: row.verdict, pay: checkerPay(NAMES[row.verdict]) })),
  independent: table.independent.map((row) => ({
    ...row,
    independent: independentVerifiers(row.worker, [row.a, row.b]),
  })),
  distinct_payouts: table.distinct_payouts.map((row) => ({ ...row, distinct: distinctPayouts(row.addresses) })),
}));
