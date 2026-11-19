# Archived live edge-function sources (previously unsourced)

These four Supabase Edge Functions were live on project `ecenvlwyenpakrxfuqup` with no matching source in any public repo branch (inventory of 2026-11-18). The copies below were re-pulled from the live project on 2026-11-19 at 3:16 AM CT and are byte-identical to `/workspace/inventory/sb_src/` on the operator box.

| Function | Live version | verify_jwt |
|---|---:|---|
| cp8-groq-inference | 5 | false |
| cp8-control | 4 | true |
| cp8-witness-tip | 5 | false |
| cp8-agent | 4 | false |

Secrets are read from `Deno.env` only. A scan of these files found no hardcoded key or token literals. Do not add secrets in review comments or follow-up commits.

This PR is an archive of the live sources so they have a git home. It does not deploy, redeploy, or merge itself. Leave it unmerged until Dennis reviews it.

Hashes: see `supabase/functions/UNSOURCED-ARCHIVE-HASHES.md`.
