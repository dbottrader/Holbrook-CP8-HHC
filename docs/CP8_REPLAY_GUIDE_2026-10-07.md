# CP8 Replay Guide — 2026-10-07

**Purpose:** let another agent reproduce what is reproducible, and see exactly what blocks the rest — without guessing.

**Companion files:** `manifests/cp8-core-index-2026-10-07.json`, `docs/CP8_CORE_EVIDENCE_MAP_2026-10-07.md`

> **The index describes evidence; it does not promote evidence.**
> A successful replay produces a receipt. It does not, by itself, promote a claim. Promotion is a gate decision under `research/cc-decoding/receipt.schema.json` and the repository's constitutional rules (`README.md`): *no receipt means no promotion; replay supersedes narration; reality retains veto.*

Record the exact commit SHA you checked out before running anything. Every result below should be filed as a receipt naming: commit, environment (OS, Python/Node versions), input hashes, command, exit code, output hashes, and a bounded verdict — `PASS`, `FAIL`, or `HOLD/BLOCKED` with the reason.

---

## 0. Checkout and record

```bash
git clone https://github.com/dbottrader/Holbrook-CP8-HHC
cd Holbrook-CP8-HHC
git rev-parse HEAD        # record this SHA in your receipt
python3 --version; node --version
```

Expected: a public MIT-licensed repository. License says nothing about the separate `cp8-morphology` code, which carries a proprietary ASIN-HHC LLC notice in its README and is *not* in this repository.

---

## 1. Replayable now: evidence infrastructure

These tools are in the public repository and use only Python stdlib / Node built-ins (plus Python dependencies for DAR-P, see §1.3). This guide was prepared from a read-only audit; **no run is claimed here**. Your run is the first replay receipt — file it, including failures.

### 1.1 Build a fresh manifest and verify it (self-consistency)

The committed `sha256-manifest.json` is a **2026-05-23 build receipt (45 files, build `Holbrook-CP8-HHC-20260523-173348`)** and does not cover the current tree. Do not cite it as a current-tree verification. Instead, test the tooling end-to-end:

```bash
# Build a manifest of your checkout (writes sha256-manifest.json, merkle-root.txt, build-manifest.json)
python3 scripts/build-merkle.py

# Verify the tree against the manifest you just built
python3 scripts/verify.py --manifest sha256-manifest.json --repo-root .
```

Success criteria (from `scripts/verify.py`):

- Exit code `0` = all valid; `1` = hash mismatch; `2` = manifest missing/corrupt; `3` = Merkle root mismatch.
- The verifier re-checks every listed file's SHA-256, recomputes the Merkle root (odd leaf count handled by duplicating the last leaf), recomputes the combined signature over the canonical file map + Merkle root, and hard-checks the HOS ground truth:
  `63b5160ef51f0464295e86888c3e6605d8f6cc970635183887083818e8749320`

Also available, Node equivalents:

```bash
node verification/verify-all.js --manifest sha256-manifest.json
node verification/verify-merkle.js            # root + tree; supports inclusion proofs
```

**What this proves:** byte integrity of your checkout relative to the manifest, and that the Merkle construction is deterministic. **What it does not prove:** authorship, scientific correctness, independent reproduction, or patent scope (boundary stated in `provenance/public-record.json`).

### 1.2 Verify the historical 2026-05-23 manifest (optional, expect mismatch)

```bash
git stash   # or work in a clean copy
python3 scripts/verify.py --manifest sha256-manifest.json --repo-root .
```

Against the current tree this is expected to report mismatches for files changed since 2026-05-23. That is evidence about manifest staleness (index item `U10`), not about the tooling. If you want a true historical check, check out the tree as of that build in a separate clone and record both results separately. Do not overwrite the committed historical manifest in the main tree without filing a new build receipt that names the commit it describes.

### 1.3 DAR-P gate validator

`dar_p/gate_validator.py` — deterministic, fail-closed validator. Signing invariant: the Ed25519 signature is verified over the canonical bytes of `unsigned_body` only; the signature block is never part of the signed message.

