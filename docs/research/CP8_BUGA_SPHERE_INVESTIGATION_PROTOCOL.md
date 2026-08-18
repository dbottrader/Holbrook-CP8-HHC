# CP8 Buga Sphere Investigation Protocol

## Purpose

Evaluate Buga sphere specimens as a forensic artifact set using reproducible measurements, provenance tracking, comparative geometry, materials data, and competing-hypothesis testing.

The protocol does **not** assume terrestrial, extraterrestrial, fabricated, natural, or experimental origin. Origin is an output classification, not an input assumption.

## 1. Specimen Separation

Every physical sphere receives an independent identifier.

Required fields:

- Specimen ID
- Discovery/recovery location
- Discovery date/time
- First documented custodian
- Complete custody sequence
- Mass measurements with date/device
- Diameter/circumference measurements with date/device
- Photograph/video references
- Laboratory examinations
- Sampling/destructive-testing history

No measurement from one specimen may be transferred to another.

## 2. Evidence Classes

Every datum receives one evidence type:

- **OBSERVED** — directly visible or instrument-recorded.
- **MEASURED** — quantitative result with method/device identified.
- **REPORTED** — attributed measurement without underlying primary record.
- **DERIVED** — mathematically calculated from observed/measured inputs.
- **INFERRED** — interpretation supported by several observations.
- **HYPOTHESIS** — proposed explanation awaiting discrimination.
- **DISCONFIRMING** — evidence contradicting an active hypothesis.

No category may silently promote itself into another.

## 3. Surface Geometry Capture

For each specimen record:

- Diameter
- Circumference
- Sphericity
- Surface curvature
- Shell irregularity
- Groove depth
- Groove width
- Marking orientation
- Angular separation between markings
- Marking-to-marking distances

Where possible, use calibrated photogrammetry or 3D scanning.

### Growth Test

For measurements at times t0...tn:

`G_D(t) = (D_t - D_0) / D_0`

Also calculate:

- Mass ratio
- Volume ratio
- Inferred average-density ratio
- Glyph-spacing ratio
- Groove-width ratio

If the object physically expands, the markings provide surface fiducials that can distinguish uniform, anisotropic, localized, or apparent growth.

## 4. Glyph / Marking Analysis

Treat markings first as geometry.

Primitive extraction:

- arcs
- straight segments
- junctions
- loops
- bifurcations
- radial structures
- rotational repetitions
- mirrored structures
- isolated marks

Convert each marking field into a graph.

### Nodes

- intersections
- endpoints
- curvature extrema
- branching points

### Edges

- continuous engraved paths

### Edge attributes

- length
- curvature
- orientation
- width
- depth
- confidence

## 5. Grammar Vector

Each surface region receives a standardized grammar vector:

`G = [AFG, NSG, LRG, BFG, FCG, SYM, ENT]`

Where:

- **AFG** — arc/flow organization
- **NSG** — node/junction density
- **LRG** — loop/recursion frequency
- **BFG** — branching/fan topology
- **FCG** — fracture/discontinuity structure
- **SYM** — rotational/reflection symmetry
- **ENT** — directional/topological entropy

These labels are computational feature classes; they do not imply semantic meaning.

## 6. Cross-Specimen Similarity

For specimens Si and Sj, compute:

- Euclidean feature distance
- Cosine similarity
- Graph-edit distance
- Motif recurrence
- Symmetry-family overlap
- Spatial-layout similarity

Create a pairwise similarity matrix.

### Shared-generator criterion

A common generating process becomes increasingly plausible when independent specimens show convergence in:

- grammar vector
- recurring motifs
- construction order
- angular relationships
- groove morphology
- internal architecture
- material composition

Similarity must exceed control objects produced by known manufacturing methods.

## 7. Fabrication Signature Analysis

Test explicitly against:

- CNC machining
- rotary engraving
- laser etching
- casting
- additive manufacturing
- hydroforming
- welded shell construction
- hand engraving
- abrasive processing
- composite fabrication

Search for:

- cutter-entry marks
- tool chatter
- heat-affected zones
- weld seams
- repeated pitch
- indexing artifacts
- machining periodicity
- casting porosity
- adhesive interfaces
- layer boundaries

Do not infer fabrication technique solely from visual resemblance.

## 8. Internal Structure

Preferred evidence:

1. Raw CT/DICOM
2. Industrial radiography
3. Ultrasound
4. Neutron imaging if available
5. Sectioning/destructive inspection only when justified

Record:

