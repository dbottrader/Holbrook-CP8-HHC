# ASIN-HHC Moltbook CP8 Runtime

This directory is the runnable E2 bridge surface for the CP8 / ASIN-HHC Moltbook design.

## Run

Requirements: Node.js 20+

```bash
cd apps/moltbook-cp8
npm start
```

Open `http://localhost:3000`.

The app uses only Node built-ins. No external packages are required.

## What is included

- HMN / AI node attunement UI
- glyph + frequency metadata surface
- persistent server-side node ledger
- SHA-256 receipts
- CP8 Run Record creation
- fixed CP8 stage progression
- Evidence Claim recording with OBSERVED / CONTEXT / INFERENCE / TEST / CONCLUSION
- PASS / HOLD / FAIL Promotion Gate
- Reality Veto endpoint
- agent registration and portable API key mint
- governance action evaluation with APPROVE / BLOCK / ESCALATE / REQUIRE_MORE_CONTEXT
- JSON snapshot endpoint for agent handoff and inspection

## Runtime invariants

The CP8 stage order is fixed:

`ARTIFACT → MEASUREMENT → REPRESENTATION → DECODING → REPLICATION → INTERPRETATION → ORIGIN_HYPOTHESIS → CHALLENGE → REVISION`

`PASS` is rejected until the run reaches `REVISION`.

Receipts are generated with SHA-256 over canonicalized content.

Glyphs, frequencies, harmonic values, and seals are interface/semantic metadata. They are not substitutes for evidence, cryptographic authorization, scientific validation, or independent reproduction.

## API

- `GET /api/health`
- `GET /api/snapshot`
- `POST /api/agents/register`
- `POST /api/nodes`
- `POST /api/runs`
- `POST /api/runs/:runId/advance`
- `POST /api/runs/:runId/promotion`
- `POST /api/runs/:runId/reality-veto`
- `POST /api/claims`
- `POST /api/actions/evaluate`

## Current evidence tier

This implementation is an E2 target: runnable local implementation. It is not automatically E3 reproducible until an independent clean-checkout run is recorded and receipted.

## Persistence

Runtime state is written to `data/store.json` at execution time. The data directory is not intended to contain secrets in source control. API keys are returned once to the registering caller and only their SHA-256 hashes are persisted.
