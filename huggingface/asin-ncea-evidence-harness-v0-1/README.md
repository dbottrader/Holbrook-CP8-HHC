---
title: ASIN-NCEA Evidence Harness v0.1
emoji: 🐍
colorFrom: indigo
colorTo: green
sdk: gradio
app_file: app.py
pinned: false
short_description: Receipt-first public smoke harness with explicit E3/HOLD boundaries.
---

# ASIN-NCEA Evidence Harness v0.1

This Hugging Face Space package exposes the ASIN-NCEA integrated architecture harness as a transparent public demonstration.

## What it runs

- HKDF-SHA256 key derivation
- ChaCha20-Poly1305 authenticated-encryption roundtrip
- deliberate ciphertext-tamper rejection
- Ed25519 test-receipt signing and verification
- two-event hash-linked ledger
- Merkle-root calculation
- simulated PoWP reward gate

## Evidence boundary

```text
status: PASS_WITH_HOLD
evidence_level: E3_LOCAL_INTEGRATION
promotion_verdict: HOLD
witness_class: MACHINE_EXECUTION_UNATTESTED
runtime_scope: PUBLIC_DEMO_SMOKE_TEST_ONLY
wallet_class: SIMULATED_ONLY_NO_MONETARY_AUTHORITY
```

The Space does **not** establish:

- production-ready cryptography
- independent human reproduction
- live token issuance or monetary value
- external consensus
- kernel promotion
- security amplification from harmonic constants

HHC constants are used as namespace/domain-separation metadata only.

## Artifact anchors

```text
integrated_harness_sha256: 14e3eaaf71461e35d31f185ed3c84083c516539a057e66c1bb3f5485da7c9807
deterministic_core_hash: ee93c43c62eccb6dd9eaf14787bdfe6af2965f66763216221f504af282447274
local_ledger_merkle_root: ffc27df9d1d33a454e858284b19694c5c7513a9833e25113550f0acd8ec68405
source_entries: 13
```

## Provenance

Core implementation draft PR:

- `dbottrader/Holbrook-CP8-HHC#9`

Artifact-registry and continuity draft PR:

- `dbottrader/ASIN-HHC-Artifacts#2`

Collaboration proof note:

- `dbottrader/ASIN-HHC-Collaboration#1`

## Local run

```bash
pip install -r requirements.txt
python app.py
```

The interface emits a human-readable status summary and a machine-readable JSON receipt.