- shell thickness
- nested layers
- cavities
- internal bodies
- attachment interfaces
- density gradients
- symmetry
- center-of-mass offset

Compare internal architecture against external marking coordinates.

A reproducible correspondence between internal nodes and external markings would be a high-value result.

## 9. Materials Investigation

Preferred analyses:

- XRF
- SEM
- EDS/EDX
- XRD
- ICP-MS
- metallography
- isotope-ratio analysis
- Raman/FTIR for polymers or residues

Preserve:

- raw spectra
- calibration data
- laboratory identity
- equipment model
- detection limits
- sample preparation
- chain of custody

## 10. Temporal Change Protocol

Because mass and dimensional changes have been reported, every repeated measurement must include:

- timestamp
- environmental temperature
- atmospheric pressure
- humidity
- scale model/calibration
- orientation
- measurement procedure
- photographic record

Test separately:

- **H-T1:** mass changes while geometry remains constant.
- **H-T2:** geometry changes proportionally with mass.
- **H-T3:** local surface regions deform.
- **H-T4:** apparent change is caused by measurement or specimen mismatch.

## 11. Competing Origin Hypotheses

Maintain simultaneously:

- **H1 — Conventional fabricated object**
- **H2 — Specialized/experimental human technology**
- **H3 — Natural or geological process**
- **H4 — Composite/modified artifact**
- **H5 — Unknown engineered origin**
- **H6 — Non-human technological origin**

No hypothesis receives privileged treatment.

For every new observation record:

- supports
- contradicts
- neutral
- discriminatory value

## 12. Controls

Create matched control datasets from:

- commercially machined spheres
- welded hollow spheres
- cast-metal spheres
- laser-engraved spheres
- CNC-engraved spheres
- hand-engraved spheres
- naturally weathered spherical objects

The Buga specimens must outperform these controls before unusual structural claims are promoted.

## 13. CP8 Evidence Promotion

- **E1 — Observation:** Documented datum exists.
- **E2 — Local verification:** Measurement reproduced on same specimen.
- **E3 — Reproduction:** Independent operator/lab reproduces result.
- **E4 — Cross-method verification:** Different measurement technique confirms result.
- **E5 — Independent ecosystem verification:** Multiple independent teams reproduce the phenomenon with accessible evidence and controls.

**No receipt = no promotion.**

## 14. Mandatory Null Tests

Before interpreting a pattern:

- perspective correction
- image-compression artifact check
- lighting/shadow control
- lens-distortion correction
- duplicate/specimen mismatch check
- random-pattern comparison
- known-manufacturing comparison

## 15. Marking-Decipherment Gate

Semantic interpretation begins **only after** structural extraction.

`IMAGE -> GEOMETRY -> VECTOR GRAPH -> MOTIFS -> GRAMMAR -> CROSS-SPECIMEN TEST -> SEMANTIC HYPOTHESES`

Candidate translations must produce predictions.

Example: if a glyph is interpreted as a spatial operator, the interpretation must predict where another feature should occur on portions of the sphere not used to derive the translation.

## 16. Falsification Requirement

Every major interpretation must state what would defeat it.

Examples:

- **Shared-generator hypothesis fails if** independent specimens do not preserve grammar/motif relationships after geometric normalization.
- **Physical-growth hypothesis fails if** calibrated repeat measurements remain constant.
- **Encoded-marking hypothesis weakens if** marking statistics are indistinguishable from known engraving/toolpath controls.
- **Unknown-material hypothesis fails if** independent spectroscopy reproduces ordinary commercial alloys within tolerance.

## 17. Provenance Ledger

Every artifact receives:

```text
artifact_id
specimen_id
source
capture_date
acquisition_method
sha256
evidence_class
confidence
dependencies
supersedes
notes
```

Never overwrite evidence. Corrections create new records linked to the original.

## 18. Immediate Research Priority

1. Establish definitive specimen registry.
2. Recover highest-resolution original sphere imagery.
3. Establish dated physical measurements.
4. Isolate and vectorize every external marking.
5. Recover CT/X-ray primary data.
6. Obtain materials reports and raw spectra.
7. Compare confirmed original specimen against known manufactured/control spheres.
8. Build cross-sphere grammar vectors.
9. Test for shared generator.
10. Only then attempt semantic decipherment.

## CP8 Closure Rule

The target is not a predetermined answer.

The target is:

> **The smallest model that explains the largest number of independently reproduced observations while surviving the strongest available controls.**

**Reality retains veto.**
