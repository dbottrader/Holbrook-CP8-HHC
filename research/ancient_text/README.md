# CP8 Ancient Text Evidence Benchmark

## Objective
Test whether a provenance-preserving, multi-channel CP8 evidence gate improves restoration precision and calibration over a single-model top-1 baseline on damaged ancient texts.

## Primary benchmark
Ancient Greek inscription restoration using Ithaca-compatible inputs/outputs.

## Secondary benchmark
Vesuvius/Herculaneum disputed-stroke analysis using public Vesuvius Challenge ink/surface predictions.

## Preregistered hypothesis
CP8 multi-channel evidence gating will improve calibrated precision at a fixed coverage level and reduce unsupported confident completions relative to a single-model top-1 restoration baseline.

## Evidence channels
Each candidate restoration is represented as an evidence node with independent channels where available:

- model restoration probability
- character/stroke geometry confidence
- cross-model agreement
- lexical/contextual plausibility
- corpus-parallel support
- provenance quality
- human review status

No channel is silently promoted to ground truth.

## Evaluation
For held-out examples with known restorations, report:

- top-1 accuracy
- precision at promoted predictions
- coverage
- Brier score
- expected calibration error (ECE)
- abstention/error rate
- unsupported-confidence rate

The key comparison is not maximum raw accuracy; it is whether CP8 produces fewer high-confidence wrong restorations while retaining useful coverage.

## Promotion rule
A candidate may be promoted only when the configured minimum number of independent evidence channels agree and the fused confidence exceeds threshold. Otherwise it remains HOLD with alternatives preserved.

## Data adapters
The benchmark deliberately separates adapters from the evidence engine:

- `ithaca_adapter`: consumes Ithaca/predicting-the-past restoration candidates
- `vesuvius_adapter`: consumes ink/surface prediction candidates
- `cp8_evidence.py`: origin-agnostic fusion, calibration, abstention, and audit output

## External open-source foundations
- Google DeepMind Ithaca: https://github.com/google-deepmind/ithaca
- Google DeepMind Predicting the Past (Ithaca/Aeneas workflow): https://github.com/google-deepmind/science-skills/tree/main/skills/predictingthepast
- Vesuvius Challenge monorepo: https://github.com/ScrollPrize/villa
- Vesuvius open-data documentation: https://github.com/ScrollPrize/open-data

## Research boundary
A restoration is a candidate reconstruction, not a historical fact. All output retains source identifiers, model/version provenance, alternatives, and evidence-channel scores.
