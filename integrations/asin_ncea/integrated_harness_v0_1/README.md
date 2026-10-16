# ASIN-NCEA Integrated Harness v0.1

This packet integrates the preserved ASIN-NCEA text snapshot lineage into a runnable local verification harness.

## Purpose

The original snapshots are preserved as lineage evidence. The raw v2.0 script currently depends on `Crypto`/`Cryptodome`, which may not be installed in a clean environment. This harness does **not** pretend that dependency issue is solved. Instead, it verifies the source lineage and runs an integrated core using the available `cryptography` package:

- SHA-256 source manifest verification
- Python syntax verification for each source snapshot
- HKDF-SHA256 key derivation
- ChaCha20-Poly1305 authenticated encryption
- ciphertext tamper rejection test
- Ed25519 signed receipt
- two-event ledger with Merkle root
- simulated PoWP wallet gate

## Boundary

HHC constants are treated as namespace/domain-separation metadata, not as cryptographic strength.

The wallet output is a local simulation only. It has no monetary value, no network consensus, and no production authority.

Promotion remains `HOLD` until independent review and/or a separate production security design exists.

## Run

```bash
python3 run_integration.py
```

Expected high-level result:

```text
pass_fail: PASS_WITH_HOLD
promotion_verdict: HOLD
raw_v2_runtime_ready: false   # unless Crypto/Cryptodome is installed
integrated_core_pass: true
```

## Outputs

After running, inspect:

```text
reproduction_output/SOURCE_MANIFEST_VERIFICATION.json
reproduction_output/RAW_RUNTIME_PROBE.json
reproduction_output/LEDGER.json
reproduction_output/INTEGRATION_RECEIPT.json
reproduction_output/ENVIRONMENT_CAPTURE.json
```

## GitHub port note

This branch records the integrated harness interface and evidence boundary. The full local bundle produced on 2026-07-23 has SHA-256:

```text
14e3eaaf71461e35d31f185ed3c84083c516539a057e66c1bb3f5485da7c9807
```

Source snapshot files remain lineage evidence, not promoted production cryptography. Do not treat the simulated HHC-SIM wallet output as monetary issuance.