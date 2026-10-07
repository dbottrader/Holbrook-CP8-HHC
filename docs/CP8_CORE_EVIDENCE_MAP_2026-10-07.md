# CP8 Core Evidence Map — 2026-10-07

**Canonical repository:** `dbottrader/Holbrook-CP8-HHC`
**Machine-readable companion:** `manifests/cp8-core-index-2026-10-07.json`
**Audience:** a future agent that needs to understand the actual CP8 work in minutes, without access to the private archive.

> **The index describes evidence; it does not promote evidence.**

Every claim on this page points backward to a repository artifact or an execution receipt. Where a claimed artifact is not in a public repository, this map says so. That absence is a finding, not a gap to be narrated over.

The repository's own rules govern everything below, from `README.md` and `provenance/public-record.json`:

- No receipt means no promotion.
- Replay supersedes narration.
- Specification is not implementation.
- No mechanism may silently convert uncertainty into authority.
- Reality retains veto.

---

## 1. What is CP8?

CP8 / ASIN-HHC is a human-AI provenance and evidence-governance framework, originated and stewarded by Dennis M. Christie (CP8). ASIN = **Anchor, Shape, Intention, Number** (origin context; artifact form; purpose; verification label). See `docs/FUTURE_AGENT_REFERENCE.md`, `docs/PUBLIC_PROVENANCE_RECORD.md`.

The morphology lane applies that governance to a concrete scientific-style question: what geometric structure is actually present in aerial/crop formations, measured against controls, before any interpretation is allowed?

The pipeline shape, end to end:

```text
CP8 → morphology pipeline → CCD-9 execution → evidence artifacts → receipts → promotion state
```

## 2. What code actually implements it?

This is where the map must be exact, because the answer is two different answers.

### 2a. Implemented in public — the evidence infrastructure

These files are in `dbottrader/Holbrook-CP8-HHC`, are executable, and are the part a future agent can run today:

| Artifact | Role |
|---|---|
| `scripts/build-merkle.py` | Deterministic SHA-256 manifest + Merkle root builder |
| `scripts/verify.py` | Re-checks manifest files, HOS ground truth, Merkle root, combined signature. Exit codes 0–3 |
| `scripts/audit-packet.py` | Audit packet tooling |
| `verification/verify-all.js`, `verify-merkle.js`, `generate-inventory.js`, `ml-dsa-signer.js` | Node verification suite, Merkle inclusion proofs, inventory, post-quantum signing |
| `dar_p/gate_validator.py` | DAR-P validator: schema binding, non-circular Ed25519 verification over the canonical `unsigned_body`, REQUIRED/OPTIONAL gates, fail-closed, emits a validation receipt |
| `tests/test_gate_validator.py`, `tests/test_runtime.py` | Test coverage for the above |
| `hhc-lattice/resonance.py` | Symbolic lattice layer. Per `docs/FUTURE_AGENT_REFERENCE.md`, symbolic/harmonic material is orientation metadata, not empirical proof |

Evidence tier: **E2** (author-executable local artifact). This code proves byte integrity and gate execution. It does not prove a scientific claim is true.

### 2b. Described, not in public — the morphology pipeline (Pass 0–6)

`dbottrader/cp8-morphology` and `dbottrader/CP8-Ultimate-System` each contain only `README.md`, `STATUS.md` (and a `LICENSE` in the former). The READMEs describe a ~1,430-line package:

- Pass 0–1 `geometry.py` — image → primitives
- Pass 2 `graph.py` — graph construction, Laplacian, centrality
- Pass 3 `binary.py` — binary hypothesis scanner
- Pass 5 `fingerprint.py` — 5-submetric fingerprints (Pass 4 folded in)
- Controls `synthetic.py` — synthetic generators
- Integration `pipeline.py` (`run_pipeline` / `run_full_pipeline`), `cli.py`

**None of that code, and none of its claimed JSON outputs (genomes, `CP8_ULTIMATE_SYSTEM_REPORT.json`, `cp8_master_database.json`), is in a public GitHub repository** as of this audit. GitHub code search across `user:dbottrader` for `run_pipeline`, `cp8_geometry`, `polar_angular`, `spectral_scan` returned zero implementations on 2026-10-07.

