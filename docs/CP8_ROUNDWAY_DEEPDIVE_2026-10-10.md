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

## D2. Superformula fits: 2023 verified, 2026 not reproduced

The receipts' winning model is a superformula with m ≈ 18.0 both years
(BIC 269/300 vs null BIC 3289/3136).

- **2023: independently re-verified.** Standard Gielis forward model with the
  receipt's parameters reproduces the scan with RSS 668.2 vs recorded 667.6
  (0.1%). The 18-fold fit is real under the receipt's own model.
- **2026: NOT reproduced.** Same forward model, best rotation/scale/offset
  grid search: RSS ≈ 900k vs recorded 726.7. The 2026 parameter set
  (n2 9.92→7.36, n3 9.93→12.86, a 0.84→1.00, n1 1.98→2.15) does not
  regenerate the scan under any standard-form variant tried. Discrepancy
  held open — needs the engine's exact forward model, not a new assumption.
  Consistent with the receipt's own SIMULATED provenance flag.

## D3. What changed 2023 → 2026

- Global shrink: mean Δ = −15.4 px (p = 0.011 vs paired-flip nulls); no long
  contiguous change arcs (longest 2σ arc 2°, p = 1.0) — the change is
  distributed, not a localized edit.
- Harmonic amplitude family stable (18/36/54 both years); 2026 gains a
  9-family (h9/h27/h45, amps 15–27, ~0 in 2023). Phases rotated 72–156°
  between years.
- The 12 morph-calibration stages are IDENTICAL across years; only the
  top-level superformula parameters drifted.

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
- R9 NOT REPRODUCED: 2026 superformula parameter set under standard forward
  model — open discrepancy.
- R10 OBSERVED: distributed ~8% shrink 2023→2026, no localized edit arcs.
- R11 OBSERVED: stable 18-family amplitudes; 2026 adds 9-family; phases rotated.
- R12 OBSERVED: 12-fold alternation quantization-robust; 2023 more
  phase-stable than 2026.
- R13 CORRECTED: receipts are not byte-identical stubs; they are full,
  differing, hash-bound, SIMULATED-provenance model fits under governance hold.
