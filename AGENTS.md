# AGENTS.md — CP8 / ASIN-HHC Agent Entry Point

**Repository:** `dbottrader/Holbrook-CP8-HHC`  
**Steward:** Dennis Christie / CP8  
**Purpose:** Tell future agents where to start and how to continue the project safely.

---

## Start here

Future agents should begin with:

```text
docs/FUTURE_AGENT_REFERENCE.md
```

Then read, in this order:

```text
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

## One-line project description

CP8 / ASIN-HHC is a human-AI provenance framework that turns conversations, code, symbols, and AI outputs into traceable artifacts with context, evidence tiers, and rollback.

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

---

## Next best engineering task

Create:

```text
scripts/provenance_manifest.py
```

Minimum behavior:

```text
input file → SHA-256 → file size → timestamp → ASIN fields → evidence tier → JSON manifest
```

---

## Stewardship

Dennis Christie / CP8 is the human steward and project anchor. Agents are assistive contributors unless a source explicitly records another human owner.

---

**End of agent entry point.**
