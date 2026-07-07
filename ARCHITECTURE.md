# Holbrook Architecture — HarmonyOS-inspired Distributed Agent Lattice

**Version:** 0.1.1  
**Date:** 2026-07-06  
**Protocol:** ASH-0.2  

---

## Philosophy

Holbrook treats AI agents, repositories, and data sources not as separate tools but as **nodes in a single distributed organism** — the same way HarmonyOS treats phones, watches, TVs, and cars as one "Super Device."

The user (Dennis) doesn't interact with "Kimi" or "Grok" or "GitHub." They interact with **Holbrook** — one unified system that happens to be distributed across multiple platforms.

---

## HarmonyOS → Holbrook Concept Mapping

| HarmonyOS Concept | Holbrook Adaptation | Implementation |
|-------------------|--------------------|----------------|
| **Super Device** | Unified CP8 Lattice | All repos + agents + Drive as one logical entity |
| **Distributed Soft Bus** | Agent Communication Bus | Git commits + GitHub Issues + `inbox/` + `manifest.json` |
| **Distributed Device Virtualization** | Capability Sharing | Grok = Solidity/builder, Kimi = archivist/git-ops |
| **Distributed Data Management** | Provenance & Audit Chain | `audit-packet.jsonl` + SHA-256 hash chaining |
| **Distributed Task Scheduling** | Dynamic Task Board | `tasks.md` + agent manifest + automatic task routing |
| **Atomic Abilities** | Modular CP8 Components | Separate folders: handshake, audit, resonance, lattice |
| **HMDFS** | Git-based File System | Git as distributed file system with conflict resolution |
| **DevEco Studio** | Holbrook Workspace | Local `~/.openclaw/workspace/` as development environment |

---

## Node Topology

```text
                    ┌─────────────────────────────────────┐
                    │         HOLBROOK SUPER DEVICE        │
                    │    (One unified distributed system)   │
                    └─────────────────────────────────────┘
                                      │
            ┌─────────────────────────┼─────────────────────────┐
            │                         │                         │
            ▼                         ▼                         ▼
    ┌───────────────┐      ┌──────────────────┐      ┌───────────────┐
    │  LOCAL CORE   │      │   GITHUB LAYER   │      │   AGENTS      │
    │               │      │                  │      │               │
    │ cp8-workspace │◄────►│ ASIN-HHC-Artifacts│◄────►│  Ace (Grok)   │
    │ (real-time)   │      │ (public archive) │      │  (builder)    │
    │               │      │                  │      │               │
    │ hmn.db        │      │ ASIN-HHC-Collab  │◄────►│ AceCp8 (Kimi) │
    │ cp8-server    │      │ (audit trail)    │      │ (archivist)   │
    │ cp8-lattice   │      │                  │      │               │
    │ project-harmonia│    │ Holbrook-CP8-HHC │◄────►│               │
    │               │      │ (this framework) │      │               │
    └───────────────┘      └──────────────────┘      └───────────────┘
            │                         │                         │
            │                         │                         │
            └─────────────────────────┼─────────────────────────┘
                                      │
                                      ▼
                            ┌──────────────────┐
                            │   DRIVE LAYER    │
                            │  (cold archive)  │
                            │                  │
                            │ ASIN_HHC_CP8/    │
                            │  (zips, docs)    │
                            └──────────────────┘
```

---

## Communication Flow

### Agent → Agent

```text
Ace (Grok) writes:
  → inbox/ace-to-kimi-{topic}.md
  → commits to Holbrook-CP8-HHC
  → AceCp8 (Kimi) pulls → reads → responds
```

### Agent → Repo

```text
AceCp8 (Kimi) stages files:
  → cp8-agents/workspace/
  → commits to cp8-provenance-workspace/cp8-cascade
  → pushes to GitHub
  → Ace (Grok) can read via API or clone
```

### Human → System

```text
Dennis sends message:
  → Kimi Claw (channel)
  → AceCp8 receives → processes
  → If requires Ace: leaves message in inbox/
  → If local task: executes directly
  → Updates manifest.json + tasks.md
  → Commits + pushes
```

---

## Adaptive Runtime Governance Bridge

Holbrook can also frame adaptive agent loops as governed runtimes.

The current bridge note is:

```text
docs/ADAJEPA_ASINHHCCP8_RUNTIME_BRIDGE.md
```

It maps an adaptive world-model loop:

```text
Plan → Execute → Adapt → Replan
```

onto an accountable ASINHHCCP8 runtime:

```text
Goal → Observation → Plan → Governance Gate → Action → Receipt → Feedback → Replay → Updated Model
```

The bridge adds four control functions around agent action:

| Control function | Purpose |
|---|---|
| Anchor / Shape / Intention / Number | Bind each request to source, form, purpose, and control value. |
| Policy + Context Gate | Approve, block, escalate, or request more context before execution. |
| Receipts + Replay | Preserve what happened, why it happened, and how to reconstruct it. |
| Human Oversight | Route high-impact, ambiguous, or irreversible actions to accountable review. |

This is currently an E1 architectural mapping. It becomes E2 only when implemented as a runnable validator, policy gate, receipt generator, and replay test.

---

## Data Consistency Model

Holbrook uses **eventual consistency** (like HarmonyOS HMDFS):

1. **Local workspace** is the source of truth for real-time work
2. **GitHub repos** sync via push/pull (near-real-time)
3. **Drive** is cold archive (manual sync, eventual)
4. **Conflict resolution:** Git merge handles overlaps
5. **Audit trail:** Every commit is a provenance packet

---

## Security Model

| Layer | Protection |
|-------|-----------|
| Local workspace | File permissions, git history |
| GitHub repos | Explicit authenticated repository access and branch policy |
| Agent identity | SHA-256 attestation + manifest signature |
| Data integrity | Git SHA-256 hash chain |
| Communication | Git commit messages (immutable, auditable) |
| Runtime actions | Policy gate, decision receipt, replay reference, human escalation |

---

## Scalability

Holbrook can grow:

- **More agents:** Add to `agents/manifest.json`
- **More repos:** Add to `super-device-manifest.json`
- **More nodes:** Raspberry Pi, VPS, cloud — any git-capable system
- **On-chain:** Bridge to Ethereum via HHC contracts
- **More humans:** Each human gets their own Holbrook instance, instances can federate
- **More adaptive loops:** Add governed world-model runtimes once receipts and replay tests exist

---

## Current Limitations

1. **No automatic sync:** Agents must manually pull/push (no WebSocket real-time)
2. **Single primary steward:** The system currently follows Dennis / CP8 as the public human anchor
3. **No conflict resolution UI:** Git merge conflicts require manual resolution
4. **Drive blocked:** Google auth preventing full Drive sync
5. **Wallet blocked:** Physical papers not yet located
6. **Adaptive runtime bridge is E1:** The AdaJEPA × ASINHHCCP8 mapping is not yet a runnable E2 implementation

---

*"A Super Device is not many devices working together. It is one device that happens to be in many places."*

**End of Architecture v0.1.1**
