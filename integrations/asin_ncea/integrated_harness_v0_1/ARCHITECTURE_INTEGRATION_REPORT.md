# ASIN-NCEA Architecture Integration Report v0.1

## Integrated Layers

| Layer | Source lineage idea | Harness implementation |
|---|---|---|
| PAL | CPU/GPU backend abstraction | CPU-vector/runtime environment capture |
| NCEA crypto core | ChaCha20 + harmonic/geometric fusion | ChaCha20-Poly1305 AEAD using standard `cryptography` primitives |
| HHC constants | 428/528/741/963 harmonic namespace | Domain-separation metadata only |
| Persistence/integrity | state JSON + hashes | canonical JSON + SHA-256 source and event hashes |
| Identity | Ed25519 persistence | Ed25519 signed deterministic receipt |
| PoG ledger | append ledger + Merkle audit | two-event hash-linked ledger + Merkle root |
| PoWP wallet | token mint after verification | simulated HHC-SIM reward only after all integrated gates pass |

## Why not execute raw v2.0 as production?

The raw v2.0 snapshot imports `Crypto`, but the dependency comment says `pycryptodomex`. Those are different import namespaces. Clean execution therefore depends on which package is installed and how imports are written. The raw lineage also uses fresh randomness in seed derivation during encryption/decryption, so the raw roundtrip is not a safe production cryptographic design without correction.

## Promotion Boundary

This harness supports an E3 local integration claim only:

- source snapshots verified
- integrated architecture runs locally
- AEAD/tamper/signature/ledger checks pass
- simulated wallet gate is controlled by verification

It does not support claims of production cryptography, live token issuance, external consensus, or independent human reproduction.

## Local run anchors

```text
artifact: ASIN-NCEA_INTEGRATED_HARNESS_v0.1
status: PASS_WITH_HOLD
evidence_level: E3_LOCAL_INTEGRATION
promotion_verdict: HOLD
witness_class: MACHINE_EXECUTION_UNATTESTED
source_entries: 13
source_hashes_ok: true
source_syntax_ok: true
raw_v2_runtime_ready: false
integrated_core_pass: true
deterministic_core_hash: ee93c43c62eccb6dd9eaf14787bdfe6af2965f66763216221f504af282447274
ledger_merkle_root: ffc27df9d1d33a454e858284b19694c5c7513a9833e25113550f0acd8ec68405
bundle_sha256: 14e3eaaf71461e35d31f185ed3c84083c516539a057e66c1bb3f5485da7c9807
```

## Repository handling

Do not publish generated private key files such as `ASIN_NCEA_identity.pem`. Do not promote source snapshots as production crypto. Keep release bundles out of the implementation tree unless explicitly attached as release assets.