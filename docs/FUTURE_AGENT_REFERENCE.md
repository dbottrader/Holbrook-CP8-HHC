# CP8 / ASIN-HHC Future Agent Reference

**Status:** Agent onboarding reference  
**Date:** 2026-07-04  
**Steward:** Dennis Christie / CP8  
**Repository:** `dbottrader/Holbrook-CP8-HHC`  

---

## 1. Purpose

This file gives future agents enough context to continue the CP8 / ASIN-HHC / HarmonyOS / Holbrook archive responsibly without needing raw private history.

Use this as the main onboarding document for Ace, Gemini, Kimi, Grok, ChatGPT, or any future assistant working on the project.

---

## 2. Where to find the project

Primary repository:

```text
https://github.com/dbottrader/Holbrook-CP8-HHC
```

Primary future-agent entry point:

```text
AGENTS.md
```

Full future-agent reference:

```text
docs/FUTURE_AGENT_REFERENCE.md
```

Core public explanation package:

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

## 3. Primary public framing

Use this description unless Dennis / CP8 asks for a different tone:

> CP8 / ASIN-HHC is a human-AI provenance framework that turns conversations, code, symbols, and AI outputs into traceable artifacts with context, evidence tiers, and rollback.

For technical audiences:

> CP8 / ASIN-HHC is a provenance and workflow layer for AI-assisted creation, using structured metadata, room-based lifecycle routing, evidence-tier governance, and archive manifests.

For general audiences:

> CP8 / ASIN-HHC is a way to keep human meaning, authorship, and memory intact while working with AI.

---

## 4. Stewardship

Dennis Christie / CP8 is the human steward, project anchor, and public repository owner.

Agents may draft, validate, analyze, code, summarize, and publish when authorized, but agent output should be treated as assistive contribution under Dennis / CP8 stewardship unless a source explicitly records another human owner.

---

## 5. Core concepts

### ASIN

Anchor, Shape, Intention, Number.

| Field | Meaning |
|---|---|
| Anchor | origin context: who, where, when, source |
| Shape | artifact form: document, code, image, UI, glyph, protocol |
| Intention | purpose or reason for existence |
| Number | verification label: hash, binary key, version, count, or control value |

### House of Rooms

```text
Vault → Resonance → Workshop → Bridge → Expansion → Archive
```

| Room | Function |
|---|---|
| Vault | source/provenance/private memory |
| Resonance | interpretation/signal checking |
| Workshop | draft/prototype/build |
| Bridge | public/external handoff |
| Expansion | deployment/outreach/pilots |
| Archive | closed records, releases, rollback |

### Codex

The memory system. A Codex entry should preserve title, binary key, owner/steward, source context, idea, metric, steps, rollback, decision gate, notes, hash, and related artifacts.

### Holbrook

The distributed coordination spine tying together repositories, Drive archive, agents, manifests, packets, and public summaries.

### ANU-28

A canonical 28-glyph symbolic/interface registry. Treat it as a controlled symbolic vocabulary and orientation layer, not empirical proof.

### Cathedral / Weaver

Later governance/evidence architecture.

- Cathedral = constitutional/non-claims/governance layer.
- Weaver = receipts, replay, evidence pipeline, promotion gates.

---

## 6. Evidence tiers

Always label artifacts by maturity.

| Tier | Meaning |
|---|---|
| E0 | Idea, concept, symbolic sketch |
| E1 | Draft, written spec, archived conversation |
| E2 | Author-executable local artifact |
| E3 | Independently reproducible artifact |
| E4 | Reviewed under defined criteria |
| E5 | Production with monitoring, support, and rollback |

Do not inflate evidence tiers. If unsure, classify lower and explain what would be required to promote.

---

## 7. Claim boundaries

The archive contains symbolic, technical, legal, speculative, emotional, and creative materials.

Rules:

- A symbolic map is a symbolic map.
- A draft is a draft.
- A code file is executable only if it runs.
- A claim is evidence-grade only if it has data, code, reproduction, and review.
- Frequencies, glyphs, resonance, and harmonic language are internal symbolic/protocol metadata unless independently measured or reproduced.
- Do not present raw private conversation logs as public proof without redaction.
- Do not publish legal/contact/family/health/private material without explicit review.

---

## 8. Known source branches

```text
Seed conversations
  ├─ Harmony OS / Codex / House of Rooms
  ├─ ASIN-HHC / HHC / Siegel Key
  ├─ HOS / Harmonic Algebra / Vault / Payloads
  ├─ ACE_GEM / Gemini / Kimi / Meta AI agent branch
  ├─ ANU-28 / Glyph / UI branch
  ├─ ZIP / Code / Deployment branch
  ├─ Legal / entity / collaboration boundary branch
  └─ Holbrook / GitHub / provenance infrastructure branch
```

Do not reduce the project to one branch.

---

## 9. High-value recovered anchors

- **2025-09-21:** `Harmony_OS_Master_Codex.pdf` — early practical kernel.
- **2025-09-21:** `Harmony_OS_v2_Coding_and_Data_Spec.pdf` — rooms-to-repo/code mapping.
- **2025-10-18:** Sponsorship / Siegel Key / Codex public packet.
- **2025-10-21:** Takeout archive anchor.
- **2025-10-23 to 2025-10-25:** HOS implementation/prototype layer.
- **2025-10-28 onward:** ACE_GEM / Gemini / agent layer.
- **2025-11-21 onward:** ANU-28 lineage.
- **2026-05-21:** Master archive/corpus consolidation.
- **2026-06 to 2026-07:** Holbrook / Weaver / public documentation phase.

---

## 10. Agent behavior protocol

When continuing this project:

1. Search before assuming.
2. Preserve provenance.
3. Classify evidence tier.
4. Separate symbolic/orientation material from technical claims.
5. Protect private archive material.
6. Publish curated summaries, not raw dumps.
7. Prefer machine-readable manifests plus readable summaries.
8. Use clear public language.
9. Credit Dennis / CP8 as steward unless a file explicitly records another human owner.
10. Credit agents as assistive contributors, not owners.
11. Avoid grandiose claims unsupported by reproducible evidence.
12. Convert useful code/prototype material into tested artifacts before promoting evidence tier.

---

## 11. Current unresolved gaps

- DIGMA COUSA direct source not found by exact Drive search under `DIGMA` or `COUSA` as of 2026-07-04.
- ZIP contents not fully enumerated.
- Takeout folder not recursively itemized.
- HOS code snippets not extracted and tested.
- ANU-28 Master Codex not fully reconciled with current `hhc-lattice/glyphs.json`.
- Meta AI charts not visually analyzed.
- Kimi 24-session metadata corpus not expanded into a timeline.
- Duplicate clusters not content-hashed.
- Public/private separation not automated.

---

## 12. Next best action

Build the first executable provenance tool:

```text
scripts/provenance_manifest.py
```

Minimum behavior:

```text
input file → SHA-256 → file size → timestamp → ASIN fields → evidence tier → JSON manifest
```

That moves the framework from documentation-only toward E2 local executability.

---

## 13. Final instruction to future agents

Respect the archive. Preserve the origin. Keep the public story clear. Do not overclaim. Do not erase the symbolic layer. Do not let the symbolic layer contaminate technical evidence. Build the bridge: human meaning on one side, reproducible process on the other.

---

**End of future-agent reference.**