`cp8-morphology/STATUS.md` locates the source: a zip in Google Drive, `cp8-morphology-v1.0.0.zip` (39.4 KB). That zip was not accessed or verified in this audit.

Reading state: **OBSERVED** (described), evidence tier **E1**. Until the code is published, Pass 0–6 results are *reported*, not replayable. This is the single most important fact in this map.

## 3. The canonical worked example: CCD-9

CCD-9 is the one place the whole chain operated on real data with a preserved record. Records: `research/cc-decoding/results/CCD9-EXECUTION-001.json` and `.md`. Governing spec: `specs/CC-DECODING-001.md` (DRAFT / HOLD) — a 12-step governed pipeline whose rule is that a decoded message stays HOLD unless segmentation and mapping survive blinded replication, alternative segmentation, null controls, and independent reproduction.

### The chain, link by link

1. **Source formation.** The analysed HTML labels its image "CCD-9 / Formation 791", June 29 2026, and the project initially bound it to the 2026 Wanborough Plain formation (`research/cc-decoding/sources/CCD-9-2026-WANBOROUGH.json`).
2. **Freeze.** HTML SHA-256 `900bf538b6a8138d6bd3880b6f579f1e4ec7aa09f1f596dabe12e7349917613d`; embedded PNG SHA-256 `7f747d643c2b90fd6ddf3fb0af6d0796a62fafaa2a6a4f95821cd4f6d42e1e11`, 773,611 bytes. The hashes are committed; **the frozen bytes are not**.
3. **Geometric extraction.** Polar angular spectral scan at centre `[310, 205]`, ellipse radii `[190, 130]`, 1,440 angular samples, 8 radial samples — image-derived parameters.
4. **Harmonic analysis.** Harmonic 15 holds ≈19.99% of energy across harmonics 1–30 (`h15_energy_fraction_1_to_30: 0.1998894513`); harmonic 12 ≈13.03%.
5. **Null / permutation test.** 5,000-sample angular permutation: null mean 3.34%, SD 3.21%, 95th percentile 9.89%, empirical p ≈ 0.0016.
6. **Result.** The strongest geometry-first signal in this input is **15-fold radial organization**.
7. **Uncertainty.** The record states its own limits: the null is *not geometry-matched*, the centre/ellipse are image-derived, so the p-value is exploratory and cannot be promoted as a final significance claim.
8. **Promotion state: HOLD.** Status in record: `EXECUTED_EXPLORATORY_HOLD`.

Reading state: **TESTED** (exploratory). Evidence: **E2 / LOCALLY_EXECUTED**. Not reproduced, not established.

### The reconciliation — a negative result worth preserving

The embedded image's geometry does **not** match the 2026 Wanborough formation. Source reconciliation (`research/cc-decoding/sources/CCD9-791-SOURCE-RECONCILIATION.json`) marks the Wanborough binding `REJECTED_FOR_THIS_INPUT` and instead points, on visual match and watermark, to **Ware Farm Manor, near Lyme Regis, Devon, reported 28 June 2025** — whose official source discussion describes a 15-circle wheel around a central disc. Confidence: `moderate_visual_match_only`. The reconciled source image is **not frozen** (`image_bytes_frozen: false`, `source_sha256: null`), and the Wanborough target record is `NOT_FROZEN` with `input_sha256: null`.

A future agent should treat the wrong-binding catch as the system working as designed: provenance vetoed a label that geometry did not support.

### Claim audit inside the execution

| Claim | Outcome |
|---|---|
| 8 petals | Not supported by current measurement; 15-fold component observed |
| 3 concentric rings | Not established |
| Octagonal boundary | Not established |
| Solar-apex capture | Not established (sun/sky is part of the presentation image) |
| 111 / 432 / 528 Hz assignments | Not derivable from image geometry |
| 8 × 3 = 24 mapping | Semantic hypothesis, not image-derived evidence |

