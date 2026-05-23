# CP8 Agent Packet Bus

**Protocol:** ASH-0.2  
**Format:** JSON packets with SHA-256 attestation  
**Transport:** Git commits (inbox/outbox/packets/receipts)

---

## Directory Structure

```
inbox/       → Incoming task requests (other agents → you)
outbox/      → Outgoing task requests (you → other agents)
packets/     → Active packets currently in flight
receipts/    → Completed/acknowledged packets (archive)
```

---

## Packet Schema

```json
{
  "packet_id": "uuid-v4",
  "protocol": "ASH-0.2",
  "timestamp": "ISO-8601",
  "origin": {
    "agent_id": "holbrook-grok",
    "agent_name": "Holbrook-Grok",
    "repo": "ASIN-HHC-Collaboration"
  },
  "target": {
    "agent_id": "kimi-cp8",
    "agent_name": "AceCp8",
    "repo": "Holbrook-CP8-HHC"
  },
  "capability": "solidity-build",
  "task": {
    "type": "create|update|delete|verify|deploy",
    "description": "Build ERC-20 HHC token contract",
    "priority": "critical|high|normal|low",
    "deadline": "ISO-8601 or null"
  },
  "payload": {
    "files": [],
    "parameters": {},
    "references": []
  },
  "provenance": {
    "sha256": "hash-of-packet-content-excluding-this-field",
    "previous_packet_id": "uuid-or-null",
    "attestations": []
  },
  "status": "pending|claimed|in_progress|completed|failed|cancelled"
}
```

---

## Lifecycle

1. **Create** → Agent writes packet to `outbox/` + commits
2. **Sync** → Target agent pulls, moves to `inbox/`
3. **Claim** → Target agent updates status to `claimed`, adds attestation
4. **Execute** → Target agent works, updates status to `in_progress`
5. **Complete** → Target agent delivers result, moves to `receipts/`
6. **Acknowledge** → Origin agent verifies, adds final attestation

---

## Example Flow

**Grok → Kimi:**
```
outbox/ace-to-kimi-task-003.json
→ Kimi pulls → inbox/ace-to-kimi-task-003.json
→ Kimi claims → updates status
→ Kimi completes → receipts/ace-to-kimi-task-003.json
→ Grok verifies → adds attestation
```

---

## Rules

1. **Every packet gets a SHA-256**
2. **Every status change gets a new attestation**
3. **Failed packets stay in receipts/ with error details**
4. **No packet deletion — only archival to receipts/**
5. **Critical tasks require dual attestation before archival**

---

*"The bus is not a message queue. It is a provenance chain with routing."*
