# Receipts

Completed, acknowledged, or cancelled packets.

**Protocol:** Append-only archive. No modifications.

## Structure

```
receipts/
├── completed/     → Successfully finished tasks
├── failed/        → Failed attempts with error logs
├── cancelled/     → Cancelled/abandoned tasks
└── archived/      → Old receipts (>90 days)
```

## Retention

- **Active receipts:** 90 days in root
- **Archived:** Moved to `receipts/archived/{year}/{month}/`
- **Audit requirement:** Never delete, only archive

## Search

Use grep for quick lookup:
```bash
grep -r "task-003" receipts/
grep -r "wallet" receipts/completed/
```
