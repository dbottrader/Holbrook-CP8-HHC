# Archive Recovery Notes — Kimi Agent User Profile Summary

## Source package

Original uploaded archive:

`Kimi_Agent_User Profile Summary.zip`

SHA-256:

`e2e2e13e262f5dd06201d4de2606f85e657eaf56eeb3f4799b13f6f9153a8399`

## Nested package archive

Nested archive inside source ZIP:

`cathedral_os_tools_v1.0.0.zip`

SHA-256:

`271538aae244165216bf1e0fd2e1f32af2e248833b30f447839cb263d7edef52`

## Import status

The project has been registered in Holbrook with:

- import manifest
- migration status tracker
- project reference metadata
- GitHub issue #4 migration queue

## Binary preservation policy

Binary payloads must be preserved using a binary-safe route before marking the mirror complete.

Acceptable routes:

1. GitHub release assets
2. Git blob/tree commit with base64-safe upload path
3. encoded text archive chunks with SHA-256 reconstruction instructions
4. external cold archive with SHA-256 pointer committed here

## Source mirror policy

The following are source and should be committed as plain files:

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

The following are generated caches and should not be committed as source:

- `cathedral_os_tools/__pycache__/`
- `cathedral_os_tools/tests/__pycache__/`
- `*.pyc`

## Verification command

After restoring archive bytes, verify with:

```bash
sha256sum "Kimi_Agent_User Profile Summary.zip"
sha256sum cathedral_os_tools_v1.0.0.zip
```

Expected hashes are listed above and in `SHA256SUMS.txt`.
