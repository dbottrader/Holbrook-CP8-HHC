# CP8 Full-Run Specimen — what I actually ran, 2026-10-10

**Executor:** Ace, on Dennis Christie's workspace.
**Rule:** this report describes evidence; it does not promote evidence. Promoted/ESTABLISHED findings after all runs: **still 0.** Everything remains `HOLD`, now with more executed receipts.

You asked me to run it — all of it, against the repos on hand. So I ran the full Pass 0–6 pipeline end to end on an expanded synthetic battery, re-derived Crabwood, executed a spectral analysis of the Drive-recorded Roundway 2023 vs 2026 scans, and re-smoked the Holbrook verification layer. Receipt: `CP8_FULLRUN_RECEIPT_2026-10-10.json` (SHA-256 `53f3c3fb96eba44e3eb1e14f2dcddff8aee3b4ba1584b4ce976ee9fba1f1f144`).

---

## Phase A — full pipeline on 14 synthetic controls (new)

The import-fixed package ran `run_full_pipeline()` on 14 generated images: the 6 recorded controls plus symmetry variants (pack 4/8/12), an 8-arm radial L-system, a minimal grammar, and a random-blob baseline. Evidence scores reproduce the recorded table exactly (grammar_default 0.503, ifs_julia 0.553, lsys_radial 0.523, pack_radial_6 0.589, lsys_koch 0.342).

**Negative control, strengthened:** 9 of 14 controls trigger Pass 3 binary detection, all via `filled_empty_grid` — pack 4/6/8/12, both radial L-systems, ifs_julia, both grammars. The three that don't: ifs_sierpinski, lsys_koch, random_blobs.

The project's own conclusion now bites harder: *binary detection fires on most synthetic controls; do not claim message encoding until the same rule must survive on ≥3 independent formations.* This is the strongest executed evidence yet for that boundary — the detector fires on geometry the method itself generated.

## Phase B — Crabwood re-derivation (reconfirmed)

Pass 2/3/5 recomputed from the recorded genome: 128 nodes, 224 edges, clustering 0.2536, density 0.027559, spectral gap 0.000451, box dimension 1.2293 ± 0.0433, and exactly 1 surviving binary rule (`filled_empty_grid`) — exact vs the record, again.

## Phase C — Roundway 2023 vs 2026 spectral (new, OBSERVED)

The Drive-recorded 360-sample polar scans were analyzed CCD-9-style (harmonic energy 1–30, 2,000-permutation null):

| | 2023 | 2026 |
|---|---|---|
| Top harmonic | **18** (0.8391) | **18** (0.7971) |
| Permutation p | at floor (~0.0005) | at floor (~0.0005) |
| h15 energy | ~0 | ~0 |

Both years show the same dominant 18-fold spectral component. But: Pearson r = **0.16** — the raw scans are only weakly correlated, so the two years are not the same signal; the 18-fold peak in each is an OBSERVED spectral feature of recorded scans, not an established formation property. And note both `measurement_receipt_roundway_*.json` files are byte-identical stubs — the receipts assert nothing. Pass 0–1 image replay for Roundway remains blocked: no source images published.

## Phase D — Holbrook smoke (green)

`tests/test_gate_validator.py`: **8 passed** (return code 0).

## What changed, what didn't

**Now executed with receipts:** full-pipeline control battery with a 9/14 negative-control failure; Roundway 2023/2026 spectral comparison; re-confirmed Crabwood re-derivation; DAR-P gate suite green.

**Still blocked:** Pass 0–1 from original images (`2289.png`, Roundway sources unpublished); original CCD-9 replay (code/seed/bytes unpublished).

**Promotion: HOLD. ESTABLISHED: 0.**

---

*Local kit: `~/workspace/cp8-fullrun/` — harness, inputs, control images, hashed outputs. Nothing private published. Curated summaries may be committed to the public repo on your word.*