```bash
pip install -r requirements-dar-p.txt   # cryptography, pydantic, typing_extensions
python3 -m pytest tests/test_gate_validator.py tests/test_runtime.py -q
```

Success criteria: the test suite passes on your checkout (record the exact pass/fail counts in your receipt). Uses the strict JSON canonicalization defined in the module (sorted keys, compact separators, UTF-8, no NaN/Infinity). A green run is `EXECUTED` evidence for the validator's behaviour on its fixtures — not a promotion of any artifact the validator might later gate.

---

## 2. Blocked: CCD-9 harmonic replay

**Target record:** `research/cc-decoding/results/CCD9-EXECUTION-001.json` / `.md`
**Recorded result to reproduce:** harmonic 15 = `0.1998894513` of harmonics 1–30 energy; harmonic 12 = `0.1303211451`; 5,000-sample permutation null mean `0.0334002843`, SD `0.0321210445`, 95th percentile `0.0988810416`, empirical p `0.00159968`. Parameters: centre `[310, 205]`, ellipse radii `[190, 130]`, 1,440 angular × 8 radial samples.
**Recorded inputs:** HTML SHA-256 `900bf538b6a8138d6bd3880b6f579f1e4ec7aa09f1f596dabe12e7349917613d`; embedded PNG SHA-256 `7f747d643c2b90fd6ddf3fb0af6d0796a62fafaa2a6a4f95821cd4f6d42e1e11` (773,611 bytes).

A replay from the public repository is **currently blocked**. Blockers, in order:

1. **Frozen input bytes are not committed.** Only the hashes above are in the repo. Without the exact HTML/PNG, step one of any replay — hash the input and compare — cannot be performed.
2. **Executing code is not committed.** GitHub code search across `user:dbottrader` found no polar/angular spectral-scan implementation (2026-10-07). The method is named (`polar_angular_spectral_scan`) and its parameters are recorded, but the code, its dependencies, and its exact sampling/weighting choices are not public.
3. **Random seed is not recorded.** The permutation null (`n=5000`) cannot be reproduced bit-for-bit, only statistically re-estimated, until a seed or a seeded re-issue is provided.
4. **Source reconciliation is unfinished.** The Wanborough 2026 binding was rejected for this input; the reconciled Ware Farm Manor 2025 source imagery is not frozen or hashed (`image_bytes_frozen: false`, `source_sha256: null` in `research/cc-decoding/sources/CCD9-791-SOURCE-RECONCILIATION.json`), and no perspective-rectified original exists yet.

### Unblock checklist (for the steward or a contributing agent)

- [ ] Commit or hash-bind an accessible copy of the frozen HTML/PNG so its SHA-256 can be re-verified by a third party.
- [ ] Commit the scan code with pinned dependencies, the recorded parameters, and a fixed random seed; include the command that produced `CCD9-EXECUTION-001`.
- [ ] Freeze and hash the original Ware Farm Manor source image; produce a perspective-rectified derivative with its own hash and preprocessing manifest.
- [ ] Add the geometry-matched null the execution record itself calls for (the simple permutation null is explicitly exploratory), plus held-out reconstruction.
- [ ] Re-run, compare against the recorded values above within a stated tolerance, and file a receipt: verdict `PASS`, `FAIL`, or `HOLD/BLOCKED`.

A passing re-run upgrades the finding from `EXECUTED` to `REPRODUCED` in the receipt vocabulary. It still does not become `ESTABLISHED` until the promotion gate — blinded replication, alternative segmentation, independent review — is separately passed and recorded. Hypotheses `CC-H001`–`CC-H004` (`research/cc-decoding/HYPOTHESES.json`) stay OPEN until their registered tests are run.

---

## 3. Blocked: morphology Pass 0–6 replay

**Target records:** `dbottrader/cp8-morphology` (README/STATUS), `dbottrader/CP8-Ultimate-System` (README results tables: Crabwood Face 2002 evidence 0.669; Jellyfish 0.542; Concentric Rings 0.525; Yin-Yang Spiral 0.519; six synthetic controls; Pass 3 triggers on 5/6 synthetics).

