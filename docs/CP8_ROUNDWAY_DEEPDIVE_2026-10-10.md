# CP8 Roundway Deep Dive — 2026-10-10

Follow-up to the 2026-10-10 decode. Seed 20261010. OBSERVED unless a
corrected p < 0.05 says otherwise. Promotion HOLD; established findings 0.

## D1. Receipts actually retrieved and verified (correction)

The full-run report said the two measurement-receipt JSONs were
"byte-identical stubs." That was wrong — the earlier download wrote 0-byte
files. Properly downloaded 2026-10-10:

- They DIFFER (canonical SHA-256 `fa207e68…` vs `9f33a1d6…`).
- Each receipt's `source_hash` matches its CSV's SHA-256 exactly
  (2023: `344b53bfc289d45b…`; 2026: `9e83700d8a075ad7…`). Hash binding VERIFIED.
- Each contains full model fits (fourier / golden / null / superformula),
  12 morph-calibration stages, and governance
  `{hold: true, reason: "NO RECEIPT = NO PROMOTION until physical replication"}`.
- Provenance field, both years: `"SIMULATED construction-derived parameters;
  replace with measured aerial geometry before any promotion"`.

## D2. Superformula fits: BOTH verified (correction)

The receipts' winning model is a superformula with m ≈ 18.0 both years
(BIC 269/300 vs null BIC 3289/3136).

- **2023: independently re-verified.** Standard Gielis forward model with the
  receipt's parameters reproduces the scan with RSS 668.2 vs recorded 667.6
  (0.1%).
- **2026: also verified — after recovering the engine's exact forward model.**
  An initial "not reproduced" verdict was my own sign-convention error, not a
  data discrepancy. The engine (`CP8_Measurement_Engine_v1.html`, Drive,
  2026-09-08) uses `t = theta − rot` with rot in radians. With the exact
  formula: RSS 726.7 vs recorded 726.7 — exact. Both 18-fold fits are real
  under the receipt's own model.
- The 2026 fit is the sharper test of the pipeline: it only verifies against
  the engine's actual code, which is why the engine HTML is now pinned as a
  required input for any future re-verification.

## D3. What changed 2023 → 2026 (corrected)

- Raw radii are smaller in 2026 (mean 173.4 vs 188.9 px; mean Δ = −15.4 px,
  p = 0.011 vs paired-flip nulls; no long contiguous change arcs — longest
  2σ arc 2°, p = 1.0, so the change is distributed, not a localized edit).
- **But invariant scale is identical: 99.88 vs 100.09** (scale·a^(n2/n1),
  a=b normalization — per the 2026-09-08 `delta_analysis_2023_vs_2026.json`,
  independently re-derived here to the same numbers). The raw-mean difference
  is absorbed by the superformula scale–a degeneracy; it is not established
  as a physical shrink. The earlier "8% shrink" phrasing is retracted.
- Harmonic amplitude family stable (18/36/54 both years); 2026 gains a
  9-family (h9/h27/h45, amps 15–27, ~0 in 2023). Phases rotated 72–156°
  between years.
- The 12 morph-calibration stages are IDENTICAL across years; only the
  top-level superformula parameters drifted (n2 9.92→7.36, n3 9.93→12.86,
  rot 0→4.0°).

## D4. The 12-fold alternation, stress-tested

- Robust to quantization: at aligned boundaries, L3/L5/L7 all give identical
  cross-year strings (`0202…`, `0404…`, `0606…`).
- Phase behavior differs: 2023 stays perfectly alternating under boundary
  rotation (phase-shifted `4040…`); 2026's alternation breaks into irregular
  strings off-alignment. 2023's 12-fold pattern is the cleaner of the two.
- Rotation/reflection nulls are degenerate here (a rotated square wave
  re-symbolizes to the same alternation) — uninformative, not a refutation;
  the permutation/walk/white-noise nulls from the decode run stand.

## Register

- R7 VERIFIED: receipt↔CSV hash binding, both years.
- R8 VERIFIED: 2023 superformula 18-fold fit (RSS match 0.1%).
- R9 VERIFIED (corrected): 2026 superformula fit reproduces exactly (RSS
  726.7 = 726.7) under the engine's exact forward model (t = θ − rot,
  rot in radians; engine HTML pinned as required re-verification input).
  The earlier "not reproduced" was my sign-convention error.
- R10 CORRECTED: raw 2026 radii smaller (mean Δ −15.4 px, distributed, no
  edit arcs) but invariant scale identical (99.88 vs 100.09) — the "8% shrink"
  phrasing retracted; raw-mean difference is scale–a degeneracy.
- R11 OBSERVED: stable 18-family amplitudes; 2026 adds 9-family; phases rotated.
- R12 OBSERVED: 12-fold alternation quantization-robust; 2023 more
  phase-stable than 2026.
- R13 CORRECTED: receipts are not byte-identical stubs; they are full,
  differing, hash-bound, SIMULATED-provenance model fits under governance hold.
