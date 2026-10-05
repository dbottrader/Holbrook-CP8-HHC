# CC-OS-001 — Crop-Circle Operating System Reverse Engineering

Status: EXECUTION / HOLD

## Objective

Treat crop formations as physical artifacts that may encode a generative grammar or executable transformation system. The research target is not a symbolic interpretation of individual formations, but the smallest reproducible computational grammar that reconstructs the largest number of independently measured formations.

## Evidence law

OBSERVED -> PROVENANCE -> TEST -> REPLAY -> PROMOTION

EXISTS != EXECUTED != REPRODUCED != ESTABLISHED.

Capability, model agreement, symbolic resemblance, harmonic significance, or numerical coincidence cannot independently promote a claim.

## Corpus model

Each formation is represented as:

SOURCE -> FREEZE -> GEOMETRY -> MORPHOLOGY -> GRAPH -> AST -> HYPOTHESES -> NULLS -> GENERATOR -> REPLAY -> RECEIPT

### Physical layer
- source image/video
- original provenance
- date/location
- crop/terrain
- perspective and scale
- uncertainty

### Structural layer
- circle/ring/arc/line primitives
- centers
- radii/diameters
- angular positions
- radial distances
- topology
- symmetry
- hierarchy
- adjacency
- orientation

### Computational layer

Candidate instruction primitives:

CIRCLE(r)
RING(r_inner,r_outer)
ARC(r,theta1,theta2)
ROTATE(theta)
TRANSLATE(x,y)
SCALE(s)
REPEAT(n, primitive)
RADIAL_DISTRIBUTE(n, rule)
NEST(parent, child)
LINK(a,b)
TRANSFORM(state_a,state_b)

These are hypotheses for representation, not claims that formations contain literal code.

## Cross-formation objective

Find a compact grammar G such that:

G(parameters_i) -> reconstruction_i

for the maximum number of formations while minimizing free parameters and reconstruction error.

A grammar only becomes a corpus-level candidate when it survives held-out formations, alternative segmentations, geometry-matched nulls, and independent replay.

## Null families

1. Uniform random points.
2. Same radial distribution, randomized angles.
3. Same angular distribution, randomized radii.
4. Geometry-preserving perturbation.
5. Matched synthetic generators.
6. Human-construction baseline where measurable.
7. Image/perspective artifact controls.
8. Multiple-comparison/max-statistic controls for exploratory scans.

## Blindness

Semantic labels are unavailable to the geometry stage. Candidate interpretations cannot modify the segmentation or generative model that produced them.

## Executed discoveries

### D1 — CCD-9 harmonic evidence is weaker than the nominal p-value suggests

The existing CCD-9 receipt reports H15 energy = 0.1998894513 against a 5,000-draw permutation null with mean 0.0334002843 and SD 0.0321210445. The nominal single-frequency empirical p-value is 0.00159968.

A cross-examination found that the scan covered harmonics 1-30, while the receipt does not report a maximum-over-30-harmonics null. The H15 deviation is about 5.18 null standard deviations, but a conservative Bonferroni correction over the 30 scanned harmonics gives 0.0479904.

Therefore the previous H15 result is an exploratory signal, not a robust discovery. The correct replay is a max-statistic permutation test over the complete preregistered harmonic family.

This is a downgrade of evidential strength, not a failure of the CC-OS method.

### D2 — 409 admits an exact six-module arithmetic decomposition

Using the currently reported aggregate inputs:

409 total circles
6 arms
1 central node
13 reported major/spine circles per arm

the arithmetic is exact:

409 = 1 + 6 x 68
68 = 13 + 55
therefore:

409 = 1 + 6 x (13 + 55)

This yields a candidate OS address-space decomposition:

KERNEL: 1 central node
MODULES: 6 arm modules
SPINE: 13 nodes/module
RESIDUAL: 55 nodes/module

The 55-node residual is not an observed measurement yet. It is a derived prediction from the aggregate count and the 13-per-arm input.

The important test is now concrete: blind circle extraction must determine whether the physical geometry actually partitions into six modules containing approximately/exactly 13 spine nodes plus 55 residual nodes each. If it does not, the arithmetic pattern is discarded.

This is therefore an executable hypothesis, not a semantic interpretation.

## Priority sequence

1. Freeze the largest reproducible image corpus.
2. Convert formations into normalized primitive graphs.
3. Cluster recurring primitives and transformations.
4. Generate candidate CC-IR programs.
5. Fit generators using minimum-description-length/reconstruction criteria.
6. Test against nulls and human-construction baselines.
7. Cross-validate on held-out formations.
8. Search temporal sequences for state transitions.
9. Only then test astronomy, calendars, ancient scripts, frequencies, constants, or other semantic domains.
10. Produce machine-readable receipts and promote only after replay.

## First flagship targets

- CCD-9 / Wanborough
- CCD-9 embedded-image provenance correction
- 409 / Galaxy 2001
- major radial/six-arm families
- historically documented formations with diagrams and field reports
- formations with independent surveys

## Definition of success

A successful decode is not a compelling interpretation.

A successful decode is a compact, falsifiable, replayable generative specification that reproduces measured structure and predicts previously withheld structure better than appropriate nulls.

Promotion target:

ESTABLISHED only after independent reproduction.