A replay from public GitHub is **currently blocked**:

1. **Code is not public.** Both repos contain documentation only. `cp8-morphology/STATUS.md` points to a Google Drive source zip (`cp8-morphology-v1.0.0.zip`, 39.4 KB) whose contents were not verified in the 2026-10-07 audit.
2. **Inputs are not hash-bound.** Formation images behind the results table are not identified by hash in the public record; scales are estimates from web-sourced imagery (both READMEs state this).
3. **Outputs are not public.** Claimed genome JSONs, `CP8_ULTIMATE_SYSTEM_REPORT.json`, `cp8_master_database.json`, and overlay/dashboard images are not in either repo.

### Unblock checklist

- [ ] Publish the Pass 0–6 code (or a public mirror with a recorded SHA-256 of the Drive zip, so the zip's contents become hash-verifiable).
- [ ] For at least one formation — Crabwood Face 2002 is the recorded primary candidate — publish: input image with SHA-256, parameters/resolution, the genome JSON output, and the synthetic-control set used.
- [ ] Document the CLI exactly as the README advertises (`cp8-morphology formation.jpg --resolution 0.15 --output genome.json --overlay viz.png` and `run_pipeline(...)`), then run it and file a receipt comparing reproduced values (circles/nodes/edges, clustering, box dimension, evidence score) against the README table within a stated tolerance.
- [ ] Re-run the six synthetic controls and confirm or revise the Pass 3 negative-control result (5/6 trigger). This check matters more than the formation scores: it is the recorded boundary on binary/encoding claims.

Until then, cite the batch as **OBSERVED (reported), HOLD** — never as verified measurements.

---

## 4. What a good replay receipt looks like

Follow `research/cc-decoding/receipt.schema.json`. Minimum fields:

```json
{
  "artifact_id": "string",
  "input_sha256": "string",
  "source_provenance": {},
  "feature_schema": {},
  "hypothesis_registry": "research/cc-decoding/HYPOTHESES.json",
  "model_registry": [],
  "outputs": [],
  "controls": {},
  "replay": {
    "commit": "full git SHA of the checkout used",
    "environment": "OS, Python/Node versions, dependency pins",
    "command": "exact command line",
    "exit_code": 0,
    "verdict": "PASS | FAIL | HOLD/BLOCKED",
    "tolerance": "how outputs were compared to the recorded values"
  },
  "evidence_tier": "E0|E1|E2|E3|E4|E5",
  "promotion_state": "HOLD|EXISTS|EXECUTED|REPRODUCED|ESTABLISHED",
  "independent_review": {}
}
```

Rules that keep a replay honest (from `PUBLIC_LAUNCH.md` and `specs/CC-DECODING-001.md`):

- Record failures, contradictions, missing dependencies, and negative results. They are first-class evidence.
- A model may not generate a candidate interpretation and then serve as the evidence that validates it.
- Classifying your own result is allowed; promoting it is not. Submit the receipt for review and Reality Veto.
- If unsure of the evidence tier, classify lower and state what would be required to promote.

---

## 5. Replay status summary (2026-10-07)

| Surface | Status | Next action |
|---|---|---|
| Manifest/Merkle verify (`scripts/`, `verification/`) | Replayable now | Run §1.1, file first receipt, index `U10` |
| DAR-P gate validator (`dar_p/`, `tests/`) | Replayable now | Run §1.3, file receipt |
| CCD-9 harmonic 15 | **Blocked** — code, seed, frozen bytes not public | Unblock checklist §2 |
| Morphology Pass 0–6 batch | **Blocked** — code, inputs, outputs not public | Unblock checklist §3 |
| Roundway 2023/2026 (Drive artifacts) | Not audited; not in a public repo | Publish hash-bound copies before citing |
| Anything promoted to ESTABLISHED | None | — |

*Prepared 2026-10-07. The index describes evidence; it does not promote evidence.*