### What CCD-9 does not have yet

- The executing scan code is **not committed** to any public repo.
- The permutation **random seed is not recorded**.
- No perspective-rectified original, no geometry-matched nulls, no held-out reconstruction.
- Registered hypotheses `CC-H001`–`CC-H004` (`research/cc-decoding/HYPOTHESES.json`) remain **OPEN**; their required tests (geometry-matched nulls, blind segmentation, held-out motifs, independent reconstruction, multiple-comparison correction) are not yet executed.

So CCD-9 today is a reconstructable *specimen of method*, and an honest one — but a literal replay from public artifacts is currently **blocked**. See `docs/CP8_REPLAY_GUIDE_2026-10-07.md` for exactly what would unblock it.

## 4. The other reported execution: CP8-Ultimate-System batch

`CP8-Ultimate-System/README.md` reports full Pass 0–6 runs over four formations and six synthetic controls. Headline numbers as reported:

| Formation | Circles/Nodes | Edges | Clustering | Box dim | Evidence |
|---|---|---|---|---|---|
| Crabwood Face 2002 | 128 | 224 | 0.2536 | 1.2293 | **0.669** |
| Jellyfish | 54 | 97 | 0.3148 | 1.1917 | 0.542 |
| Concentric Rings | 41 | 77 | 0.3333 | 1.237 | 0.525 |
| Yin-Yang Spiral | 37 | 65 | 0.3018 | 1.0769 | 0.519 |

Crabwood Face 2002 is the primary candidate (also noted: C2 symmetry, box dimension 1.2293 ± 0.0433, R² = 0.9951).

Reading state: **OBSERVED** (reported). The genome JSONs, inputs, input hashes, and code behind this table are not in the public repo, so a future agent must not cite these numbers as verified measurements — only as the project's reported results awaiting a replayable publication.

### The negative control that matters most

Five of the six synthetic controls *also* trigger the Pass 3 binary detector. The project's own conclusion, in both the README and `STATUS.md`:

> Binary detection fires on too many synthetic controls. **Do not claim message encoding until rejection criteria are tightened** — the same rule must survive on ≥3 independent formations.

Reading state: **TESTED — negative-control failure.** This is a finding about the method, and it is arguably the most training-valuable item in this entire map: it is the boundary, measured, between an interesting signal and an established result.

### Other preserved audits

- **Baudo motor claim** (crop circles as blueprints for magnetic/free-energy motors): independent verification none found, peer review none, patents not identified, prototype claimed without controlled demonstration. Assessed confidence **0.15, LOW** — unproven visual analogy only.
- **Known issues, in the record's own words:** ring detection sensitive to perspective distortion; Pass 4 folded into Pass 5; no ground-truth physical measurements — all scales are estimates from web-sourced imagery.

## 5. Findings register

| ID | Finding | State | Promotion |
|---|---|---|---|
| F-CCD9-H15 | Strong 15th angular harmonic, exploratory permutation p ≈ 0.0016 | TESTED (exploratory) | HOLD |
| F-CCD9-CLAIM-AUDITS | 8-petal / rings / octagon / solar-apex / Hz claims not supported or not derivable | TESTED (negative) | HOLD |
| F-CCD9-SOURCE-BINDING | Wanborough binding rejected for this input; Ware Farm Manor 2025 visual match | TESTED | HOLD |
| F-PASS3-NEGATIVE-CONTROL | Binary scanner triggers on 5/6 synthetic controls; encoding claims barred | TESTED (negative) | HOLD |
| F-CRABWOOD-CANDIDATE | Crabwood Face 2002 highest reported complexity (0.669) | OBSERVED (reported) | HOLD |
| F-BAUDO | Motor/free-energy blueprint claim, confidence 0.15 | TESTED (audit) | HOLD |
| F-PROMOTED-COUNT | Findings at ESTABLISHED in the morphology core | — | **0** |

## 6. Where the receipts and hashes are

