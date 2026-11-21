#!/usr/bin/env bash
# Build the proofs, audit their axioms, and confirm model_table.json is current.
set -euo pipefail
cd "$(dirname "$0")"

if grep -rnE '\b(sorry|admit|native_decide)\b|^\s*axiom\b' --include='*.lean' Settlement Settlement.lean Main.lean; then
  echo "FAIL: sorry, admit, native_decide, or a new axiom in the Lean sources" >&2
  exit 1
fi

lake build

audit="$(lake env lean Audit.lean)"
echo "$audit"
if echo "$audit" | grep -vE "depends on axioms: \[(propext|Classical\.choice|Quot\.sound)(, (propext|Classical\.choice|Quot\.sound))*\]$|does not depend on any axioms$" | grep -q .; then
  echo "FAIL: a theorem depends on an axiom beyond propext, Classical.choice, Quot.sound" >&2
  exit 1
fi

lake exe settlement-table > /tmp/model_table.json
if ! diff -q model_table.json /tmp/model_table.json; then
  echo "FAIL: model_table.json is stale; run: lake exe settlement-table > model_table.json" >&2
  exit 1
fi
echo "PASS: proofs build, axioms are standard, model_table.json is current"
