# CP8 / ASIN-HHC — Public Important Parts Release

**Status:** Curated public release  
**Date:** 2026-07-04  
**Steward:** Dennis Christie / CP8  
**Repository:** `dbottrader/Holbrook-CP8-HHC`  

---

## 1. Why this release exists

The full CP8 / ASIN-HHC / HarmonyOS archive contains conversations, legal drafts, agent logs, code prototypes, screenshots, PDFs, ZIPs, corpora, and symbolic material. Publishing everything raw would make the work harder to understand and would mix public architecture with private archive data.

This release publishes the important parts in a filtered, public-safe form:

- the architecture;
- the timeline;
- the evidence model;
- the contribution map;
- the source branches;
- the project vocabulary;
- the public explanation;
- the next engineering path.

Raw private conversations, legal packets, contact details, and sensitive Takeout material remain source evidence, not public payload.

---

## 2. Public core statement

CP8 / ASIN-HHC is a human-AI provenance and workflow framework. It turns conversations, code, symbols, AI outputs, and project files into traceable artifacts with context, versioning, evidence tiers, and rollback.

The project began as a practical continuity problem: useful work was being created across AI tools, chats, files, prototypes, and images, but there was no stable way to preserve origin, intent, authorship, status, or next action.

The answer became a system:

```text
Idea → Anchor → Shape → Intention → Number → Codex → Review → Publish or Archive
```

---

## 3. What matters most

### 3.1 Provenance before claims

The most important contribution is not a single glyph, phrase, or interface. It is the insistence that AI-assisted work should preserve its creation path.

Every artifact should answer:

- Who created or stewarded it?
- What source did it come from?
- What was the intent?
- What version is it?
- What changed?
- What evidence tier does it belong to?
- Can it be reproduced, reviewed, or rolled back?

### 3.2 Human-centered AI

The system keeps the human operator at the center. Agents help draft, validate, translate, build, summarize, and review, but the human steward remains responsible for direction and publication.

### 3.3 Evidence boundaries

The archive contains symbolic, technical, legal, and speculative material. The public system must not flatten those into one claim type.

A symbolic map can be valuable as a map. A code file can be valuable as executable work. A reviewed artifact can be evidence. These should be labeled differently.

### 3.4 UI-first accessibility

The project repeatedly favors single-file HTML tools, visual maps, dashboards, glyph cards, and phone-friendly workflows. This is not cosmetic. It is a design constraint: make complex AI work understandable from limited devices.

### 3.5 Reversibility

A repeated early principle is that changes should be reversible. This appears in the Codex, House-of-Rooms workflow, repository mapping, rollback tests, archive room, and evidence promotion logic.

---

## 4. The five public layers

### Layer 1 — Codex memory

The Codex stores structured entries: title, binary key, owner, context, idea, metric, steps, rollback, decision gate, notes, and artifact links.

### Layer 2 — ASIN metadata

ASIN means Anchor, Shape, Intention, Number. It is a metadata header for human-AI artifacts.

### Layer 3 — House of Rooms

The House of Rooms is the workflow lifecycle:

```text
Vault → Resonance → Workshop → Bridge → Expansion → Archive
```

### Layer 4 — Evidence tiers

Artifacts are labeled from idea to production:

```text
E0 Idea → E1 Draft → E2 Local → E3 Reproducible → E4 Reviewed → E5 Production
```

### Layer 5 — Distributed archive

Holbrook ties together GitHub, Google Drive, Takeout, agents, manifests, packets, and public summaries into a coordinated archive.

---

## 5. What is public now

This repository now contains a public-safe explanation package:

| File | Purpose |
|---|---|
| `docs/PUBLIC_PRESENTATION_BRIEF.md` | First thing to show people |
| `docs/PUBLIC_IMPORTANT_PARTS_RELEASE.md` | This curated release |
| `docs/CP8_PROJECT_GENOME.md` | Full narrative reconstruction |
| `docs/GLOSSARY.md` | Plain-language definitions |
| `docs/CP8_HISTORICAL_ARCHIVE_INDEX.md` | Historical source index |
| `docs/NO_STONE_UNTURNED_AUDIT_PROTOCOL.md` | Recovery protocol |
| `docs/SOURCE_DISCOVERY_LOG_2026-07-04.md` | Search/discovery log |
| `manifests/cp8-historical-archive.json` | Machine-readable archive manifest |
| `hhc-lattice/glyphs.json` | Canonical ANU-28 v2.0 registry |

---

## 6. What is intentionally not dumped raw

The following remain indexed but not raw-published:

- full ChatGPT exports;
- full Master AI Corpus;
- Google Takeout contents;
- legal/entity packets;
- NDA/collaborator files;
- private family/health/legal messages;
- unredacted contact information;
- agent logs containing sensitive internal/private statements;
- raw ZIP contents until enumerated and hashed.

This is not hiding the work. This is responsible publishing.

---

## 7. What a reviewer should evaluate

A reviewer should focus on:

1. Does the framework solve a real provenance/workflow problem?
2. Are the terms clear enough for a third-party builder?
3. Are evidence tiers applied consistently?
4. Are symbolic layers properly separated from technical claims?
5. Are manifests useful and machine-readable?
6. Can the next executable tool promote the project from E1 to E2?
7. Can the archive be safely expanded without exposing private data?

---

## 8. The public invitation

Builders do not need to adopt the symbolic layer to use the system.

They can adopt:

- ASIN headers;
- Codex entries;
- evidence tiers;
- room-based artifact routing;
- provenance manifests;
- rollback rules;
- public/private separation;
- agent contribution logs.

That is the practical adoption path.

---

## 9. The best public summary

> CP8 / ASIN-HHC is a human-AI project operating system for provenance, continuity, and responsible publication. It helps preserve where an idea came from, what it became, who contributed, what evidence tier it belongs to, and whether it can be reproduced or rolled back.

---

## 10. Next engineering step

The next public artifact should be executable:

```text
scripts/provenance_manifest.py
```

Minimum function:

```text
input file → SHA-256 → file size → timestamp → ASIN fields → evidence tier → JSON manifest
```

That would move the core tooling from documentation-only into local executable form.

---

**End of curated public release.**
