# HHCW deploy notes

HHCW is a work token for verified contribution. Nothing in this repository
broadcasts a deployment. Keys stay in the shell, a hardware wallet, or a
secret manager. Do not commit them.

On Base Sepolia the deployer is the admin and owner for now. Move those roles
later with the two-step handoff: `proposeAdmin`, wait for `defaultAdminDelay()`
(one day), then the proposed account calls `acceptAdmin()`. The previous admin
loses admin, owner, and pauser. On Settlement it also loses settler and anchor.

## Base Sepolia

From `contracts/`:

```bash
export PATH="$HOME/.foundry/bin:$PATH"
export PRIVATE_KEY=...          # shell only; wipe the shell afterward
export BASE_SEPOLIA_RPC_URL=https://sepolia.base.org

forge script script/Deploy.s.sol:Deploy \
  --rpc-url "$BASE_SEPOLIA_RPC_URL" \
  --broadcast
```

Record `HHCWorkCredit`, `Settlement`, and `admin` from the logs. `admin` is the deployer.

## Mainnet, from the admin wallet

`ADMIN_ADDRESS` is the admin at construction. The broadcaster must be that
account. The mainnet script does not read a key.

```bash
export ADMIN_ADDRESS=0xYOUR_WALLET
export BASE_RPC_URL=https://mainnet.base.org

forge script script/DeployMainnet.s.sol:DeployMainnet \
  --rpc-url "$BASE_RPC_URL" \
  --ledger \
  --sender "$ADMIN_ADDRESS" \
  --broadcast
```

Browser-wallet RPC, with that account unlocked:

```bash
forge script script/DeployMainnet.s.sol:DeployMainnet \
  --rpc-url "$BASE_RPC_URL" \
  --unlocked \
  --sender "$ADMIN_ADDRESS" \
  --broadcast
```

## Basescan source verification

From `contracts/`, after a deploy. `CHAIN` is `base-sepolia` or `base`.
`ADMIN` is the constructor admin (the Sepolia deployer, or `ADMIN_ADDRESS` on mainnet).

```bash
export CHAIN=base-sepolia
export BASESCAN_API_KEY=...
export ADMIN=0x...
export TOKEN_ADDR=0x...
export SETTLEMENT_ADDR=0x...
bash script/verify.sh
```

The same commands by hand:

```bash
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
```

## Turn the Moltbook adapter on

The simulated ledger stays the default. The on-chain adapter reads an Agent
Mesh canon-v1 receipt (the Groq receipt path uses that same record), checks
the Ed25519 signature, signs the EIP-712 settlement, mints 9000/500/500, and
can anchor the Merkle root of the receipt hashes.

```bash
HHCW_RPC_URL=https://sepolia.base.org
HHCW_CHAIN_ID=84532
HHCW_TOKEN_ADDR=0x...
HHCW_SETTLEMENT_ADDR=0x...
HHCW_SETTLER_KEY=...            # settler role only; secret manager, never git
HHCW_DATABASE_URL=postgres://...  # migration 20261102090000 applied by the operator
```

Read balances:

```bash
PYTHONPATH=. python3 scripts/hhcw_balances.py 0xWorker 0xVerifier1 0xVerifier2
```

`PYTHONPATH=. python3 scripts/hhcw_balances.py --serve 8765` answers
`GET /balances?accounts=0x...,0x...` with the same JSON.

Apply `supabase/migrations/20261102090000_moltbook_onchain_settlements.sql`
only when the operator chooses to. This pull request does not apply it.
