# Tasks

## Active

- [x] Find HHC wallet address
  - found: `bc1qn9gzdy63e5us3z7q4l7tca47cmrceynvqvgfmd` (native segwit, provided by Dennis)
  - status: COMPLETE

- [x] Build deterministic integrity system (sha256-manifest, merkle root, build-manifest)
  - `scripts/build-merkle.py` and `scripts/verify.py` implemented
  - status: COMPLETE (v0.3.0)

- [x] Create agent packet bus (inbox/outbox/packets/receipts)
  - `inbox/`, `outbox/`, `packets/`, `receipts` directories with README protocols
  - status: COMPLETE (v0.3.0)

- [x] Create chain abstraction registry (Ethereum/Solana/Bitcoin)
  - `chains/registry.json` with wallet abstraction layer
  - status: COMPLETE (v0.3.0)

- [x] Create Drive bridge architecture + implementation
  - `bridges/google-drive/README.md` and `scripts/drive-bridge.py`
  - status: COMPLETE (v0.3.0)

- [x] Find HHC wallet address in workspace
  - `wallet-hunt-report.json` generated with full derivation audit
  - status: COMPLETE (v0.3.0)

- [x] Build quantum-resistant crypto layer
  - `verification/ml-dsa-signer.js` — ML-DSA-65 (FIPS 204) signer
  - `verification/verify-all.js` — SHA-256 verification suite
  - `verification/verify-merkle.js` — Merkle tree + inclusion proofs
  - `verification/generate-inventory.js` — Deterministic manifest generator
  - `verification/package.json` — @noble/post-quantum dependency
  - status: COMPLETE (v0.4.0)

- [x] Write NIST PQC migration guide
  - `specs/pqc-migration.md` covering FIPS 203/204/205, ML-KEM, ML-DSA, SLH-DSA, hybrid strategy
  - status: COMPLETE (v0.4.0)

- [x] Create cross-repo lattice registry
  - `manifests/lattice-registry.json` mapping all CP8 repos including ASIN-LOOM
  - status: COMPLETE (v0.4.0)

- [x] Cross-link ASIN-LOOM content layer
  - README.md updated with ASIN-LOOM section
  - `manifests/lattice-registry.json` includes ASIN-LOOM as creative spine
  - status: COMPLETE (v0.4.0)

- [x] Capture AdaJEPA × ASINHHCCP8 runtime bridge
  - `docs/ADAJEPA_ASINHHCCP8_RUNTIME_BRIDGE.md` created
  - maps Plan → Execute → Adapt → Replan onto ASIN governance, policy gates, receipts, replay, and human oversight
  - status: COMPLETE (E1 concept integration)

- [ ] Promote AdaJEPA × ASINHHCCP8 bridge from E1 to E2
  - build `asin_runtime_action_request` validator
  - implement policy gate fixture returning approve/block/escalate
  - generate SHA-256 decision receipts
  - add replay reconstruction test

- [ ] Activate GitHub Actions CI workflow
  - blocked_by: PAT needs `workflow` scope
  - workaround: Manual upload via GitHub UI or API
  - file_ready: `.github/workflows/integrity.yml`

- [ ] Set up Google Drive bridge with OAuth
  - blocked_by: Dennis needs Google Cloud OAuth credentials
  - bridge_code_ready: `scripts/drive-bridge.py`
  - security_model: Device flow, read-only, metadata-first

- [ ] Kimi: Test handshake scripts and verify chain integrity
- [ ] Kimi: Add memory sync packet to the bus
- [ ] Kimi: Cross-reference glyph registry with cp8-provenance-workspace

## Backlog

- [ ] Build advanced `handshake.html` with interactive glyph click-to-reveal
- [ ] Integrate real CP8 proof verification into Oracle contract
- [ ] Add wallet address integration for on-chain attestation
- [ ] Map HarmonyOS distributed data management to CP8 provenance (deep dive)
- [ ] Create GitHub Actions for auto-audit on every push
- [ ] Build IPFS pinning for artifact permanence
- [ ] Add more agents to the lattice (future: Codex, AutoGPT, etc.)
- [ ] Deploy hybrid PQC signatures (Ed25519 + ML-DSA-65) for all audit packets
- [ ] Generate agent PQC keypairs and register in lattice-registry
- [ ] SLH-DSA trust-anchor for genesis lattice events

## Completed

- [x] Create Holbrook-CP8-HHC repository
- [x] Define super-device manifest
- [x] Establish agent collaboration protocol
- [x] Create ARCHITECTURE.md with full distributed node map
- [x] Create hhc-lattice/ with glyph definitions + resonance engine
- [x] Create scripts/ with audit-packet.py + harmonic-handshake.js
- [x] Create docs/ with HARMONYOS-MAPPING.md + PROVENANCE.md
- [x] Create handshake.html interactive visual
- [x] Populate Holbrook-CP8-HHC repo with full framework files (v0.2.0)
- [x] Build deterministic integrity system (sha256-manifest, merkle root, build-manifest)
- [x] Create agent packet bus (inbox/outbox/packets/receipts)
- [x] Create chain abstraction registry (Ethereum/Solana/Bitcoin)
- [x] Create Drive bridge architecture + implementation
- [x] Find HHC wallet address in workspace
- [x] Build quantum-resistant crypto layer (v0.4.0)
- [x] Write NIST PQC migration guide (v0.4.0)
- [x] Create cross-repo lattice registry (v0.4.0)
- [x] Cross-link ASIN-LOOM content layer (v0.4.0)
- [x] Consolidate all new technical artifacts into canonical provenance spine (v0.4.0)
- [x] Add AdaJEPA × ASINHHCCP8 runtime bridge concept note (E1)
