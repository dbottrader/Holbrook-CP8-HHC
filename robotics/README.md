# CP8 Robotics / Humanoid Audit Layer

**Status**: Active consolidation into Holbrook-CP8-HHC (the high-impact spine).

## What This Is
CP8 / ASIN-HHC applied to humanoid robotics (Tesla Optimus, Boston Dynamics Atlas, Figure 01, Agility Digit, Sanctuary Phoenix, etc.).

The core problem: Current humanoids exhibit jitter, stutter-steps, over-correction, and unverifiable behavior because their motion models run on disharmonic control loops (PID at 60Hz grids, high-latency inference).

The CP8 solution: A lightweight, cryptographically sealed lattice layer (SHA-256 chains + 28 glyphs + harmonic anchors) that third-party audits and corrects robot outputs in real time. Gait, torque, speech, and decision traces become provenance-bound and verifiable.

This layer turns robot behavior from "black box motion" into "auditable, correctable, rewardable work."

## Key Artifacts in This Folder
- sensor_merkle.py — Deterministic CSV sensor Merkle proofs and CLI (`cp8.sensor_merkle.v1`)
- samples/ — Synthetic (not real) sensor CSVs for tests and examples
- CP8_Humanoid_Audit_Spec.md — Technical specification
- LinkedIn_Pitch_Robotics.md — Public-facing posts for collaboration
- Integration_with_CP8Oracle.md — How verified robot corrections can mint HarmonicCoin on-chain

## Why This Belongs in Holbrook-CP8-HHC
This repo already contains the provenance engine (Merkle scripts, build-merkle.py, verification/), harmonic lattice (hhc-lattice/), multi-agent cognition, and on-chain contracts (via Collaboration bridge). The robotics layer is the highest-leverage application: making physical AI accountable.

## Next Steps
1. Done: Merkle proofs for robot gait/sensor logs (`sensor_merkle.py`, below)
2. Pilot with one humanoid platform (testnet first)
3. Publish side-by-side before/after footage with cryptographic receipts


## Sensor Merkle proofs (`sensor_merkle.py`)

Hash a humanoid sensor CSV into a replayable Merkle receipt (`cp8.sensor_merkle.v1`).

```bash
python robotics/sensor_merkle.py --csv robotics/samples/humanoid_sensor_log.sample.csv
python robotics/sensor_merkle.py --csv path/to/log.csv --max-rows 100 --prove 0 --out receipt.json
python robotics/sensor_merkle.py --verify-receipt receipt.json
```

The sample CSV is synthetic and is not a real robot recording. Each frame becomes a canonical JSON object (sorted keys, fixed-precision decimal strings, no NaN). Leaves are `SHA-256(0x00 || frame)`, internal nodes are `SHA-256(0x01 || left || right)`, and an odd level duplicates the last node (Bitcoin / gpu-mesh style). Domain-separation prefixes are used so a leaf cannot be confused with a node. That differs from `gpu-mesh/gpumesh/merkle.py` (raw digest concatenation, no prefixes) and `scripts/build-merkle.py` (UTF-8 concatenation of hex strings). The receipt records the prefixes, the odd-node rule, the precision, `input_digest` (SHA-256 of the raw CSV bytes), the root, `n_frames`, the tool version, and the git commit.

### Feeding the root into a CP8 manifest / CP8Oracle

What exists in this repo today:

- The receipt JSON is the sensor manifest. Put `root` and `input_digest` on any higher-level work record you already emit. Independent replay is `python robotics/sensor_merkle.py --verify-receipt receipt.json` (or rerun the CLI on the same CSV with the same `--max-rows` / `--precision` / `--skip-bad` flags).
- `Settlement.merkleAnchor(bytes32 root)` in `contracts/src/Settlement.sol` stores a raw 32-byte root and emits `MerkleAnchored`. It is documented in the contract as a commitment over **mesh receipt hashes**, and it has no schema or type tag. A sensor root *could* be passed as that `bytes32`, but nothing in the contract distinguishes a sensor tree from a mesh receipt tree, and `ANCHOR_ROLE` is required. `Settlement.settle(...)` also takes a `receiptRoot`, which is bound by an EIP-712 settler attestation — again with no sensor-schema entrypoint.
- HOS runtime HTTP routes in `hos/api/main.py` are `/health`, `/v1/process`, `/v1/verify`, `/v1/harmonic-state`, and `/v1/manifest`. None of them accepts a sensor Merkle root.

What does **not** exist in this repo:

- There is no module named "Physical-State Bridge". The protocol described in the robotics docs (hash frames, Merkle receipt, independent replay) is what `sensor_merkle.py` implements.
- `CP8Oracle.sol`, `CP8Oracle.verifyProof()`, and `HarmonicCoin.mintForVerifiedBlock()` are cited in `Integration_with_CP8Oracle.md` as living in ASIN-HHC-Collaboration. They are not in `contracts/src/` here. There is no on-chain function that takes a `cp8.sensor_merkle.v1` root and mints a reward for a verified sensor log.

A later integration would need a typed hook — for example an oracle or settler method that records `(schema, input_digest, root, n_frames)` and only then allows a work credit — rather than overloading the untyped mesh `merkleAnchor`.

No woo. Grounded engineering. Human-mediated verification first.
