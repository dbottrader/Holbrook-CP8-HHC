# Outbox

Outgoing task requests and messages to other agents.

**Protocol:** Write by sender. Read-only for recipient (after sync).

## Naming Convention

```
outbox/{sender-agent-id}_to_{recipient-agent-id}_{timestamp}_{topic}.md
```

## Format

Same as inbox, but with explicit `expected_response` field.

## Sync

Outbox files are committed and pushed. Recipient pulls and moves to their inbox.

## Rules

1. **Only write your own outbox files**
2. **Commit before expecting recipient to see it**
3. **Include packet_id reference for tracked tasks**
