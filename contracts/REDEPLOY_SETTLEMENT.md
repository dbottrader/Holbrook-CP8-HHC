# Redeploy Settlement with the SameAddress guard (Dennis's step)

`Settlement.sol` now reverts with `SameAddress(worker, verifier1, verifier2)`
unless the worker and the two verifiers are three different addresses. The
live Base Sepolia contract (`0xdfFE664d23E30Baff7Ad4d16831aD625Cc90bcCA`)
does not have this guard. Contracts cannot be changed in place, so a new
Settlement has to be deployed and given the mint right on the existing HHCW
token. This needs the token admin key, so only Dennis can do it. Nothing here
has been broadcast to any public chain.

Until the redeploy, the off-chain checks already refuse shared payout
addresses: the coordinator (`skipped_shared_payout` in `releasePending` and
`/api/settlements/pending`) and the box settler (`refusal_status`). The new
contract is the last line of defence.

## What the script does

`script/RedeploySettlement.s.sol`, run by the HHCW token admin:

1. deploys a new `Settlement(admin, HHCW)`, which grants `SETTLER_ROLE` and
   `ANCHOR_ROLE` to the admin;
2. grants `MINTER_ROLE` on HHCW to the new Settlement;
3. revokes `MINTER_ROLE` from the old Settlement, so only the new one can mint;
4. checks both role changes and prints the new address.

Balances already minted are untouched. The old Settlement stays deployed but
can no longer mint.

Tested on a local Anvil chain (chain 31337, Anvil's public dev key): after
`Deploy.s.sol` and then this script, the new Settlement had `MINTER_ROLE` and
the old one did not.

## Commands (from `contracts/`, on Dennis's machine)

```bash
export PATH="$HOME/.foundry/bin:$PATH"
forge install foundry-rs/forge-std@v1.17.0 --no-git
forge install OpenZeppelin/openzeppelin-contracts@v5.0.2 --no-git
forge test                     # 22 tests, all must pass

# The key stays in this shell; never commit it or paste it anywhere.
read -rs PRIVATE_KEY && export PRIVATE_KEY
export TOKEN_ADDR=0x24a7B22fC54DbFD117023535eBeCf660B76fdb5d
export OLD_SETTLEMENT=0xdfFE664d23E30Baff7Ad4d16831aD625Cc90bcCA

# Dry run first (simulates against the live chain, broadcasts nothing):
forge script script/RedeploySettlement.s.sol --rpc-url https://sepolia.base.org

# Then broadcast:
forge script script/RedeploySettlement.s.sol --rpc-url https://sepolia.base.org --broadcast
```

Optional source verification on Sourcify, as for the first deploy:

```bash
forge verify-contract --chain base-sepolia --verifier sourcify \
  "$NEW_SETTLEMENT" src/Settlement.sol:Settlement
```

## After the broadcast: point the code at the new address

The EIP-712 domain includes the contract address, so the settler must sign for
the new contract. Replace `0xdfFE664d23E30Baff7Ad4d16831aD625Cc90bcCA` with the
new address in:

- `supabase/functions/gpu-mesh/protocol.mjs` (`CHAIN.settlement`)
- `gpu-mesh/settler/settle.py` (`SETTLEMENT`)
- `deployments/base-sepolia.json`, `contracts/DEPLOYMENT_BASE_SEPOLIA.md`
- `gpu-mesh/gpumesh/ledger.py`, `gpu-mesh/gpumesh/ledger_backend.py`, and the
  site and docs pages that link the contract (`rg -l 0xdfFE664d` lists them)

Then restart the box settler and deploy the edge function (merging to `main`
does it through `.github/workflows/supabase-functions.yml`).
