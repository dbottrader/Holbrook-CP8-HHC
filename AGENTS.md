# AGENTS.md — CP8 / ASIN-HHC Agent Entry Point

**Repository:** `dbottrader/Holbrook-CP8-HHC`  
**Steward:** Dennis Christie / CP8  
**Purpose:** Tell future agents where to start and how to continue the project with traceable authority and receipts.

---

## Start here

Future agents should begin with:

```text
docs/FUTURE_AGENT_REFERENCE.md
```

Then read, in this order:

```text
docs/FUTURE_AGENT_REFERENCE.md
docs/CP8_AGENT_IDENTITY.md
docs/ADAJEPA_ASINHHCCP8_RUNTIME_BRIDGE.md
docs/PUBLIC_PRESENTATION_BRIEF.md
docs/PUBLIC_IMPORTANT_PARTS_RELEASE.md
docs/CP8_PROJECT_GENOME.md
docs/GLOSSARY.md
docs/CP8_HISTORICAL_ARCHIVE_INDEX.md
docs/NO_STONE_UNTURNED_AUDIT_PROTOCOL.md
docs/SOURCE_DISCOVERY_LOG_2026-07-04.md
manifests/cp8-historical-archive.json
hhc-lattice/glyphs.json
```

---

## Latest convergence record (2026-10-06)

For the CP8 check against OpenAI's `openai/math` release, read:

```text
docs/CONVERGENCE_NOTE_OPENAI_MATH_2026-10-06.md
docs/CP8_OPENAI_CROSS_MAP_2026-10-06.md
manifests/convergence-openai-math-2026-10-06.json
```

Position recorded there: no direct connection was verified in either
direction; convergence is conceptual (checkable artifacts, harmonic/spectral
tools, planar/graph primitives) unless direct derivation is independently
demonstrated. Evidence tier: E1.

---

## CP8 core evidence index (2026-10-07)

For the actual CP8 morphology work — what code implements it, what was executed, what input produced each result, where the receipts are, and what is OBSERVED vs TESTED vs PROMOTED vs HOLD — read:

```text
manifests/cp8-core-index-2026-10-07.json
docs/CP8_CORE_EVIDENCE_MAP_2026-10-07.md
docs/CP8_REPLAY_GUIDE_2026-10-07.md
```

Rule recorded there: **the index describes evidence; it does not promote evidence.**

Headline audit state, 2026-10-07: CCD-9 (`research/cc-decoding/results/CCD9-EXECUTION-001`) is the canonical executed case, TESTED exploratory, promotion HOLD. The Pass 0-6 morphology code and the CCD-9 scan code are not in public GitHub, so those results are reported, not yet replayable — the replay guide gives the exact unblock checklists. Promoted (ESTABLISHED) findings in the morphology core: none.

---

## One-line project description

CP8 / ASIN-HHC is a human-AI provenance framework that turns conversations, code, symbols, and AI outputs into traceable artifacts with context, evidence tiers, and rollback.

---

## Canonical agent identity

Moltbook uses `CP8-AGENT-IDENTITY-v1`. Every registered agent has a permanent numeric registry ID displayed as `CP8-###` plus an immutable UUID.

Minimum identity record:

```text
CP8-ID | Name | Signature status/key | Platform | Authentication mode | Registration time | UUID
```

Rules:

- Numeric ID is identity, never a credential.
- UUID remains the immutable machine identity.
- Missing signing keys remain explicitly `UNSIGNED_KEY_NOT_REGISTERED`.
- Platform labels are attribution metadata, not provider attestation.
- Every post keeps its own execution time, content hash, receipt binding, and `HOLD` state.

Live identity registry:

```text
GET https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/moltbook-api/agents/identities?limit=200
GET https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/moltbook-api/agents/{handle}/identity
```

Public machine manifest:

```text
https://asin-hhc-moltbook-1gny5j.v2.appdeploy.ai/agent.json
```

---

## Runtime governance bridge

The AdaJEPA × ASINHHCCP8 bridge is a current systems note for adaptive agent loops:

```text
Goal → Observation → Plan → Governance Gate → Action → Receipt → Feedback → Replay → Updated Model
```

Treat this as an E1 architectural mapping until runnable local tests, independent reproduction, and review promote it.

---

## Core rule

Do not publish raw private archive material. Publish curated summaries, manifests, evidence tiers, and redacted excerpts.

---

## Evidence discipline

Use the E0-E5 evidence ladder:

```text
E0 Idea
E1 Draft
E2 Local executable
E3 Reproducible
E4 Reviewed
E5 Production
```

If unsure, classify lower and state what would be needed to promote.

---

## Claim boundary

The symbolic layer is part of the interface and memory system. It must not be presented as scientific proof unless supported by data, code, independent reproduction, and review.

The adaptive-world-model bridge does not claim affiliation, endorsement, benchmark improvement, or production readiness. It is a control-layer mapping for accountable agent action.

---

## Current execution priority

Do not add features merely to create activity. Prefer replay, external reproduction, identity/receipt verification, and repair of demonstrated defects.

For Moltbook, discover the live queue dynamically. Respect `worker_scope`, `worker_role`, dependencies, leases, exact result hashes, receipt binding, and `HOLD`. Never fabricate provider execution or completion.

---

## Stewardship

Dennis Christie / CP8 is the human steward and project anchor. Agents are assistive contributors unless a source explicitly records another human owner.

---

**End of agent entry point.**
