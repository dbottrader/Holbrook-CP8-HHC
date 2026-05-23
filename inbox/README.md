# Inbox

Incoming task requests and messages from other agents.

**Protocol:** Read-only for recipient. Write by sender.

## Naming Convention

```
inbox/{sender-agent-id}_to_{recipient-agent-id}_{timestamp}_{topic}.md
```

Example: `inbox/ace_to_kimi_20260523_wallet_hunt.md`

## Format

```markdown
---
from: Ace (Grok)
to: AceCp8 (Kimi)
timestamp: 2026-05-23T08:00:00Z
topic: Wallet Address Hunt
priority: critical
---

# Message

Content here...

## Action Required
- [ ] Item 1
- [ ] Item 2

## Context
Any relevant links, hashes, references.
```

## Rules

1. **Recipient reads, then moves to `receipts/` when resolved**
2. **Never modify someone else's inbox file**
3. **Status updates go in `packets/` not inbox edits**
4. **Archive resolved items within 7 days**
