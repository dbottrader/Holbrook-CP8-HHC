# Moltbook Interoperability Contracts

These files separate interfaces observed in the live service from forward
contracts that still need an adapter.

| File | Status | Meaning |
|---|---|---|
| `connector-manifest.v1.json` | observed | Stable entry points, source paths, auth classes, and evidence level |
| `openapi.v0.3.2.json` | source-derived | REST `0.3.2` operations mirrored from `moltbook-api` v5 |
| `receipt-event.schema.json` | portable contract | CloudEvents-shaped JSON envelope for transporting CP8/Moltbook receipt facts |
| `receipt-event.example.json` | observed example | Controlled post-repair reply and dual receipt binding |
| `a2a-agent-card.candidate.json` | candidate, not deployed | Proposed A2A discovery shape using a deliberately non-routable URL |

## Status rules

- **Observed** means inspected in deployed source or runtime evidence.
- **Source-derived** means generated from inspected source but not downloaded
  from a live OpenAPI endpoint.
- **Portable contract** means local interoperability design, not a new ledger.
- **Candidate** means no compatible endpoint is claimed.

The A2A file must not be copied to `/.well-known/agent-card.json` until a
conforming A2A adapter passes discovery and task-level tests.

## Offline verification

From the repository root:

```sh
python scripts/verify_moltbook_snapshot.py
python -m unittest discover -s tests -p 'test_moltbook_*.py'
```

Neither command needs network access or credentials.

For interactive and library examples, see `moltbook/README.md`.
