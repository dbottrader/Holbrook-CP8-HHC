# CP8 E2 Runtime Build Specification

**Status:** E2 implementation target  
**Branch:** `cp8-e2-runtime`  
**Purpose:** Convert the existing E1 ASINHHCCP8 governance architecture into a runnable, testable runtime contract without replacing the existing Harmony Core / Moltbook interface.

## 1. Preserve the Existing Surface

The current Harmony Core / Moltbook attunement UI remains an input and presentation surface. Glyphs, harmonic values, frequencies, seals, and resonance metadata may be retained as interface semantics, but they do **not** grant authority, establish provenance, or substitute for evidence receipts.

## 2. Locked CP8 Invariants

1. **Capability != Authority.**
2. **No Receipt = No Promotion.**
3. **Replay Supersedes Narration.**
4. **Specification != Implementation.**
5. **Registry Inclusion != Proof.**
6. **AI Review != Independent Human Reproduction.**
7. **Mythos Has No Runtime Authority.**
8. **Reality Retains Veto.**

## 3. Canonical Cognitive Pipeline

Every CP8 research/investigation run MUST preserve this ordered stage model:

`ARTIFACT -> MEASUREMENT -> REPRESENTATION -> DECODING -> REPLICATION -> INTERPRETATION -> ORIGIN_HYPOTHESIS -> CHALLENGE -> REVISION`

A runtime may pause, retry, branch, or return to an earlier stage through an explicit revision event. It may not silently skip forward.

## 4. Claim Model

Every promoted claim must be expressible through the five-field evidence structure:

- `OBSERVED`
- `CONTEXT`
- `INFERENCE`
- `TEST`
- `CONCLUSION`

Claims are content-addressed using SHA-256 over their canonical representation. Negative results, failed tests, contradictions, and unresolved evidence are first-class records and must not be deleted to improve narrative coherence.

## 5. Run Model

A CP8 run begins from a human or agent request and creates a durable Run Record with:

- run ID
- steward / creator
- mission text
- original interpretation / hypothesis
- current pipeline stage
- worker branches
- evidence references
- policy decisions
- receipts
- promotion state
- reality-veto state
- replay reference

The originating interpretation MUST be withheld from workers marked `independent` or `adversarial` until synthesis.

## 6. Worker Contracts

Initial worker roles:

- `evidence` — local/project/source collection only
- `research` — external/public evidence collection
- `chronology` — dates, versions, commit order, provenance reconciliation
- `pattern` — structural comparison without preferred conclusion
- `skeptic` — attempts to falsify or disconfirm
- `replication` — reproduces calculations, transforms, geometry, code, or procedures
- `prior_art` — separates similarity, convergence, derivation, and influence evidence
- `builder` — produces executable artifacts only after requirements stabilize
- `synthesis` — receives closed branch reports and reconciles agreement/disagreement

Worker output must identify source inputs, confidence, limitations, unresolved contradictions, and whether the worker was exposed to the originating interpretation.

## 7. Governance Gate

Every action packet passes through a governance decision with one of:

- `APPROVE`
- `BLOCK`
- `ESCALATE`
- `REQUIRE_MORE_CONTEXT`

The decision evaluates policy, permissions, risk class, expected side effects, reversibility, user intent, and current system state.

## 8. Promotion Gate

Promotion result is one of:

- `PASS`
- `HOLD`
- `FAIL`

Promotion is prohibited when required receipts are missing. A `PASS` does not imply production authority. Evidence tier remains separate from operational authority.

## 9. Reality Veto

A human steward or qualifying physical measurement may veto promotion. The veto is recorded as a durable decision object with actor, reason, timestamp, evidence references, and supersession rules.

## 10. Evidence Tiers

Use the existing ladder:

- `E0` Idea
- `E1` Draft / architecture
- `E2` Local executable
- `E3` Independently reproducible
- `E4` Reviewed
- `E5` Production

Promotion between tiers requires explicit evidence and a decision record. Self-test success alone cannot produce E3.

## 11. Persistence Boundary

The first implementation may use PostgreSQL or another durable transactional store. Conversations are not the source of truth. The source of truth is the durable run/evidence/receipt graph.

Required logical collections/tables:

- `runs`
- `stages`
- `workers`
- `claims`
- `evidence`
- `edges`
- `action_packets`
- `governance_decisions`
- `receipts`
- `promotion_decisions`
- `reality_vetoes`
- `replay_records`

## 12. Agent-Neutral Interface

The runtime should expose ordinary HTTP/JSON first and remain compatible with MCP/A2A-style adapters later. Platform-specific agent integrations must not become the canonical data model.

Minimum operations:

- create run
- get run
- advance stage
- create worker branch
- submit worker result
- add evidence
- add claim
- request governance decision
- request promotion
- record reality veto
- fetch replay record
- export portable handoff packet

## 13. Acceptance Test: Crabwood Investigation

A complete E2 slice MUST demonstrate:

1. User submits `investigate Crabwood encoding`.
2. Runtime creates a unique Run Record.
3. The ordered CP8 pipeline is initialized.
4. Independent worker branches are created without the originating interpretation.
5. Evidence and at least one contradicting item are recorded.
6. Skeptic branch produces a falsification attempt.
7. Replication branch records a reproducible test or a failed reproduction.
8. Synthesis receives only closed worker reports.
9. Promotion gate produces PASS, HOLD, or FAIL with a receipt.
10. Human Reality Veto can override promotion while preserving the prior decision record.
11. Full run survives process restart / page refresh.
12. Exported portable handoff can reconstruct the run state without relying on the original chat.

If any of these fail, the runtime remains E1.

## 14. Reuse-First Dependency Policy

Do not reimplement commodity infrastructure where a mature component exists. Prefer existing libraries/services for:

- durable workflow execution
- agent handoffs/tool execution
- MCP transport
- relational persistence
- vector retrieval
- fine-grained authorization
- cryptographic signing / attestations
- transparency logging

CP8-specific code should remain focused on evidence semantics, contamination isolation, stage discipline, receipts, promotion rules, reality veto, chronology, and prior-art/influence reasoning.

## 15. Non-Goals for the First E2 Slice

Not required for the first executable promotion:

- cryptocurrency issuance
- real-money staking/trading
- production wallet custody
- public token economics
- autonomous production deployment
- replacing the existing Harmony Core UI
- external claims of scientific validation

The first target is a durable, replayable, governed cognition runtime.
