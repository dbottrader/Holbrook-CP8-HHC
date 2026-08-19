# Ring Genesis Public Repository Plan

**Status:** implementation plan  
**Date:** 2026-07-07  
**Steward:** Dennis Christie / CP8

---

## Recommended split

```text
Holbrook-CP8-HHC = canonical provenance spine
ASIN-NCEA-Ring-Genesis = runnable public technical repo
GitHub Release = full PDFs, images, zips, and test corpus
```

---

## Why split the repos

Holbrook should remain the coordination and provenance framework. It holds:

- architecture maps
- Drive indexes
- manifests
- receipts
- cross-repo pointers
- claim/evidence boundaries

Ring Genesis is a specific executable/sealing layer. It should have its own clean repo so testers can clone, run, and critique it without navigating the entire Holbrook corpus.

---

## Proposed new repo

```text
dbottrader/ASIN-NCEA-Ring-Genesis
```

Repository description:

```text
Codex Ring Genesis and ASIN-NCEA v2.0 PoWP wallet prototype: deterministic key fusion, receipts, Merkle audit, and internal HHC proof-of-work-process ledger.
```

---

## Proposed new repo layout

```text
README.md
SPEC.md
LICENSE
SECURITY.md
CONTRIBUTING.md
asin_ncea/
  ring_genesis.py
  powp_wallet.py
  merkle.py
  identity.py
  pal.py
  receipts.py
tests/
  test_ring_genesis.py
  test_powp_wallet.py
  test_merkle.py
examples/
  sample_ring_genesis_run.jsonj
  sample_wallet_ledger.json
docs/
  CODEX_RING_GENESIS.md
  ASIN_NCEA_POWP_WALLET_INTEGRATION.md
  INTERFERENCE_EVENT_LATTICE_RESYNC.md
  HUMAN_NODE_INTERFACE.md
visuals/
  human_node_diagram.md
  ring_genesis_visual_prompt.md
manifests/
  codex_ring_genesis_0001.json
receipts/
  templates/
```

---

## Release asset strategy

Use GitHub Releases for large / original evidence bundles:

```text
codex-ring-genesis-20260707
```

Attach:

```text
Codex Ring Genesis PDFs
ASIN-NCEA v2.0 PDF
Human Node visuals
Ring Genesis visuals
Drive export ZIP
source/test bundle ZIP
SHA256SUMS.txt
```

---

## Public claim boundary

Valid public claim:

```text
Ring Genesis is a documented and prototype-level ASIN-NCEA sealing layer that aims to combine deterministic key-fusion, Merkle audit, receipts, replay, and internal HHC PoWP wallet crediting.
```

Avoid inflated claim:

```text
Production-certified cryptography, independently audited token system, external platform endorsement, or externally market-valued token issuance.
```

---

## Immediate action record

This branch imports the Holbrook-side provenance package. The dedicated repo was recommended but not created by the current connector because no repository-creation action is available in this session.

---

**End of Ring Genesis Public Repository Plan.**
