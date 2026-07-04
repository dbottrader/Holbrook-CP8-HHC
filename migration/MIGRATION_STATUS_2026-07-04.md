# Holbrook Repository Migration Status — 2026-07-04

## Status

Migration work has resumed in the live GitHub-connected thread.

The repository is confirmed as:

- Repository: `dbottrader/Holbrook-CP8-HHC`
- Default branch: `main`
- Permission: push/admin available through connected GitHub session

## Current finding

The published GitHub state is a partial mirror of the broader CP8 / ASIN-HHC corpus.

The uploaded payload reviewed in this thread contains:

- `SPEC.md`
- `plan.md`
- `cathedral_os_tools/` Python package
- `cathedral_os_tools/tests/` unit tests
- nested package archive `cathedral_os_tools_v1.0.0.zip`
- generated Python cache files under `__pycache__/`

## Import policy

Source files should be imported into the repository as first-class source files.

Generated files should not be treated as source:

- `*.pyc`
- `__pycache__/`
- regenerated build/cache output

Binary archives should be preserved by one of these routes:

1. encoded archive file with SHA-256 recovery instructions, or
2. Git blob/tree commit when binary-safe commit path is available, or
3. release asset when release tooling is available.

## Completed in this thread

- Confirmed connected GitHub access.
- Listed accessible repositories.
- Confirmed `dbottrader/Holbrook-CP8-HHC` as the Holbrook target.
- Added import manifest at:
  - `imports/kimi-agent-user-profile-summary/2026-07-03-import-manifest.md`
- Manifest commit:
  - `8f583410c6dae9494132b6295bdcba7dffd79bbc`

## Active migration queue

### 1. Source import

Target path:

`imports/kimi-agent-user-profile-summary/source/`

Files queued:

- `SPEC.md`
- `plan.md`
- `cathedral_os_tools/.gitignore`
- `cathedral_os_tools/README.md`
- `cathedral_os_tools/__init__.py`
- `cathedral_os_tools/cli.py`
- `cathedral_os_tools/evidence_ladder.py`
- `cathedral_os_tools/lmc_init.py`
- `cathedral_os_tools/schemas.py`
- `cathedral_os_tools/tests/__init__.py`
- `cathedral_os_tools/tests/test_evidence_ladder.py`
- `cathedral_os_tools/tests/test_lmc_init.py`

### 2. Binary/archive preservation

Queued:

- `Kimi_Agent_User Profile Summary.zip`
- `cathedral_os_tools_v1.0.0.zip`

Known hashes are recorded in the import manifest.

### 3. Repository consolidation

Accessible repositories should be classified into:

- canonical Holbrook infrastructure
- ASIN/HHC artifact repos
- collaboration/audit repos
- duplicate or placeholder candidates
- external/reference repos

### 4. Cleanup gate

No repository should be deleted until:

- contents are inventoried,
- unique files are migrated or intentionally excluded,
- README/status is inspected,
- commit history value is assessed,
- deletion candidate list is reviewed.

## Working rule

This is a migration and repository-engineering task, not new feature development.

The target outcome is a complete reproducible Holbrook mirror with source files, manifests, encoded/binary-preserved assets, cleanup notes, and release tagging.
