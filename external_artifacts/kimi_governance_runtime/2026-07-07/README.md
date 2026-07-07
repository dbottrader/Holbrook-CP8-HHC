# Kimi Agent Governance Runtime Initiative — Test Import

**Status:** pushed for public testing and external inspection.  
**Date:** 2026-07-07  
**Steward:** Dennis Christie / CP8  
**Evidence tier:** E2 for local executable runtime components that passed tests; E1 for release/integration claims.

This folder records the Kimi Agent Governance Runtime Initiative parse and delivery package for the Holbrook / ASIN-HHC / CP8 provenance spine.

## Included files

- `parse_report.md` — local parse and verification report.
- `inventory.json` — parsed inventory with hashes, paths, sizes, and classifications.
- `tree.txt` — parsed source tree.
- `SHA256SUMS.txt` — hashes for public import artifacts.
- `unified_delivery.zip.b64` — base64 encoded delivery ZIP for reconstruction and testing.
- ASIN-NCEA bridge state, public identity, and ledger artifacts.

## Reconstruct delivery ZIP

```bash
base64 -d unified_delivery.zip.b64 > unified_delivery.zip
unzip unified_delivery.zip -d unified_delivery
```

## Verification summary

```text
project/tests: 92 passed
test_bridge.py: 36 passed
compileall: passed
full project pytest including benchmarks: 94 passed, 7 benchmark fixture/plugin errors
```

The benchmark errors are fixture/dependency setup issues involving benchmark support, not direct governance-runtime unit-test failures.
