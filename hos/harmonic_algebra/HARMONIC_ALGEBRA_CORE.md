# ASIN-HHC Harmonic Algebra — Operational Core

This module defines the project-specific algebra used to transform ASIN packets into deterministic HOS receipts. It complements the historical specification in `docs/HARMONIC_ALGEBRA_SPEC.md` while tightening the implementation and claim boundary.

## 1. State space

Let a system state be a tuple

```text
S = (A, S_h, I, N, R, E)
```

where:

- `A` is the Anchor: source context and constraints;
- `S_h` is the Shape: task or data structure;
- `I` is the Intention: requested outcome;
- `N ∈ {111, 428, 528, 963}` is a project namespace label;
- `R` is the ordered Rooms trace;
- `E` is the evidence tier.

The numeric labels are identifiers inside the project vocabulary. They do not confer physical, medical, cryptographic, or causal properties.

## 2. Canonicalization operator

```text
C(S) = UTF8(JSON_sort_keys(S))
```

`C` removes serialization ambiguity. The cryptographic seal is:

```text
H(S) = SHA256(C(S))
```

SHA-256, not harmonic notation or resonance scoring, is the integrity primitive.

## 3. HOS state and correction

For measurable vectors, define an ideal state `x*` and observed state `x`:

```text
ΔS = x* - x
E_HOS = 1 / (1 + ||ΔS||₂)
```

Properties:

- `0 < E_HOS ≤ 1`;
- `E_HOS = 1` exactly when `ΔS = 0`;
- the score is a normalized engineering metric, not a claim about consciousness or reality manipulation.

A bounded correction step is:

```text
x_next = x + α · clamp(ΔS, -b, b)
```

with `0 < α ≤ 1` and bound `b > 0`.

## 4. Composition operators

### Sequential composition

```text
P ⊙ Q
```

runs `P`, verifies its receipt, then passes its reviewed output to `Q`. Provenance order is preserved.

### Parallel composition

```text
P ∥ Q
```

runs independent packets and merges only after both receipts verify. Parallel results never silently overwrite one another.

### Projection and trace

```text
Π: artifact → published representation
ι: published representation → source references
```

A round-trip is valid when:

```text
H(source) = H(ι(Π(source)))
```

or when a documented transformation receipt explains an intentional difference.

## 5. Promotion rule

```text
Promote(P) = verified_hash(P)
             ∧ required_evidence(P)
             ∧ human_approval(P)
```

No symbolic score, model confidence, registry entry, or narrative assertion substitutes for these conditions.

## 6. Runtime mapping

- `ASINPacket.validate()` enforces the state domain.
- `canonical_json()` implements `C`.
- `sha256_hex()` implements `H`.
- `process_packet()` emits a receipt with review and evidence metadata.
- `verify_receipt()` replays the hash check.
- `harmonic_state()` and `bounded_correction()` implement the measurable state equations.

## 7. Security boundary

Cryptographic:

- SHA-256 digests;
- deterministic serialization;
- Git commit lineage;
- signed or authenticated storage when configured.

Symbolic/project-semantic:

- the labels 111, 428, 528, and 963;
- glyph mappings;
- Room names;
- harmonic metaphors;
- auxiliary resonance interpretations.

The symbolic layer may organize work, but it has no independent runtime authority.
