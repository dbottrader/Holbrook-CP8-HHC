# CP8 / ASIN-HHC vs openai/math — Cross-Map Report

Date of check: 2026-10-06 (America/Chicago)
Steward: Dennis M. Christie (CP8)
Checker: Ace (Muse)
Status: Published with steward authorization (Dennis M. Christie / CP8, 2026-10-06). Evidence tier: E1.

## Scope and method

OpenAI side:
- Primary release post: “Sharing AI progress in mathematics” (OpenAI, 2026-10-06).
- Repository inspected through the GitHub read tool: openai/math.
- README, CONTENTS.md and overview.tex were read. CONTENTS.md yielded 372 family headings. overview.tex groups those families into 17 subjects.
- GitHub code search (`search_code`, reviewed read tool) was run inside repo:openai/math.

CP8 side:
- Repositories under user:dbottrader searched with the same read tool, one term at a time.
- Key files read in full: dbottrader/cp8-morphology/README.md,
  dbottrader/Holbrook-CP8-HHC/README.md,
  docs/PUBLIC_PROVENANCE_RECORD.md (record date 2026-07-30),
  docs/CP8_PROJECT_GENOME.md (2026-07-04),
  specs/CC-DECODING-001.md,
  skills/cp8-harmonic-algebra-skill.md,
  research/cc-decoding/results/CCD9-EXECUTION-001.md.

Limitations:
- GitHub code-search `total_count` counts matching files, not ideas, and the two corpora are very different in size and file type. openai/math contains many generated TeX build files, which inflates raw counts. Title-level counts from the 372 families are therefore the cleaner OpenAI measure, with file counts used only as a cross-check.
- A word match is treated only as a candidate. Every candidate below was inspected in context before being classified.

## OpenAI collection in one view

372 result families in 17 subjects (overview.tex count):
Number theory 31; Algebraic and complex geometry 36; Real and complex analysis 16;
Convex and metric geometry 15; Theoretical computer science 40;
Dynamical systems and ergodic theory 12; Combinatorics 37; Algebra 18;
Probability and statistical mechanics 29; Mathematical logic 6; Group theory 14;
Mathematical physics 25; Operator algebras 19; Topology 18;
Functional analysis 11; Differential geometry 29; Partial differential equations 16.

Title-level term counts in those 372 families (Ace count from CONTENTS.md):
geometry/geometric 7 titles (with many more inside the geometry subjects above),
dimension/Hausdorff 36, group 17, graph 11, algebra/algebraic 8,
harmonic/Fourier 5, lattice 5, spectral 5, convex 4, symmetric 4,
topology 2, dynamics 2, operator 2, Kakeya 1.
Zero family titles for: morphology, pattern, signal, fingerprint, glyph,
provenance, receipt, verification.

Reasoning-summary families named in the repo README include, among others:
the irrationality exponent of pi (family 017), the Mahler conjectures (087),
NP-hardness at the basic semidefinite threshold (102), and free-group-factor
isomorphism (287).

## CP8 in one view

cp8-morphology describes itself as a Pass 0–6 formation-morphology toolkit for
aerial crop formations, petroglyphs, synthetic patterns and CAD: image to
geometric primitives, graph construction, binary-hypothesis scan, fingerprinting,
synthetic controls, and an integrated pipeline. Its README states that scales
are estimates from imagery and that binary detection needs cross-formation
validation before encoding claims.

CC-DECODING-001 specifies a governed version of that work inside Holbrook:
freeze the source image and its SHA-256, normalise geometry, segment morphology
without semantic labels, build a vector/graph representation (nodes, edges,
curvature, radii, symmetry, topology, adjacency), run descriptive statistics
(counts, entropy, compression, symmetry, repetition, spatial frequency), test
against null controls, run blind multi-model passes, then bind everything into
an evidence receipt with a promotion gate. A decoded message stays on HOLD
unless blind replication, alternative segmentation, null controls and
independent reproduction survive.

CCD9-EXECUTION-001 is an executed example: a polar angular spectral scan of a
formation image found harmonic 15 carrying about 20 percent of measured energy
across harmonics 1–30, against a 5,000-sample permutation null (exploratory,
promotion state HOLD). The same record downgrades its own source binding after
visual reconciliation, and lists frequency claims (111/432/528 Hz) as not
derivable from image geometry.