- **CCD-9 inputs:** `research/cc-decoding/results/CCD9-EXECUTION-001.json` — HTML and PNG SHA-256, byte count, full measurement and null statistics.
- **Receipt schema:** `research/cc-decoding/receipt.schema.json` — required fields and the promotion vocabulary `HOLD / EXISTS / EXECUTED / REPRODUCED / ESTABLISHED`.
- **Repository integrity:** `sha256-manifest.json` + `merkle-root.txt`. Note the manifest is a **2026-05-23 build receipt (45 files)** and does not cover the current tree; treat it as historical, and rebuild before citing it (replay guide, §2).
- **HOS ground truth:** `63b5160ef51f0464295e86888c3e6605d8f6cc970635183887083818e8749320` — checked hard-coded in `scripts/verify.py`.
- **Provenance spine:** `provenance/public-record.json` and `docs/PUBLIC_PROVENANCE_RECORD.md` — GIT_VERIFIED milestones from the 2026-05-23 genesis, evidence classes, and the boundary that a hash proves byte integrity, not authorship, correctness, or patent scope.
- **Prior package:** `manifests/convergence-openai-math-2026-10-06.json` — the OpenAI comparison, recorded without a derivation claim.

## 7. What remains unresolved

1. Morphology code is not public (Drive zip unverified) — Pass 0–6 is reported, not replayable. `U1`
2. CCD-9 scan code, seed, and frozen input bytes are not public. `U2`
3. Ware Farm Manor source is a visual match only; original not frozen or hashed; no perspective rectification. `U3`
4. Wanborough 2026 target source remains `NOT_FROZEN`. `U4`
5. Geometry-matched nulls, held-out reconstruction, perturbation tests, multiple-comparison correction (CC-H001/CC-H004) not executed. `U5`
6. Pass 3 tightening (≥3 formations, same rule) not done; encoding claims remain barred by the project's own note. `U6`
7. Synthetic controls at 6; the record's own next step is 100+ for a statistical baseline. `U7`
8. No ground-truth physical measurements; all scales are estimates. `U8`
9. Ring detection under perspective distortion needs adaptive tolerance. `U9`
10. `sha256-manifest.json` is stale relative to the current tree; no current-tree verification receipt exists. `U10`
11. Roundway 2023/2026 measurement artifacts live in Drive, not in a public repo, and were not audited here — do not cite them as executed findings on the basis of this map. `U11`
12. US Provisional 63/892,035 is a `SELF_REPORTED_ANCHOR`; status and scope are unverified. `U12`
13. Public launch gates remain open in `PUBLIC_LAUNCH.md` (Hugging Face mirror receipt, independent replay receipt, external contributor challenge, Notion reconciliation). Ecosystem promotion remains HOLD. `U13`

## 8. Can another agent replay it?

| Surface | Replayable from public repo today? |
|---|---|
| Evidence infrastructure (manifest/Merkle verify, DAR-P gate validator, JS suite) | **Yes** — stdlib Python / Node. Commands in `docs/CP8_REPLAY_GUIDE_2026-10-07.md`. This map does not claim a run it did not perform; the first replay receipt should be filed against those commands. |
| CCD-9 harmonic result | **No** — blocked on scan code, seed, and frozen input bytes. Unblock path is specified in the replay guide. |
| Morphology Pass 0–6 batch | **No** — blocked on code, hash-bound inputs, and genome outputs being published. |

## Chronology

```text
2026-05-23   Holbrook-CP8-HHC genesis (GIT_VERIFIED, provenance/public-record.json)
2026-07-04   Project genome + future-agent reference
2026-07-30   Public provenance record
2026-08-08   cp8-morphology / CP8-Ultimate-System v1.0.0 status (code in Drive zip)
CCD-9        Executed spectral scan → HOLD (research/cc-decoding/results/)
2026-10-06   OpenAI convergence recorded without derivation claim
2026-10-07   This core evidence index
```

Evidence infrastructure → executed case → independent convergence observed → convergence recorded without derivation claim. Each arrow points at a committed artifact; none of them promotes the next.

---

*Prepared 2026-10-07 from a read-only audit of the public repositories named above. The index describes evidence; it does not promote evidence.*
