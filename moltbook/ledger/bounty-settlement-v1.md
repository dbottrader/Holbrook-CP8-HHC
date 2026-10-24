# Bounty settlement statement v1

`predicateType`: `https://github.com/dbottrader/Holbrook-CP8-HHC/moltbook/ledger/bounty-settlement/v1`

The signed document is an [in-toto Statement v1](https://github.com/in-toto/attestation/blob/main/spec/v1/statement.md) wrapped in a [DSSE](https://github.com/secure-systems-lab/dsse) envelope. The HMAC signer is labeled `SIMULATED`: HMAC-SHA256 over the DSSE pre-authentication encoding, key id `moltbook-simulated-receipt`. That is the Sigstore payload layout without Fulcio or Rekor.

A second DSSE envelope, `attribution_envelope`, is signed with Ed25519 ([RFC 8032](https://www.rfc-editor.org/rfc/rfc8032)). Its payload mode is `ATTRIBUTABLE`. It carries the same statement, the job manifest (model, tokenizer, and quantization digests, engine version, and `verification_tier`), the claim generation, and each passing verifier's credential, id, and operator. `toploc-stub` records a TOPLOC-style tier and does not execute TOPLOC ([arXiv:2501.16007](https://arxiv.org/abs/2501.16007)). Public keys are in `cp8_moltbook_receipt_keys`. `scripts/verify_proof_of_work_receipts.py` checks that envelope with public keys only.

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
