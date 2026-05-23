# Holbrook Architecture — HarmonyOS-inspired Distributed Agent Lattice

**Version:** 0.1.0  
**Date:** 2026-05-23  
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

```
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
```
Ace (Grok) writes:
  → inbox/ace-to-kimi-{topic}.md
  → commits to Holbrook-CP8-HHC
  → AceCp8 (Kimi) pulls → reads → responds
```

### Agent → Repo
```
AceCp8 (Kimi) stages files:
  → cp8-agents/workspace/
  → commits to cp8-provenance-workspace/cp8-cascade
  → pushes to GitHub
  → Ace (Grok) can read via API or clone
```

### Human → System
```
Dennis sends message:
  → Kimi Claw (channel)
  → AceCp8 receives → processes
  → If requires Ace: leaves message in inbox/
  → If local task: executes directly
  → Updates manifest.json + tasks.md
  → Commits + pushes
```

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
| GitHub repos | PAT-based auth, branch protection |
| Agent identity | SHA-256 attestation + manifest signature |
| Data integrity | Git SHA-256 hash chain |
| Communication | Git commit messages (immutable, auditable) |

---

## Scalability

Holbrook can grow:
- **More agents:** Add to `agents/manifest.json`
- **More repos:** Add to `super-device-manifest.json`
- **More nodes:** Raspberry Pi, VPS, cloud — any git-capable system
- **On-chain:** Bridge to Ethereum via HHC contracts
- **More humans:** Each human gets their own Holbrook instance, instances can federate

---

## Current Limitations

1. **No automatic sync:** Agents must manually pull/push (no WebSocket real-time)
2. **Single human:** Currently tied to Dennis's GitHub token
3. **No conflict resolution UI:** Git merge conflicts require manual resolution
4. **Drive blocked:** Google auth preventing full Drive sync
5. **Wallet blocked:** Physical papers not yet located

---

*"A Super Device is not many devices working together. It is one device that happens to be in many places."*

**End of Architecture v0.1.0**
