# Skill: Deterministic Merkle Build & Verify

**Skill ID:** `skill-cp8-merkle-v1.0`
**Files:** `scripts/build-merkle.py` + `scripts/verify.py`

---

## build-merkle.py

Deterministically hashes all tracked files:
- Walks repo recursively
- Sorts files alphabetically
- Normalizes paths (\ → /)
- Excludes: `.git`, `__pycache__`, `node_modules`, `sha256-manifest.json`, `merkle-root.txt`
- INCLUDES `.github/workflows/` (CI is part of integrity surface)
- Computes SHA-256 per file
- Writes `sha256-manifest.json` + `merkle-root.txt` + `build-manifest.json`

## verify.py

Enforces integrity spine:
1. Reload manifest
2. Re-hash every file
3. Compare expected vs actual
4. Recompute Merkle root
5. Exit nonzero on mismatch
6. Print exact drift locations

## GitHub Actions Integration

```yaml
name: integrity
on: [push, pull_request]
jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: python scripts/build-merkle.py
      - run: python scripts/verify.py
```

## Determinism Requirements

- `sort_keys=True` in JSON dump
- Binary file reads (no encoding drift)
- `.gitattributes`: `* text=auto eol=lf` + explicit per-type rules
- Canonical path separators
- File timestamps EXCLUDED from hash
- `.github/` INCLUDED in hash surface

---
*CP8 Protocol • ASIN-HHC Framework • Holbrook Distributed Lattice*
