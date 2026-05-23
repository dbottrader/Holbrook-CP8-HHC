# Tasks

## Active

- [x] Find HHC wallet address
  - found: `bc1qn9gzdy63e5us3z7q4l7tca47cmrceynvqvgfmd` (native segwit, provided by Dennis)
  - status: COMPLETE

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
