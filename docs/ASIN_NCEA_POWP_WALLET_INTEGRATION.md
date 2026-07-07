# ASIN-NCEA v2.0 — HHC Wallet PoWP Integration

**Status:** Drive-indexed prototype integration note  
**Evidence tier:** E1 document index; E2 candidate when executable code and tests are imported/reproduced  
**Date indexed:** 2026-07-07  
**Steward:** Dennis Christie / CP8

---

## Source artifact

```text
ASIN-NCEA Prototype v2.0 — HHC Wallet PoWP Integra.pdf
```

Drive ID:

```text
1Zsexla8nO7neU5ooehnTQnTlYwbPOt1T
```

The Drive scan also found a Google Docs version:

```text
ASIN-NCEA Prototype v2.0 — HHC Wallet PoWP Integra...
Drive ID: 1meufDHxyX94QAAnG99hii4FDQ-o0zdF6kHi42VOxjYA
```

---

## Extracted implementation anchors

The scan identified the following implementation constants and file targets:

```text
THREAD_COUNT = 4
CHUNK_SIZE = 4096
STATE_FILE = "ASIN_NCEA_adaptive_state.json"
KEY_FILE = "ASIN_NCEA_identity.pem"
PUB_KEY_EXPORT = "ASIN_NCEA_identity.pub"
PoG_LEDGER_FILE = "PoG_consensus_ledger.json"
HHC_WALLET_FILE = "HHC_wallet_ledger.json"
SYSTEM_ID_V20 = "ASIN_NC_0006_PoWP_Wallet_FINAL"
```

The artifact describes v2.0 as the final PoWP wallet integration layer.

---

## Intended runtime behavior

The prototype links cryptographic process work to an internal HHC wallet ledger.

A valid run should:

1. Initialize ASIN-NCEA v2.0 identity state.
2. Select PAL backend, such as CPU, CUDA, or future WebGPU abstraction.
3. Generate or load adaptive state.
4. Produce cryptographic/integrity output.
5. Compact proof data into a Merkle root.
6. Verify both integrity and Merkle audit.
7. Credit internal HHC wallet ledger only when verification passes.
8. Write proof-of-governance / proof-of-work-process ledger entries.

---

## Wallet boundary

The HHC wallet layer is best described as an internal prototype ledger until there is an externally deployed contract, settlement layer, exchange path, or wallet bridge.

Valid claim:

```text
The prototype records internal HHC PoWP credits for verified runs.
```

Avoid inflated claim:

```text
The prototype creates externally market-valued tokens by itself.
```

---

## Evidence boundary

Current classification:

```text
E1 from Drive-indexed specification artifacts.
E2 once the Python prototype is imported, runs locally, and produces a reproducible receipt/ledger result.
```

Promotion requirements:

```text
- import runnable source
- run local tests
- produce sample ASIN_NCEA_adaptive_state.json
- produce sample PoG_consensus_ledger.json
- produce sample HHC_wallet_ledger.json
- verify replay from receipt
```

---

**End of ASIN-NCEA PoWP Wallet Integration note.**
