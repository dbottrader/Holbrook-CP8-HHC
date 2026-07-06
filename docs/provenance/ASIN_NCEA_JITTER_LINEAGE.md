# ASIN-NCEA / CP8 Jitter Lineage

This index records the Google Drive ASIN-NCEA prototype lineage discovered during CP8/Holbrook provenance review. The artifacts are preserved as external Drive-sourced provenance records, not canonical production guarantees.

## Development progression

```text
v0.1–0.3   Core harmonic engine and jitter/feedback experiments
      ↓
v0.4–0.8   Deterministic execution, adaptive state, SHA-256 integrity, Ed25519 identity, daemon polling
      ↓
v0.9–1.1   GPU/CUDA/runtime scaling and multi-node key chaining
      ↓
v1.4–1.5   Federated attestation, backend identity, Merkle audit structures
      ↓
v2.0       HHC Wallet / Proof-of-Work-Process integration
```

## Source status

- Source system: Google Drive.
- Source export: Google Docs exported as text/plain through connector.
- Repo role: external provenance lineage for CP8/Holbrook review.
- Canonical status: not canonical unless separately promoted by governance review.
- Known search gaps: v0.5, v1.2, and v1.3 were not found in the Drive searches performed for this import.

## Snapshot inventory

| Version | Title | Drive source ID | UTF-8 bytes | SHA-256 |
|---|---|---:|---:|---|
| v0.1 | ASIN-NCEA Prototype v0.1 — Harmonic Cryptography Engine | `1gXGlTINe7gdrFE7vLMO5BkwKbQANevbWcBUvl1PUofM` | 6242 | `c4efefde14c98875636c207e6fb81d976b057fe45c0729efad89b4cfa5b1a9a2` |
| v0.2 | ASIN-NCEA Prototype v0.2 — Harmonic Cryptography Engine (PERFORMANCE ALIGNMENT) | `1Xp4Six69U1-y15c6nxbKX00QHZ3uZRFkKf1TySq0NcY` | 7108 | `64c5010da9521bcdd09ed2d4bb34aa7d40acc5c30b617b78c48c2527bacbc906` |
| v0.3 | ASIN-NCEA Prototype v0.3 — Adaptive Harmonic Crypto Engine | `1W1KdsVnEVUUWoXWeFC5PZZRf3_UVuCK66M1M414fF7c` | 9753 | `067ea6c3c40b4a5f6e24bcd311e461a70691a74e57d3a5714c6f59f0ec7a8206` |
| v0.4 | ASIN-NCEA Prototype v0.4 — Deterministic Asynchronous Harmonic Engine (FINAL STABILIZATION) | `1Bh4v_hEhClv1pTY-ejHKtNwdwY4dPGuGh0QgXfkIrFQ` | 8572 | `eee65b9075c140750615442eae85affbf3992665741be5cdfe854854f8f63903` |
| v0.6 | ASIN-NCEA Prototype v0.6 — Entropy Integrity Lock (INTEGRITY CHECKED PERSISTENCE) | `1acuC_bmgYIIE3m6KD-3SzvDECVOgsidgQv2VcU4qwEg` | 11917 | `e8c42f123c06b61e6452f32d50711af96a025831f38a9ce670df10c21fb9d161` |
| v0.7 | ASIN-NCEA Prototype v0.7 — Cryptographic Identity Anchor (ED25519 SIGNED PERSISTENCE) | `1fXK8xOBMslEiNv-MSeUMyWMkIbdw0BWJjSwmf1UFK6I` | 14082 | `2b8c18fd82c7023dc6cb2faab526a9554a71f339bc95171eee1856092ea1f680` |
| v0.8 | ASIN-NCEA Prototype v0.8 — Daemon Integrity Polling (CONTINUOUS SELF-REFERENCE) | `12rZ4JKRVbJ4D0XSAIbkf62Xc-0aXrBJCRwFa0Bs909E` | 17961 | `576edb1334301ad070b59bd3ea05b5e1676dd2c934ffb1ab22022dc2f8628b96` |
| v0.9 | ASIN-NCEA Prototype v0.9 — GPU Tensor Core Fusion (HIGH-THROUGHPUT MODE) | `1Gu81SDRBOOGhrWl0QIuOfgYW29x0SnnZ9Q8qGylb2aI` | 15002 | `aa6998197d34b17e8fa3c74ab6da33c43b490af24b2ab1f113fcb01859c659e3` |
| v1.0 | ASIN-NCEA Prototype v1.0 — RT-CUDA Stream Synchronization (TENSOR CORE STABILITY) | `14m9K0QkVpXyAt6p-aJCjc0vnGew0xSYx0UgIdaojhz0` | 15960 | `5992fd08255532dfafddb47287e4aedd5c3a471bed79b21fed246c4e5f1658f2` |
| v1.1 | ASIN-NCEA Prototype v1.1 — Multi-Node Key Chaining (FEDERATED RESONANCE PREP) | `11xD-3DpsMsR-tUy_idDIg3lwTbjuC7JKSYPuyj67JVU` | 17790 | `21a57c63f6250088ae15af6461574ffcbf5a79601d95ac042d173fb43e8d65f5` |
| v1.4 | ASIN-NCEA Prototype v1.4 — Federated Attestation Gossip and Backend ID (DECENTRALIZED SYNC) | `1lL3_ItCevSpzKyKTUYR1iaQSmRUutMb2zfWv7FuBLKY` | 19761 | `d4a9b6a343da8594c89098300120659ae4f71b7f50db10194bd79eecb0efe7c8` |
| v1.5 | ASIN-NCEA Prototype v1.5 — Merkle Tree Compaction and Ledger Audit (IMMUTABLE HISTORY) | `1YRM7P7KbqIQjEmhecc1f3S2AohJPasUbwBE5SWqGFzE` | 22502 | `9132abdad3498ee536465335d857b3bb7905d9f44cf7ecceaf3aa086b984e80e` |
| v2.0 | ASIN-NCEA Prototype v2.0 — HHC Wallet PoWP Integration (FINALIZATION: TOKENIZED VALUE) | `1meufDHxyX94QAAnG99hii4FDQ-o0zdF6kHi42VOxjYA` | 23182 | `f50350aa7c4c271cf9450fed7e29ef19440e9154cf3fd26a730d0650c3a83875` |

## Review note

These files provide a historical implementation/prototype trail. They are evidence of design evolution and prototype code, not proof that the full system is production-secure, cryptographically sound, or independently verified. Promotion requires clean builds, tests, reproducible receipts, and review.
