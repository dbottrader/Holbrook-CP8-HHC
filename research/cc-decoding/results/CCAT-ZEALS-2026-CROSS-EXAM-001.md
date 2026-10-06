# CCAT-ZEALS-2026-CROSS-EXAM-001

Status: EXECUTED_EXTERNAL / HOLD

## OBSERVED

A public GitHub project, CCAT v1.0.0, reports a stable geometric construction-grammar analysis of the Zeals Knoll 2026 formation, reported 5 July 2026.

The repository states:
- measured dataset: `data/circles_drag_60.csv`
- measured circles: 60
- near-regular 17-circle outer boundary
- five metric radius classes A-E
- radial organisation of radius classes
- enriched A-E adjacency under ring-preserving nulls
- repeated A/B/E local motifs
- approximate coordinate-scaffold generation
- predictive support for distinctive E-class anchors
- negative Pleiades test
- full grammar did not beat radial priors in raw accuracy

The repository includes scripts for boundary geometry, radius-class validation, radial nulls, contact-grammar nulls, motif nulls, generative grammar, coordinate generation, and predictive validation.

## INFERENCE

This is materially relevant to CC-OS because it is the first newly surfaced 2026 analysis found in this watch that closely matches our executable-grammar objective rather than stopping at symbolic interpretation.

Its most useful contribution is the separation of:
1. global scaffold,
2. metric classes,
3. radial organization,
4. local adjacency,
5. repeated motifs,
6. generative reconstruction,
7. predictive validation.

That decomposition should become a candidate CC-IR representation.

## CROSS-EXAMINATION

The result is not promoted to independent confirmation.

Reasons:
- circle centers/radii originate from a manual one-click digitization workflow;
- the release is a single external implementation;
- independent extraction of the same image is not yet demonstrated in the inspected release;
- the strongest predictive result is described as diagnostic support, while radial priors dominate common-class prediction;
- approximate coordinate generation is not exact physical replay;
- the repository's own claim boundary explicitly excludes proof of construction or intent.

## NEW TEST NODE

PIECEWISE-GRAMMAR-CROSSREPLAY-001

Take the CCAT Zeals Knoll 60-circle CSV as a candidate frozen geometry, then independently reconstruct it with our CC-OS pipeline.

Compare:

A. CCAT grammar:
17-shell + 5 radius classes + radial class organization + adjacency/motif rules

B. CC-OS primitive grammar:
CIRCLE + RING + RADIAL_DISTRIBUTE + NEST + LINK + local motif transforms

C. Nulls:
radial-only, ring-preserving label permutations, radius-preserving coordinate perturbations, and matched human-construction baselines.

Primary metrics:
- MDL / description length
- center reconstruction error
- radius reconstruction error
- adjacency precision/recall
- motif recovery
- held-out node prediction
- sensitivity to alternate segmentation
- parameter count

Promotion condition:
The external grammar must survive independent extraction and replay, and its advantages must persist against matched nulls and our independently implemented grammar.

## LATTICE EFFECT

Adds a new external benchmark for the exact problem CC-OS is trying to solve: recover a compact geometric construction grammar without semantic decoding.

Status: HOLD.
