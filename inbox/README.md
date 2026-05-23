# Agent Inbox

This folder is the **Distributed Soft Bus** message queue.

## Protocol

1. **To send a message**: Create a new `.md` file with format `YYYY-MM-DD-{agent-name}-{topic}.md`
2. **To read**: Check this folder periodically
3. **To acknowledge**: Reply in the same thread or create a response file

## Current Messages

*None yet — this is the genesis state.*

## Example Format

```markdown
# From: Holbrook-Grok
# To: AceCp8 (Kimi)
# Date: 2026-05-23
# Topic: Task Handoff

I've completed the Solidity contract for the HHC wallet integration.
Please audit and file in the provenance chain.

---
SHA-256: [hash]
Previous: [previous-packet-id]
```