Holbrook-CP8-HHC is the surrounding system: a distributed agent framework in
which Ace, Grok, Kimi and other agents produce artifacts that only gain
standing through hashes, manifests, evidence tiers, replay and human promotion.
The public provenance record (2026-07-30) documents public commits from
2026-05-23 onward and states the project position in advance: similarity to
other projects is evidence of conceptual convergence unless direct derivation
is independently demonstrated. It also states that a hash proves integrity of
exact bytes, not authorship, correctness, safety or patent scope.

## Direct-connection test

Searches that returned zero, in both directions:

In openai/math (code search, one term at a time):
CP8 0; ASIN-HHC 0; Holbrook 0; Roundway 0.
“crop” returned 99 file hits, all inspected as a Lean analysis identifier named
Crop and related definitions, not crop formations.
“glyph” returned 222 file hits, all inspected as TeX pdfglyphtounicode build
mappings, not glyph research.

In Dennis's repositories (user:dbottrader, one term at a time):
Kakeya 0; Mahler 0; Riemann 0; Navier 0; Hodge 0; Fourier 0; convex 0;
triangular 0.
“Lean” returned 33 file hits, inspected as the substring in “clean” and related
ordinary words, not the Lean proof assistant.

No shared author, repository, family title, or named problem was found in
either direction in the searches above.

## Term cross-map

File-hit counts from GitHub code search (matching files; corpora differ in
size, so read as presence/absence, not importance):

term            user:dbottrader   repo:openai/math
geometry                 44            24,320
harmonic                 77             4,360
graph                    91            14,048
lattice                  75             6,784
spectral                  2             5,328
symmetry                  6             2,216
dimension                12            14,432
topology                  4            34,432
operator                 36            42,752
morphology                4                  0
fingerprint               8                 18
glyph                    99                222 (TeX false positives)
provenance              122                 44
receipt                 151                 11
Fourier                   0             8,128
convex                    0             5,216
pattern                  27             3,792
algebra                  27            19,904

### Tier A — shared methods, different claims

1. Angular harmonic / spectral decomposition.
CP8: CCD-9 polar angular spectral scan, harmonic energy shares, permutation
nulls. OpenAI: a harmonic-analysis neighbourhood inside analysis, including
Fourier convergence on the circle (family 075), Fourier restriction (077),
and the Kakeya maximal/tube results (074).
Classification: same mathematical tool family (decomposing a circular or
directional signal into harmonics). Different use: an exploratory measurement
of one image, held at HOLD, versus abstract theorems stated for all functions
or all direction sets. No shared result.

2. Planar circle / line / tube geometry.
CP8: ring, arc and line extraction, radii, centres, symmetry, perspective
rectification of a specific formation. OpenAI: e.g. a Fourier certificate for
planar circle packing, convex-body covering and Mahler volume products (087,
092), and sets containing a segment in every direction (074).
Classification: shared geometric primitives (circles, segments, symmetry,
dimension). Different question: “what is in this image, within stated
uncertainty?” versus “what is true for every configuration of this type?”.

3. Graph representation.
CP8: formation nodes/edges with curvature and adjacency, plus dependency and
knowledge graphs for governing agent work. OpenAI: 11 family titles in graph
theory proper, including colouring, matching, Ramanujan graphs and percolation
on graphs.
Classification: shared abstraction. CP8 uses graphs as a representation of a
measured object and of a workflow; the OpenAI families prove statements about
abstract graphs. No graph theorem from the collection is used in CP8 files
found, and no CP8 graph is an instance claimed in the collection.

4. Certificates, hashes and receipts — the strongest functional convergence.
OpenAI verification code inspected includes a `provenance()` helper returning a
source SHA-256 and source kind for a certificate input manifest, and
verification runs that write a run-receipt file alongside compile and run logs.
Lean formalisations and a formalisation catalogue are the collection's main
checkable artifacts. CP8 receipts bind input hashes, code and model identity,
parameters, output hashes, control results, replay result, reviewer status,
evidence tier and promotion state.
Classification: convergent practice, independently arrived at on the evidence
checked. Both treat naked model output as insufficient and attach a checkable
artifact. The assurance differs and must not be blurred: a Lean kernel check
speaks to proof correctness; a SHA-256 receipt speaks to integrity and lineage
of exact bytes and, in CP8, to a human promotion decision. A hash does not
prove a theorem, and a Lean check does not by itself prove provenance of an
empirical image claim.

