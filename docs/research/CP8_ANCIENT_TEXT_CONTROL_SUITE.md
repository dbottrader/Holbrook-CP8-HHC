# CP8 Ancient Text Control Suite

## Purpose
Extend PR #27 with adversarial controls that distinguish real structural recovery from plausible-looking interpretation.

## Model classes under test
1. **Substitution** — symbols encode letters, phonemes, syllables, or words.
2. **Compositional/operator** — symbols encode states, operators, relations, polarity, or transformations whose adjacency/ordering composes meaning.
3. **Null/projection** — apparent grammar is produced by visual resemblance, prior knowledge, or model narrative completion rather than encoded structure.

## Required control sets
### A. Known ancient-text ground truth
Held-out damaged Greek/Latin/cuneiform examples with accepted restorations.

### B. Synthetic compositional messages
Novel glyph sequences generated from a fixed grammar with withheld intended meaning. Evaluators receive either raw sequence only or grammar only, never both plus the answer.

### C. Order-shuffled controls
Randomly permute sequence order while preserving exact symbol multiset and frequency. A genuine order-sensitive grammar should lose predictive power under this intervention.

### D. Mixed-Unicode control corpus
Use the 17-glyph control sequence documented in the uploaded Unicode analysis. Preserve official Unicode identity where known. Do not treat shape similarity as semantic equivalence.

Control facts frozen from source artifact:
- 17 glyphs, not 18.
- `ꗃ` U+A5C3 = VAI SYLLABLE BO.
- `⟡` U+27E1 and `⟢` U+27E2 have inherited mathematical/modal-logic semantics and form a documented relational pair.
- `⧖` / `⧗` and `⧈` / `⧉` are externally named related symbol pairs.

The purpose is not to prove the control string contains a hidden message. It is to test whether the pipeline fabricates structure from heterogeneous symbols with familiar visual or historical associations.

### E. Geometry-matched random controls
Generate or sample glyph-like marks with matched stroke count, curvature, symmetry, junction count, and density but no intended semantic grammar.

## Primary discrimination metric: shuffle degradation
For each method M:

`shuffle_degradation = score(original) - score(shuffled)`

A method that detects genuine sequential grammar should show substantial positive degradation when order is destroyed while symbol frequencies remain fixed.

If performance remains stable after shuffling, semantic recovery is likely being driven by symbol identity or interpretive flexibility rather than sequence grammar.

## Metrics
Report for every condition:
- semantic recovery score
- operator/relation recovery
- top-1 accuracy where ground truth exists
- promoted precision
- coverage
- Brier score
- expected calibration error
- HOLD/abstention rate
- cross-agent agreement
- shuffle degradation
- unsupported-confidence rate

## Blind-agent protocol
### Phase 1 — Raw sequence
Independent evaluator receives only raw glyph/text sequence and provenance-blind sample ID.

### Phase 2 — Grammar-only transfer
Independent evaluator receives the formal grammar and a novel sequence, but not the intended meaning.

### Phase 3 — Encode/decode transfer
Agent A encodes a novel concept under the grammar. Agent B receives only the encoded sequence and grammar. Score semantic recovery against a preregistered rubric.

### Phase 4 — Stress/generalization
Introduce unseen but systematically related operators/modifiers and test whether independent evaluators infer compatible extensions without retraining on the target message.

## Promotion rule
No candidate grammar or decipherment is promoted solely because it produces a coherent narrative.

Promotion requires:
1. performance above matched null controls;
2. positive order/shuffle sensitivity when order is claimed to matter;
3. non-trivial cross-agent convergence;
4. calibration within preregistered bounds;
5. provenance-complete evidence nodes;
6. replication on held-out examples.

Otherwise: **HOLD**.

## Discovery criterion
A candidate unknown-script grammar becomes a research result only if it predicts withheld structure or restorations significantly better than frequency-, geometry-, and semantics-matched controls.

## Falsification criteria
The structural-decipherment hypothesis is weakened or rejected if any of the following occur:
- shuffled sequences perform comparably to originals;
- random geometry controls receive similar semantic coherence scores;
- cross-agent agreement disappears under blinding;
- confidence remains high on known-invalid controls;
- gains vanish at matched coverage;
- the method depends on leaked provenance or intended meaning.

## Evidence OS mapping
Use the existing CP8 evidence states:
- T0: narrative/speculative interpretation
- T1: located artifact
- T2: hash-pinned artifact
- T3: protocol-validated result

No decipherment result reaches T3 without a frozen dataset, protocol version, hashes, outputs, and passing receipt.

## Immediate execution order
1. Freeze the Unicode 17-glyph control artifact and hash it.
2. Generate order-shuffled and geometry-matched controls.
3. Add held-out Ithaca-compatible examples with known restorations.
4. Run single-model baseline.
5. Run CP8 fusion/abstention pipeline.
6. Run blind structural grammar lane.
7. Compare original vs shuffled vs null controls.
8. Publish full negative and positive results.

## Boundary
This suite tests whether CP8 can discriminate recoverable encoded structure from model projection. It does not assume that any unknown artifact, inscription, crop-circle glyph set, or Unicode sequence carries a hidden message.