# Project Reference — Kimi Agent User Profile Summary Import

## Canonical target

- Repository: `dbottrader/Holbrook-CP8-HHC`
- Branch: `main`
- Role: Holbrook / CP8-HHC canonical infrastructure and migration target
- Connected account: `dbottrader`

## Conversation directive

User directive: publish everything possible in the current GitHub-connected thread and reference the project metadata.

This file anchors the migration so later work is traceable to the uploaded package and not confused with a new feature build.

## Project identity

- Upload name: `Kimi_Agent_User Profile Summary.zip`
- Extracted project: `cathedral_os_tools`
- Declared version: `1.0.0`
- Project class: Cathedral-OS / Labyrinth / LMC tooling
- Modules:
  - `lmc_init.py` — LMC project bootstrap/scaffolding engine
  - `evidence_ladder.py` — Evidence Ladder Enforcer for E0-E6 claim/evidence promotion control
  - `schemas.py` — shared schema/dataclass definitions
  - `cli.py` — unified CLI entry point
  - `tests/` — validation tests for scaffold and evidence ladder behavior

## Hash metadata

- Source ZIP SHA-256: `e2e2e13e262f5dd06201d4de2606f85e657eaf56eeb3f4799b13f6f9153a8399`
- Nested archive SHA-256: `271538aae244165216bf1e0fd2e1f32af2e248833b30f447839cb263d7edef52`

## Corpus assessment preserved

The current GitHub publication is a partial mirror of the broader CP8 / ASIN-HHC corpus.

Estimated publication status at time of this import:

| Area | Status |
|---|---:|
| Repository foundations | 95% |
| Documentation | 90-95% |
| Handshake Engine | 85-90% |
| Provenance/manifests | 90% |
| Complete source mirror | 20-35% |
| Binary asset publication | 0-20% |
| Repository consolidation/cleanup | Not started |

## Remaining migration classes

The remaining work is repository engineering, not core code invention:

1. Export every HTML UI.
2. Export every JS/TS utility.
3. Export every Python utility.
4. Export JSON/CSV/manifests.
5. Upload or preserve PDFs and ZIP archives.
6. Preserve commit history where possible.
7. Remove placeholder repositories only after inventory.
8. Consolidate duplicate repositories.
9. Tag releases.
10. Produce a complete reproducible mirror.

## Publication policy for this thread

Publish immediately when safe:

- UTF-8 source files
- Markdown specifications
- JSON manifests
- checksums / SHA inventories
- migration trackers
- reproducibility instructions

Preserve carefully:

- ZIP archives
- PDFs
- certificates
- binary payloads
- generated outputs

Exclude from source mirror unless deliberately preserved by hash:

- `__pycache__/`
- `*.pyc`
- temporary build caches
- duplicated generated files

## Already committed in this thread

1. Import manifest
   - Path: `imports/kimi-agent-user-profile-summary/2026-07-03-import-manifest.md`
   - Commit: `8f583410c6dae9494132b6295bdcba7dffd79bbc`

2. Migration status tracker
   - Path: `migration/MIGRATION_STATUS_2026-07-04.md`
   - Commit: `5768248c24030f63dc673d67db9560879953b727`

3. This project reference file
   - Path: `migration/PROJECT_REFERENCE_KIMI_AGENT_USER_PROFILE_SUMMARY.md`

## Next preferred repo layout

```text
imports/kimi-agent-user-profile-summary/
├── 2026-07-03-import-manifest.md
├── PROJECT_REFERENCE.md
├── source/
│   ├── SPEC.md
│   ├── plan.md
│   └── cathedral_os_tools/
│       ├── README.md
│       ├── __init__.py
│       ├── cli.py
│       ├── evidence_ladder.py
│       ├── lmc_init.py
│       ├── schemas.py
│       └── tests/
└── archives/
    ├── SHA256SUMS.txt
    └── RECOVERY.md
```

## Cleanup rule

No repository deletion should occur until all accessible repositories are inventoried and compared for unique files, artifact value, commit-history value, and placeholder-only status.