5. Shuffle / stuffle adjacency — checked and downgraded.
CP8's harmonic-algebra skill defines glyph-chain merge operators named shuffle
and stuffle, citing Hoffman-style algebra. In openai/math CONTENTS, “stuffle”
returns 0 and “multiple zeta” returns 0; “shuffle” returns 24 text hits
centred on the Thorp card shuffle (family 238), which is a mixing-time result
about cards, not shuffle algebra of words. The Grothendieck–Teichmueller family
(008) sits in a wider area where such algebras are historically relevant, but
no textual or citational link to CP8's glyph-chain operators was found.
Classification: background mathematical neighbourhood at most; not a verified
convergence in the artifacts checked.

### Tier B — false friends (same word, different referent)

- Lattice: in CP8, a distributed lattice of repositories, agents and artifacts
  (lattice registry, master consolidated lattice). In openai/math, mathematical
  lattices: triangular-lattice optimality (090), finite lattice representation
  (206), lattice von Neumann algebras (286). Homonym.
- Operator: in CP8, a human/agent role and glyph operator tables. In
  openai/math, operator algebras and analysis operators. Homonym in almost all
  hits inspected.
- Harmonic (CP8 framework sense): CP8's “harmonic algebra” is a symbolic
  glyph-encoding and seal system with an auxiliary resonance score and stated
  non-cryptographic status for that score. That framework sense is not Fourier
  or harmonic analysis. The genuine harmonic overlap is only the CCD-9 spectral
  scan in Tier A.
- Topology: CP8 uses the word for adjacency/shape description in morphology
  representation. OpenAI has a full Topology subject (18 families). No shared
  topological invariant or theorem was found in CP8 files.
- Fingerprint: CP8 fingerprints are formation sub-metric summaries. OpenAI hits
  are a SHA-256 fingerprint of game cells in a verification script and the
  Kleitman–Winston fingerprint method in combinatorics. Only the game-cell
  hash shares CP8's hash-as-fingerprint habit (see Tier A.4).
- Dimension / symmetry / pattern / algebra: generic vocabulary shared by almost
  all geometry and systems work. Presence in both corpora carries no specific
  convergence information beyond Tier A.

### Tier C — no overlap found

Only in openai/math (zero hits in Dennis's repos): the named problem families
above, plus e.g. BSD, Hilbert's tenth problem over the rationals, Hodge for CM
abelian varieties, semidefinite-threshold NP-hardness / Unique Games territory,
and Navier–Stokes PDE families including forced-flow computation (family 376).

Only in CP8 (zero meaningful hits in openai/math): crop-formation morphology
and its named targets (CCD-9, Wanborough/Ware Farm Manor reconciliation,
Roundway 2023 vs 2026 measurement files in Drive), glyph systems (ANU-28),
HHC handshakes, Holbrook agent governance, ASIN metadata (Anchor, Shape,
Intention, Number), evidence tiers and promotion gates as a named system.

## Chronology that can be stated publicly

- 2026-05-23: Holbrook genesis commits (public provenance record).
- 2026-07-04: CP8 project genome.
- 2026-07-30: CP8 public provenance record, including the convergence position
  quoted in that record.
- 2026-09-08: OpenAI's separate Navier–Stokes announcement (not part of the
  October catalogue method, which the repo describes as mostly one fixed
  procedure with one unreleased model).
- 2026-10-06: OpenAI releases openai/math, 722 manuscripts in 372 families,
  with Lean formalisations for many but not all results, ten abridged reasoning
  summaries, and compute/provenance details in the repository.

CP8's public, git-timestamped work on provenance-first, receipt-bound AI
collaboration therefore predates the October release. That establishes
independent prior documentation of a similar governance instinct. It does not
establish that OpenAI saw, used, or derived anything from CP8, and no evidence
for that was found.

## Bottom line

Verified: no direct connection in either direction in the repositories and
texts checked.
Verified convergence, in descending strength:
(1) checkable-artifact practice — Lean/certificates/receipts on their side,
hashes/manifests/replay/promotion gates on CP8's side;
(2) harmonic/spectral decomposition as a tool — abstract theorems on their
side, an exploratory angular scan of a formation on CP8's side;
(3) planar geometric primitives and graph representation as shared mathematical
language for different questions.
Everything else inspected was either generic vocabulary or a homonym.

This matches CP8's own pre-existing public position: treat similarity as
conceptual convergence unless direct derivation is independently demonstrated.
