# Harmony Core Publication Matrix

This document keeps external publishing aligned to one canonical technical source rather than creating divergent platform-specific claims.

## Canonical source
- Repository: `dbottrader/Holbrook-CP8-HHC`
- Active implementation branch: `cp8-e2-runtime`
- Public technical brief: `docs/PUBLIC_LAUNCH_BRIEF.md`
- Runtime build spec: `docs/CP8_E2_RUNTIME_BUILD_SPEC.md`

## Platform roles

### GitHub — canonical engineering/provenance record
Publish source, schemas, run/evidence contracts, changelog, issues, witness kits, and reproducibility instructions. GitHub commit chronology is the canonical public engineering record unless explicitly superseded by another signed record.

### Vercel — primary live web deployment
Use the existing `asin-hhc-harmonyos` project as the preferred public launch anchor where practical. Deploy the full-stack Harmony Core web/API surface after clean build and acceptance testing. Do not treat a deployment as E3/E4 proof by itself.

### Replit — secondary development/deployment surface
Use once the MCP resource-binding issue is resolved. Replit must consume the canonical GitHub source rather than becoming a forked source of truth.

### Hugging Face — AI/research discovery mirror
Publish a Space or repository that introduces the system to ML/agent researchers, links to canonical GitHub, exposes a demo when technically appropriate, and clearly separates implemented behavior from experiments.

### Notion / Google Drive — readable research and collaboration briefs
Publish curated public-facing summaries, onboarding material, architecture explainers, and collaboration packets. Do not expose private archive material by default.

### LinkedIn / social channels — education and recruitment
Publish concise explainers and build-in-public updates aimed at builders, researchers, skeptical reviewers, and independent witnesses. Avoid unsupported priority, influence, scientific, or investment claims.

### Linear / project trackers — execution coordination
Track implementation blockers, acceptance tests, E2→E3 promotion work, security hardening, and deployment readiness. Project management state is not evidence by itself.

## Core public messages
1. Harmony Core is a human+AI collaboration and evidence runtime.
2. CP8 separates observation, context, inference, test, and conclusion.
3. Independent/adversarial workers are intentionally isolated before synthesis.
4. Capability does not imply authority.
5. No receipt means no promotion.
6. Failed replication and contradiction are first-class evidence.
7. Human/physical reality retains veto at consequential boundaries.
8. Agent onboarding should be copy/paste-simple while permissions remain scoped.

## Required disclosure language
- Symbolic resonance/glyph/frequency layers are experimental interface metadata unless independently validated.
- ROI/staking features are simulation only unless backed by real, reviewed economic infrastructure.
- E1 architecture does not become E2 until it runs; E2 does not become E3 until a clean independent reproduction succeeds.

## Launch asset set
Each platform should derive from the same asset set:
- one-sentence description
- public launch brief
- architecture diagram or compact flow
- 60-second onboarding explanation
- contributor call
- skeptical-review call
- witness/reproduction instructions
- machine-readable agent discovery/handoff description
- current evidence tier and known blockers

## Success condition
The launch is considered operational when a public deployment supports:
Human creates mission → external/scoped agent connects → agent reads permitted mission → agent submits a contribution → persistent receipt is produced → human sees it → governance blocks unauthorized promotion → handoff/replay reconstructs the event.
