# CP8 Ancient Text Benchmark — Preregistration

## Research question
Does multi-channel evidence fusion with explicit abstention improve the reliability of ancient-text restoration relative to single-model top-1 predictions?

## Primary outcome
Precision among promoted restorations at matched or reported coverage.

## Secondary outcomes
- top-1 accuracy
- coverage
- Brier score
- expected calibration error
- number of high-confidence incorrect restorations
- number of cases retained as HOLD with useful alternatives

## Baselines
1. Single-model top-1 candidate.
2. Single-model thresholded candidate using the same promotion threshold.
3. CP8 fused evidence candidate.

## CP8 treatment
Candidate restorations are scored by a weighted geometric mean across available channels. Missing channels are ignored rather than imputed. A prediction is promoted only if:

1. fused confidence >= 0.72; and
2. at least 3 channels individually score >= 0.50.

These values are fixed before benchmark execution. Any later tuning must be reported as a separate experiment.

## Initial channel weights
- model restoration probability: 1.0
- geometry/stroke support: 1.0
- independent model agreement: 1.0
- lexical/contextual support: 0.8
- corpus-parallel support: 0.7
- provenance quality: 0.8

## Dataset split
Use a held-out set with known restorations. Do not tune thresholds or channel weights on the final evaluation partition.

## Success criterion
The primary hypothesis is supported if CP8 increases promoted precision and/or reduces high-confidence incorrect restorations while preserving non-trivial coverage. Raw accuracy alone is insufficient.

## Failure criterion
The approach is considered unsupported if CP8 fails to improve calibration or promoted precision, or if improvements disappear under matched-coverage comparison.

## Interpretation boundary
No restoration is treated as historical fact solely because the evidence engine promotes it. Promotion means the candidate passed the predefined evidence rule for this benchmark.
