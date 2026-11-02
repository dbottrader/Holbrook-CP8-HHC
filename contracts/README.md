# HHCW + Settlement (Base)

HHCW is a work token for verified contribution.

- `HHCWorkCredit` (HHCW): ERC-20. Only `MINTER_ROLE` (the Settlement contract) mints.
- `Settlement`: an EIP-712 `SettlementAttestation` mints exactly 9000 bps to the
  worker and 500 bps to each of the two verifiers. A total that does not divide
  evenly reverts. `settlementId` cannot be reused. `merkleAnchor(bytes32)` stores
  a Merkle root over mesh receipt hashes.
- Admin handoff is two-step (`proposeAdmin`, then `acceptAdmin` after
  `defaultAdminDelay()`). On Base Sepolia the deployer is admin and owner for now.
  Mainnet construction takes `ADMIN_ADDRESS` and the broadcaster must be that account.

```bash
forge install foundry-rs/forge-std@v1.17.0 --no-commit
forge install OpenZeppelin/openzeppelin-contracts@v5.0.2 --no-commit
forge test
```

`lib/` is installed locally and is not committed. Deploy and Basescan
`forge verify-contract` commands are in `MAINNET.md`. The live Base Sepolia
record is [DEPLOYMENT_BASE_SEPOLIA.md](DEPLOYMENT_BASE_SEPOLIA.md). Do not
commit keys and do not broadcast from CI.
