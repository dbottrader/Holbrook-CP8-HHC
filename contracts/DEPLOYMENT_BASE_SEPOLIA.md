# Base Sepolia live deployment — HHCW work token for verified contribution

Chain: Base Sepolia (`84532`)  
RPC: `https://sepolia.base.org`  
Git: `cursor/base-hhcw-settlement-onchain` @ `f0ca7ad` — [PR #46](https://github.com/dbottrader/Holbrook-CP8-HHC/pull/46)  
Admin / settler / anchorer (testnet deployer): `0x182c77EDEc89961cde09f8f449aE5a3dFb16B89b`

HHCW is a **work token for verified contribution**. This deploy proves the real end-to-end path: Ed25519 mesh `inference_receipt` (verifier_decision `agree`) → EIP-712 SettlementAttestation → `settle` mint 9000/500/500 bps → `merkleAnchor` → `balanceOf` / LedgerBackend `balance_report`.

## Contracts

| Contract | Address | Deploy tx |
|---|---|---|
| HHCWorkCredit (HHCW) | [`0x24a7B22fC54DbFD117023535eBeCf660B76fdb5d`](https://sepolia.basescan.org/address/0x24a7B22fC54DbFD117023535eBeCf660B76fdb5d) | [`0x48ecd923…19f862`](https://sepolia.basescan.org/tx/0x48ecd923083a51cd54f0828ec4b8b4c23b09d2722fe01c30a1dac5a47a19f862) (block 53387342) |
| Settlement | [`0xdfFE664d23E30Baff7Ad4d16831aD625Cc90bcCA`](https://sepolia.basescan.org/address/0xdfFE664d23E30Baff7Ad4d16831aD625Cc90bcCA) | [`0x9f3da862…41d4e7`](https://sepolia.basescan.org/tx/0x9f3da862ff31465d4ec4ce9c187d42ada6fa0c6c50d138b4e668ddabde41d4e7) (block 53387352) |
| grant MINTER_ROLE → Settlement | same token | [`0x6278ecf5…a87456`](https://sepolia.basescan.org/tx/0x6278ecf5e33b7553a9edf341536e9e3902c738ec1f3112349a6c5bf981a87456) (block 53387361) |

## Live proof settlement

- settlementId string: `settle-basesepolia-live-001`
- mesh receipt hash / merkle root: `18eff3522db0639e85bfb691ca71be012b175fa41216f6c3693bcc160a496f77`
- contributionMinor: `1000` → worker `900` / verifier1 `50` / verifier2 `50`
- recipients (throwaway, no keys required to receive mint):
  - worker `0x1111111111111111111111111111111111111111`
  - verifier1 `0x2222222222222222222222222222222222222222`
  - verifier2 `0x3333333333333333333333333333333333333333`

| Step | Tx | Block |
|---|---|---|
| settle (mint 900/50/50) | [`0xc8664a1d…c41180`](https://sepolia.basescan.org/tx/0xc8664a1dc651913cb501b7c720dd17456c5a43964b4f70d43e0588da8ec41180) | 53387566 |
| merkleAnchor | [`0x10e5b60d…bd0681`](https://sepolia.basescan.org/tx/0x10e5b60d3137af3cd0ca6f29dd3cfbe76fc4bcc9ca4a947b135e3dfba1bd0681) | 53387573 |

`anchorCount` after proof: `1`.

### Final balances (HHCW integer units)

| Account | Units |
|---|---|
| worker `0x1111…1111` | 900 |
| verifier1 `0x2222…2222` | 50 |
| verifier2 `0x3333…3333` | 50 |

Confirmed via `cast call balanceOf` and `scripts/hhcw_balances.py` / `OnchainLedger.balance_report` (`description`: "work token for verified contribution").

### Replay protection

eth_call of the same `settle` with the same settlementId reverts with `AlreadySettled(bytes32)` (selector `0xb196a44a`). No second broadcast.

## Source verification

- Basescan API: **skipped** — no `BASESCAN_API_KEY` / `ETHERSCAN_API_KEY` in env or files.
- Sourcify: **exact_match** for both contracts
  - Token: https://repo.sourcify.dev/84532/0x24a7B22fC54DbFD117023535eBeCf660B76fdb5d/
  - Settlement: https://repo.sourcify.dev/84532/0xdfFE664d23E30Baff7Ad4d16831aD625Cc90bcCA/

## Remaining deployer ETH

`59978822982043064` wei ≈ `0.059978822982043064` ETH on Base Sepolia after deploy + settle + anchor.

## Machine-readable

See [`../deployments/base-sepolia.json`](../deployments/base-sepolia.json).

## Env for LedgerBackend

```
HHCW_RPC_URL=https://sepolia.base.org
HHCW_CHAIN_ID=84532
HHCW_TOKEN_ADDR=0x24a7B22fC54DbFD117023535eBeCf660B76fdb5d
HHCW_SETTLEMENT_ADDR=0xdfFE664d23E30Baff7Ad4d16831aD625Cc90bcCA
HHCW_SETTLER_KEY=<deployer key; never commit>
```
