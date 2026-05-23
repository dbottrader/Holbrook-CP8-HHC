# Skill: CP8 Agent Handoff Protocol

**Skill ID:** `skill-cp8-agent-handoff-v1.0`
**Protocol:** ASIN-HHC Law 428 / Holbrook-CP8-HHC

---

## Purpose

Enable deterministic state transfer between agents (Grok, Kimi, Claude, human operators) with cryptographic provenance.

---

## Handoff Packet Schema

```json
{
  "packet_id": "pkt-{timestamp}-{nonce}",
  "origin": "agent-{name}-{version}",
  "target_agent": "agent-{name}-{version}",
  "capability": "<skill-id>",
  "payload_sha256": "sha256-of-payload",
  "parent_packet": "pkt-{prev-id}",
  "timestamp": "ISO8601",
  "signature": "agent-sig"
}
```

## Flow

1. Origin writes packet to `outbox/`
2. Bus moves packet to `inbox/` of target
3. Target validates `payload_sha256` + `signature`
4. Target executes capability
5. Target writes receipt to `receipts/`
6. Origin verifies receipt and archives packet to `packets/`

## Verification Steps

1. Recompute Merkle root of repo
2. Verify packet hash against manifest
3. Check agent signature against registry
4. Confirm parent_packet exists in chain
5. Validate capability against `skills/` manifest

## Memory Anchor Points

- `HOS_GROUND_TRUTH_HASH`: `63b5160ef51f0464295e86888c3e6605d8f6cc970635183887083818e8749320`
- `MASTER_BUILD_HASH`: `25eca922f12a902d8b946bb2259e2b49d0346c2ecd3920d75364cf09ee720e14`
- `BTC_ADDRESS`: `bc1qn9gzdy63e5us3z7q4l7tca47cmrceynvqvgfmd`

---
*CP8 Protocol • ASIN-HHC Framework • Holbrook Distributed Lattice*
