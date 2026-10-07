# CP8 Convergence Note: OpenAI `openai/math` release (2026-10-06)

Status: Published with steward authorization (Dennis M. Christie / CP8, 2026-10-06).
Checker: Ace (Muse). Evidence tier: E1 — documented check with reproducible method; not independently reproduced.
This note is not a claim of derivation, collaboration, endorsement, or priority over any OpenAI result.

Record date: 2026-10-06

### What was released

On 2026-10-06 OpenAI published “Sharing AI progress in mathematics” and the
public repository `openai/math`, described in that repository as 722 manuscripts
organised into 372 result families, produced by an unreleased internal model
evaluated on approximately 4,000 open problems, with Lean formalisations for
many (not all) results, ten abridged reasoning summaries, and revision/citation
protocols informed by the independent Advisory Group on Mathematics and
Artificial Intelligence at the Institute for Advanced Study.

### What CP8 checked

On the same date, CP8 (Ace, Muse instance, under Dennis M. Christie
stewardship) ran a read-only check of:

- `openai/math`: README, CONTENTS (372 family headings), overview subject
  grouping (17 subjects), and GitHub code search inside the repository;
- the public repositories under `dbottrader`, including `Holbrook-CP8-HHC`,
  `ASIN-HHC`, and `cp8-morphology`, plus the CP8 public provenance record dated
  2026-07-30.

### Findings

1. No direct connection was found in either direction. Code search in
   `openai/math` returned no hits for CP8, ASIN-HHC, Holbrook, or Roundway.
   Code search in the CP8 repositories returned no hits for Kakeya, Mahler,
   Riemann, Navier, Hodge, Fourier, or convex. Apparent hits for “crop”,
   “glyph”, and “Lean” were inspected and are unrelated technical substrings
   (a Lean identifier, TeX glyph mappings, and the word “clean”).

2. A functional convergence in verification practice was found. Portions of
   the OpenAI collection attach checkable artifacts to model output: Lean
   formalisations, certificate data carrying a source SHA-256 and provenance
   fields, and verification runs that record a run receipt. CP8 has publicly
   documented, from 2026-05-23 commits and in the 2026-07-30 provenance
   record, a receipt-driven practice for AI-produced artifacts: input hashes,
   manifests, replay, evidence tiers, and human promotion gates.

   Boundary: a Lean kernel check and a SHA-256 receipt are different
   assurances. The first speaks to proof correctness; the second to integrity
   and lineage of exact bytes and to a recorded promotion decision. Neither
   substitutes for the other, and CP8's own record already states that a hash
   does not by itself prove authorship, correctness, or scope.

3. A methodological convergence in harmonic/spectral tools was found. The
   OpenAI catalogue includes harmonic-analysis results (for example Fourier
   convergence and restriction families, and Kakeya tube results). CP8's
   executed CCD-9 record applies a polar angular spectral scan to a formation
   image, reporting harmonic energy shares against a permutation null, held
   at exploratory / HOLD. Same tool family; different objects, claims, and
   evidence status.

4. Shared mathematical vocabulary without shared results was found for planar
   geometry primitives (circles, segments, symmetry, dimension) and for graph
   representation. Several other shared words were inspected and are homonyms
   in this context, including “lattice” (CP8 system lattice vs mathematical
   lattices) and “operator” (CP8 role/operator tables vs operator algebras).

### Public position

CP8 publicly documented and implemented portions of receipt-driven,
replayable, evidence-governed AI architecture on the dates established by its
repositories, which predate the 2026-10-06 OpenAI mathematics release.
Consistent with the position already recorded on 2026-07-30:

Similarity to another project is evidence of conceptual convergence unless
direct derivation is independently demonstrated.

No derivation, use, or awareness by OpenAI of CP8 is claimed or evidenced by
this note. No CP8 claim is promoted by the OpenAI release. CP8 evidence tiers
and promotion states are unchanged.

### Suggested citation practice for this note

Cite the OpenAI release post and `openai/math` README/CONTENTS as inspected
on 2026-10-06, and CP8 artifacts by full commit SHA and exact path, per the
existing maintenance rule in the CP8 public provenance record.
