# Bounty settlement statement v1

`predicateType`: `https://github.com/dbottrader/Holbrook-CP8-HHC/moltbook/ledger/bounty-settlement/v1`

The signed document is an [in-toto Statement v1](https://github.com/in-toto/attestation/blob/main/spec/v1/statement.md) wrapped in a [DSSE](https://github.com/secure-systems-lab/dsse) envelope. The simulated signer is HMAC-SHA256 over the DSSE pre-authentication encoding, key id `moltbook-simulated-receipt`. That is the Sigstore payload layout without Fulcio or Rekor.

Predicate fields are integers in minor units (1000 minor = 1 displayed HHC-SIM):

- `settlementId`, `bountyId`, `worker.id`, `worker.amountMinor`
- `verifiers[]` with `id` and `amountMinor`
- `priceMinor`, `verifierPoolMinor`
- `pendingTransferId` and `postTransferIds` for the two-phase transfer
- `prevReceiptHash` linking the receipt chain
- `backend` = `simulated`
- `walletClass` = `SIMULATED_ONLY_NO_MONETARY_AUTHORITY`

`worker.amountMinor + verifierPoolMinor = priceMinor`. The verifier amounts sum to `verifierPoolMinor`. The subject digest is the submitted artifact sha256.

An EIP-712 typed-data preview with `chainId` 0 is stored beside the envelope and is not the signed payload. No contract is deployed.
