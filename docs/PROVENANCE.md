# CP8 Provenance Chain Rules

**Version:** 0.1.0
**Protocol:** ASH-0.2
**Hash Algorithm:** SHA-256
**HOS Ground Truth:** `63b5160ef51f0464295e86888c3e6605d8f6cc970635183887083818e8749320`

---

## Philosophy

Provenance is not logging. Logging records what happened. Provenance records what happened **in a way that cannot be lied about.**

---

## Rules

### Rule 1: Every Action is a Packet
Every significant action generates a CP8 audit packet.

### Rule 2: Every Packet Hashes Its Content
The SHA-256 of a packet is computed from its content, excluding the hash field itself.

### Rule 3: Every Packet Links to the Previous
The provenance chain is a linked list. The genesis packet has `previous_packet_id: null`.

### Rule 4: Critical Actions Require Multi-Agent Attestation
Tasks marked 🔴 CRITICAL require sign-off from both agents.

### Rule 5: The Human is the Root of Trust
Dennis is the ultimate authority. Agents recommend, prepare, and draft. Dennis approves on-chain transactions and sensitive releases.

### Rule 6: Git Commits Are Lightweight Packets
Every git commit message is a lightweight provenance packet.

### Rule 7: Cross-Repo Actions Must Log in All Affected Repos
If an action spans multiple repos, log it in each.

### Rule 8: Failed Actions Log Too
If an action fails but modified state, log the failure.

---

## Verification Protocol

### Daily Verification (Automated)
```bash
cd ~/.openclaw/workspace
git fsck --full
python3 Holbrook-CP8-HHC/scripts/audit-packet.py --action verify
```

### Weekly Verification (Manual)
1. Review `audit-packets.jsonl` for gaps
2. Verify all 🔴 CRITICAL tasks have dual attestation
3. Check `super-device-manifest.json` matches actual repo state

### Monthly Verification (Deep Audit)
1. Full SHA-256 verification of all files
2. Review agent capability drift
3. Check for unauthorized access attempts

---

## Threat Model

| Threat | Mitigation |
|--------|-----------|
| Agent impostor | SHA-256 attestation + manifest verification |
| Git history tampering | SHA-256 chain + remote backup |
| Token compromise | PAT with minimal scope |
| Drive data loss | GitHub as hot backup |
| Agent disagreement | Human arbitration |

---

*"Trust but verify. Then verify the verification. Then hash it."*

**End of Provenance Rules v0.1.0**
