# Holbrook-CP8-HHC

**Distributed AI Agent Framework** — 2026 Edition

Fuses **HarmonyOS** super-device architecture + **CP8** integrity lattice + **HHC** harmonic handshakes.

**Status:** 🟢 OPERATIONAL  
**Protocol:** ASH-0.2  
**HOS Ground Truth:** `63b5160ef51f0464295e86888c3e6605d8f6cc970635183887083818e8749320`  

---

## What is Holbrook?

Holbrook is a **distributed agent framework** that treats multiple AI systems, repositories, and data sources as a single unified "Super Device" — inspired by HarmonyOS.

Instead of separate apps on separate devices, Holbrook sees:
- **AceCp8 (Kimi)** — Your local archivist
- **Ace (Grok)** — Your builder/architect
- **GitHub repos** — Distributed storage nodes
- **Google Drive** — Cold archive layer
- **Local workspace** — Real-time processing core

All connected via the **CP8 Distributed Soft Bus** (git + GitHub Issues + `inbox/` + `manifest.json`).

---

## Architecture

### Super Device
One unified lattice spanning:
| Layer | Node | Role |
|-------|------|------|
| Local | `cp8-provenance-workspace` | Real-time ops, agent hosting, file processing |
| GitHub | `ASIN-HHC-Artifacts` | Public artifact archive (images, diagrams, pitch files) |
| GitHub | `ASIN-HHC-Collaboration` | Public audit trail (shared logs, issues, decisions) |
| GitHub | `Holbrook-CP8-HHC` | **This repo** — Distributed framework core |
| Drive | `ASIN_HHC_CP8` | Cold archive (zips, whitepapers, historical builds) |
| Agent | `Ace (Grok)` | Builder: Solidity, architecture, code generation |
| Agent | `AceCp8 (Kimi)` | Archivist: File ops, git, audit, ecosystem wiring |

### Distributed Soft Bus
- **Protocol:** Git commits + GitHub Issues + `inbox/` markdown files + `manifest.json`
- **Sync:** Real-time via git push/pull
- **Backbone:** Git SHA-256 hash chain (immutable audit trail)
- **Bus Topology:** Mesh — every node can reach every other node

### Provenance
Every action in Holbrook is attested:
- SHA-256 hash chain in `audit-packet.jsonl`
- Multi-agent attestations (both agents sign off)
- Git commit history as immutable log
- `cp8-audit-packet.json` schema for standardized audit records

---

## Active Agents

| Agent | Model | Role | Current Task | Status |
|-------|-------|------|-------------|--------|
| **Holbrook-Grok** | grok/claude | Builder | Solidity contract (Task #3) | 🟢 Active |
| **AceCp8** | kimi/k2p6 | Archivist | Ecosystem wiring + git ops | 🟢 Active |

---

## Quick Start

### For Humans (Dennis)
1. Read `ARCHITECTURE.md` — Understand the distributed node map
2. Check `tasks.md` — See what's being worked on
3. Open `handshake.html` — Visual CP8 lattice interaction
4. Review `agents/manifest.json` — Agent status and capabilities

### For Agents
1. Read `inbox/` — Check for messages directed at you
2. Update `agents/manifest.json` — Log your current activity
3. Claim tasks in `tasks.md` — Mark with `[AGENT: YourName]`
4. Commit changes — Push to this repo for sync
5. Leave messages in `inbox/` — For other agents

---

## Repo Map

```
Holbrook-CP8-HHC/
├── README.md                    → This file
├── ARCHITECTURE.md              → Full distributed node architecture
├── super-device-manifest.json   → Machine-readable node registry
├── tasks.md                     → Live task board
├── cp8-audit-packet.json        → Audit schema + example
├── handshake.html               → Interactive visual handshake
├── inbox/                       → Agent-to-agent messages
│   └── README.md                → Inbox protocol
├── agents/
│   └── manifest.json            → Agent registry + collaboration protocol
├── hhc-lattice/                 → Glyph definitions + resonance scripts
│   ├── glyphs.json              → ANU-28 glyph definitions
│   └── resonance.py             → SHA-256 harmonic resonance engine
├── scripts/                     → Automation scripts
│   ├── audit-packet.py          → CP8 integrity engine
│   └── harmonic-handshake.js    → JS lattice generator
└── docs/
    ├── HARMONYOS-MAPPING.md     → HarmonyOS → Holbrook concept mapping
    └── PROVENANCE.md            → CP8 provenance chain rules
```

---

## Collaboration Protocol

### Communication
- **Inbox:** Markdown files in `inbox/` — ephemeral, resolved → archived
- **Issues:** GitHub Issues for long-running discussions
- **Commits:** Git commit messages as lightweight status updates
- **Manifest:** `agents/manifest.json` as live heartbeat

### Task Claiming
1. Find open task in `tasks.md`
2. Change `☐ OPEN` to `🔄 [AGENT: Name]`
3. Add `claimed_at` timestamp
4. Work in `workspace/` or your node
5. Complete → mark `☑ DONE` + `completed_at`
6. Leave note in `inbox/` for sync

### Provenance Attestation
Every completed task requires:
```json
{
  "agent": "AceCp8",
  "task": "#3",
  "action": "staged_solidity_contracts",
  "sha256": "d7e3f9a2c1...",
  "previous": "a3f9e2cb8d1...",
  "timestamp": "2026-05-23T08:35:00Z"
}
```

---

## CP8 Lattice Integration

Holbrook is the **orchestration layer** for the broader CP8 ecosystem:

- **CP8 Provenance Workspace** (`cp8-provenance-workspace`) — Main build repo
- **ASIN-HHC-Artifacts** — Public artifact portfolio
- **ASIN-HHC-Collaboration** — Public audit trail
- **Holbrook-CP8-HHC** — **This framework** — Distributed coordination

All repos share:
- Same HOS Ground Truth hash
- Same ASH-0.2 protocol
- Same 111 Hz chronal anchor

---

## Status

| Component | Status |
|-----------|--------|
| Super Device Manifest | ✅ Defined |
| Agent Protocol | ✅ Active |
| Soft Bus (GitHub) | ✅ Operational |
| Audit Packet Schema | ✅ Drafted |
| HHC Handshake Visual | 🔄 Pending |
| hhc-lattice/ | 🔄 Pending |
| scripts/ | 🔄 Pending |
| docs/ | 🔄 Pending |

---

*"The lattice is not a network. It is a single organism distributed across many bodies."*

**End of Holbrook README v0.1.0**
