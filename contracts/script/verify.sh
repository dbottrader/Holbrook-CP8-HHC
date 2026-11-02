#!/usr/bin/env bash
# Verify HHCW source on Basescan. HHCW is a work token for verified contribution.
# Does not broadcast a deployment.
set -euo pipefail
: "${CHAIN:?set CHAIN to base-sepolia or base}"
: "${BASESCAN_API_KEY:?}"
: "${ADMIN:?admin address used in the constructor}"
: "${TOKEN_ADDR:?}"
: "${SETTLEMENT_ADDR:?}"
cd "$(dirname "$0")/.."

forge verify-contract \
  --chain "$CHAIN" \
  --verifier etherscan \
  --etherscan-api-key "$BASESCAN_API_KEY" \
  --constructor-args "$(cast abi-encode "constructor(address)" "$ADMIN")" \
  "$TOKEN_ADDR" \
  src/HHCWorkCredit.sol:HHCWorkCredit

forge verify-contract \
  --chain "$CHAIN" \
  --verifier etherscan \
  --etherscan-api-key "$BASESCAN_API_KEY" \
  --constructor-args "$(cast abi-encode "constructor(address,address)" "$ADMIN" "$TOKEN_ADDR")" \
  "$SETTLEMENT_ADDR" \
  src/Settlement.sol:Settlement
