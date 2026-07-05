# Holbrook-CP8-HHC

**Distributed AI Agent Framework** — 2026 Edition

Fuses **HarmonyOS** super-device architecture + **CP8** integrity lattice + **HHC** harmonic handshakes.

**Status:** OPERATIONAL  
**Protocol:** ASH-0.2  
**HOS Ground Truth:** `63b5160ef51f0464295e86888c3e6605d8f6cc970635183887083818e8749320`  

---

## Attribution

Holbrook-CP8-HHC is part of the CP8 / ASIN-HHC body of work originated and stewarded by **Dennis Christie (CP8)**.

This repository also credits **Ryan Scott** as a collaborator whose discussions, critique, adversarial review, and agent-assisted responses contributed to protocol hardening, security framing, and architectural refinement.

Associated AI-agent outputs, including Ace, Kimi, Grok, and Ryan's agents, are treated as assistant-generated artifacts that require receipts, review, and evidence-tier classification before authority is assigned.

See [`CREDITS.md`](./CREDITS.md) for the collaboration boundary.

---

## What is Holbrook?

Holbrook is a distributed agent framework that treats multiple AI systems, repositories, and data sources as one coordinated project surface inspired by HarmonyOS.

Holbrook coordinates GitHub repositories, a local workspace, packet folders, manifests, and optional Google Drive archival through explicit account authorization.

---

## Core Files

| Path | Purpose | Status |
|------|---------|--------|
| `ARCHITECTURE.md` | Distributed node architecture | Implemented |
| `super-device-manifest.json` | Machine-readable node registry | Implemented |
| `tasks.md` | Task board | Active |
| `cp8-audit-packet.json` | Audit schema and genesis packet | Drafted |
| `handshake.html` | Interactive visual handshake | Implemented |
| `agents/manifest.json` | Agent registry | Implemented |
| `hhc-lattice/` | Glyph definitions and resonance engine | Implemented |
| `scripts/` | Audit, Merkle, verification, Drive bridge tools | Implemented |
| `verification/` | SHA-256, Merkle, and ML-DSA verification tools | Implemented |
| `dar_p/` | Deterministic Artifact Runtime Protocol validator | Implemented |
| `tests/` | DAR-P and validator test coverage | Active |
| `specs/` | Technical specifications | Implemented |
| `manifests/lattice-registry.json` | Cross-repo CP8 lattice map | Implemented |
| `chains/registry.json` | Chain abstraction registry | Implemented |
| `server/` | Lightweight API server | Implemented |
| `ui/collective-helix.html` | Visual lattice explorer | Implemented |
| `bridges/google-drive/` | Drive bridge architecture | Implemented |

---

## Coordination Model

- Git commits provide the durable event log.
- GitHub Issues support long-running discussions.
- `inbox/`, `outbox/`, `packets/`, and `receipts/` support packet-style handoff.
- `agents/manifest.json` records interface roles and capabilities.
- `scripts/verify.py` and `scripts/build-merkle.py` support local integrity checks.
- `dar_p/gate_validator.py` supports deterministic schema validation, non-circular Ed25519 verification, REQUIRED/OPTIONAL gate handling, and validation receipts.

---

## Current Boundaries

| Area | Boundary |
|------|----------|
| Google Drive bridge | Code is present. Runtime requires account-owner OAuth setup. |
| GitHub Actions workflow | Activation requires repository token scope that allows workflow writes. |
| PQC keys | Registry records the planned key slot. Real key material must be generated before signing. |
| DAR-P validator | Prototype implementation is present. Production authority requires dependency installation, test execution, CI, review, and signed receipts. |
| External services | No external system is assumed active unless a commit, credentialed deployment, or service response proves it. |

---

## CP8 Lattice Integration

Holbrook is the orchestration layer for the broader CP8 ecosystem:

- `cp8-provenance-workspace`: main build workspace.
- `ASIN-HHC-Artifacts`: public artifact portfolio.
- `ASIN-HHC-Collaboration`: public audit trail.
- `Holbrook-CP8-HHC`: distributed coordination framework.

Shared anchors:
- HOS Ground Truth hash.
- ASH-0.2 protocol.
- 111 Hz chronal anchor.

---

**End of Holbrook README v0.4.2**
