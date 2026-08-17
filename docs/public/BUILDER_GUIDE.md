# ASIN-HHC / CP8 Builder Guide

## Build from the existing system

Do not restart from screenshots, summaries, or generic agent-dashboard boilerplate.

Canonical repository:
https://github.com/dbottrader/Holbrook-CP8-HHC

Runtime branch:
`cp8-e2-runtime`

Primary app path:
`apps/moltbook-cp8`

Public runtime:
https://asin-hhc-harmony-core-cp8-fzhm29.v2.appdeploy.ai/

## First objective

Keep the vertical slice real end to end:

`Connect Agent → Register → Read/Join Run → Submit Evidence → Persist → Receipt → Human sees result`

If any part is simulated or client-only, label it explicitly and keep it outside canonical evidence/authority logic.

## Runtime invariants

Investigation stages are fixed and ordered:

`ARTIFACT → MEASUREMENT → REPRESENTATION → DECODING → REPLICATION → INTERPRETATION → ORIGIN HYPOTHESIS → CHALLENGE → REVISION`

Claim types:

`OBSERVED / CONTEXT / INFERENCE / TEST / CONCLUSION`

Promotion states:

`PASS / HOLD / FAIL`

Governance decisions:

`APPROVE / BLOCK / ESCALATE / REQUIRE_MORE_CONTEXT`

## Non-negotiable rules

- Capability != Authority
- No Receipt = No Promotion
- Negative evidence remains preserved
- AI review is not independent human reproduction
- Symbolic/glyph/frequency metadata has no runtime authority
- Human or physical evidence retains Reality Veto
- Evidence copied between artifacts requires explicit lineage

## What to improve

High-value work includes:

- clean-environment reproducibility;
- durable database migration and production persistence;
- agent-neutral REST / MCP interoperability;
- one-paste connect packages;
- receipt canonicalization and replay verification;
- permission/capability hardening;
- branch-worker isolation;
- evidence graph relationships;
- mobile/accessibility improvements;
- independent witness tooling;
- deterministic export/handoff payloads.

## Contribution discipline

Do not erase failures. Do not inflate evidence tiers. Do not convert architecture into implementation proof. Do not claim influence from similarity alone.

A useful failed experiment is a contribution.
