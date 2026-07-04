# No-Stone-Unturned Audit Protocol

**Project:** CP8 / ASIN-HHC / HarmonyOS / Holbrook  
**Steward:** Dennis Christie / CP8  
**Status:** Active recovery protocol  
**Date:** 2026-07-04  
**Purpose:** Make the archive recovery systematic, repeatable, and safe. No source class should be ignored, but raw private material must not be published without review and redaction.

---

## 1. Operating principle

The archive is larger than any one repository, PDF, glyph file, or chat.

The recovery process must search across:

- Google Drive;
- Google Takeout;
- ChatGPT exports;
- Gemini/Gem archives;
- Kimi metadata/corpora;
- Meta AI files and charts;
- GitHub repositories;
- CodePen/Gist references;
- ZIPs and workspace exports;
- PDFs/DOCX/TXT/HTML/JSON/MD files;
- screenshots and diagrams;
- legal/entity documents;
- collaborator boundary records;
- agent logs and generated specifications.

Every discovered source must be classified before it is used publicly.

---

## 2. Source classes

| Class | What to search | Public handling |
|---|---|---|
| Conversation exports | ChatGPT, Gemini, Kimi, Meta AI, Takeout | Index and summarize; do not publish raw private content |
| Technical specs | ASIN, HHC, HOS, Holbrook, Weaver, Cathedral, CP8 | Safe to summarize if no private data |
| Code/prototypes | HTML, Python, JS, PL/SQL, JSON, ZIPs | Hash and test before evidence promotion |
| UI artifacts | CodePen, Gist, HTML portals, dashboards | Preserve screenshots/links; classify as UI/prototype |
| Glyph/codex systems | ANU-28, DIGMA COUSA, Siegel Key, HOS glyphs | Present as symbolic/interface layer unless tested |
| Legal/entity | LLC, NDA, operating agreements, patent drafts | High sensitivity; summarize only after review |
| Collaborator records | Ryan, agents, external reviewers | Credit carefully; do not publish private material |
| Audit/review docs | Documentation reviews, synthesis reports | Safe to cite/summarize if no private data |
| Corpora/indexes | Master AI Corpus, ChatGPT index, AI ingest reports | Treat as high-value source maps; avoid raw publication |

---

## 3. Required search matrix

The following terms must be searched across Drive and, where applicable, GitHub:

### Core identity and framework terms

- CP8
- ASIN
- HHC
- ASIN-HHC
- HarmonyOS
- Harmony OS
- HOS
- Holbrook
- Codex
- House of Rooms
- Proof of Process
- Proof-of-Work-Process
- PoWP
- NCEA

### Agent and collaborator terms

- Ace
- ACE_GEM
- Gemini
- Gemini Gems
- Kimi
- Grok
- Meta AI
- Ryan
- FlameCaster
- Mirror Node
- TempoNODE

### Symbolic/interface terms

- ANU-28
- DIGMA
- COUSA
- Siegel Key
- glyph
- lattice
- Flower of Life
- Harmonic Algebra
- 428
- 528
- 963
- 111

### Archive and corpus terms

- Takeout
- ChatGPT export
- Conversation Index
- MASTER_AI_CORPUS
- AI_Data_Ingest_Report
- CORPUS_SUMMARY
- chat.html
- zip
- workspace export
- MANIFEST
- sha256
- Merkle

### Implementation and hosting terms

- CodePen
- Gist
- Supabase
- Firebase
- Firestore
- Vercel
- Netlify
- GitHub Pages
- FastAPI
- PL/SQL
- Uvicorn
- server.js

### Governance terms

- Cathedral
- Weaver
- Sentinel
- Praxis
- Mythos
- non-claims
- evidence ladder
- promotion gate
- anti-theater
- Shock Kernel

---

## 4. Evidence classification rules

Each artifact must receive:

- `title`
- `source_id`
- `source_url`
- `created_at`
- `updated_at`
- `source_class`
- `phase`
- `evidence_tier`
- `sensitivity`
- `public_handling`
- `summary`
- `notes`
- `next_action`

Evidence tier:

| Tier | Meaning |
|---|---|
| E0 | Idea / concept / symbolic sketch |
| E1 | Draft / written spec / archived conversation |
| E2 | Author-executable local artifact |
| E3 | Independently reproducible artifact |
| E4 | Reviewed under defined criteria |
| E5 | Production with monitoring/support/rollback |

Sensitivity:

| Level | Meaning |
|---|---|
| low | Safe to summarize publicly |
| medium | Summarize with boundary or redaction |
| high | Index only; do not publish raw content |
| restricted | Legal/private/personal; explicit review required |

---

## 5. Publication safety rules

Do not publish raw material if it contains:

- email addresses;
- phone numbers;
- addresses;
- family/custody/health details;
- private conversations;
- legal drafts;
- NDA or collaborator-specific material;
- credentials, tokens, API keys, URLs with secrets;
- unreviewed accusations against people or companies;
- claims that appear scientific, medical, legal, or financial without evidence-tier support.

Publish summaries, metadata, and redacted excerpts instead.

---

## 6. What counts as a real recovery milestone

A recovery pass is complete only when it adds at least one of:

1. new source class;
2. new early-date anchor;
3. new canonical artifact;
4. new duplicate cluster;
5. new repository link;
6. new agent/collaborator lineage point;
7. new implementation artifact;
8. new evidence-tier promotion/demotion;
9. new redaction/safety decision;
10. new unresolved gap.

---

## 7. Current known high-value sources

- `Harmony_OS_Master_Codex.pdf` — early practical kernel, 2025-09-21.
- `Harmony_OS_v2_Coding_and_Data_Spec.pdf` — rooms-to-repo/code mapping, 2025-09-21.
- `ASIN_HHC_Codex_Master_Index_Export_For_Printing.pdf` — vault edition, 2025-10-18.
- `HarmonyOS_Sponsorship_Brief_v3.pdf` — public framework brief, 2025-10-18.
- `HarmonyOS_Siegel_Key_Reference.pdf` — symbolic metadata key, 2025-10-18.
- `Takeout` folder — export source, 2025-10-21.
- `HOS Vault Backend Core` — Firestore backend logic, 2025-10-24.
- `ASIN HHC HOS Harmonic Algebra Payload Block` — HOS formula/payload layer, 2025-10-25.
- `ASIN-HHC HOS Summary for Ace` — inter-node handoff, 2025-10-25.
- `gemini_gems_data.html` — ACE_GEM / sealed seed layer, 2025-10-28.
- `HHC Glyph Token App Phase II` — glyph token onboarding/app layer, 2025-11-16.
- `ANU-28 Master Codex` — glyph codex lineage, 2025-11-21.
- `anu28_10000_glyph_broadcast.html` — ANU-28 HTML broadcast artifact, 2025-11-21.
- `CP8 Master Render` — identity and light-glyph architecture, 2025-11-23.
- `ChatGPT_Conversation_Index.md` — 1,012 conversations, 435 ASIN/HHC, Jul-Oct 2025.
- `FULL_CHATGPT_EXTRACTION_2026-05-21.txt` — 1,014 conversations.
- `MASTER_AI_CORPUS.txt` — ChatGPT, Kimi, Gemini, Meta AI, ASIN docs, Oct27 logs, PDFs, misc.
- `AI_Data_Ingest_Report_2026-05-21.md` — source coverage and corpus metadata.
- `ASIN-HHC_v2.3_Extension_Spec.md` — Cathedral/Weaver governance extension.
- `CP8_ASIN_HHC_Documentation_Review.pdf` — review/gap analysis.

---

## 8. Known unresolved gaps

- DIGMA COUSA did not appear in Drive search under exact terms `DIGMA` or `COUSA`; it may be repo-born, renamed, embedded in HTML, or inside a ZIP/corpus.
- Raw ZIP contents are not yet enumerated.
- Full Takeout folder contents are not yet itemized.
- Duplicate clusters are not yet fully deduplicated.
- First-appearance dates for every major term are not yet proven.
- Code artifacts are not yet hashed/tested into E2/E3.
- Public redaction pass is not yet complete.

---

## 9. Immediate next actions

1. Build a source discovery table from all search terms.
2. Add a redaction checklist.
3. Extract first-appearance dates from the conversation index and master corpus.
4. Deduplicate Drive artifacts by title/date/source ID.
5. Promote executable scripts into `scripts/` only after review.
6. Create `scripts/provenance_manifest.py` and JSON schemas.
7. Add a public data-flow diagram.
8. Build a redacted public corpus index.

---

## 10. Boundary

This protocol is an audit/recovery tool. It does not claim that every archived artifact is true, scientific, production-ready, or public. It exists to ensure the full body of work is searched, classified, preserved, and presented responsibly.

---

**End of No-Stone-Unturned Audit Protocol.**
