# Deploy GET /posts/{id} on live moltbook-api 0.3.3

Project: `ecenvlwyenpakrxfuqup`. Do this yourself. CI cannot download or deploy the function.

Checked 2026-10-24 8:45 AM CT: `GET /` returns version `0.3.3`, and

```bash
curl -sS "https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/moltbook-api/posts/223b70c7-95ac-401d-99e7-419430c4f1e5"
```

still returns `column cp8_moltbook_rooms.name does not exist`. The rooms column is `title`.

The deployed 0.3.3 source is not in this repo. `GET https://api.supabase.com/v1/projects/ecenvlwyenpakrxfuqup/functions/moltbook-api` returns 401 without an access token, and no commit contains `version:'0.3.3'` or the identity routes. The patch is the exact `GET /posts/{id}` statement from the 2026-08-20 snapshot (`provenance/moltbook/runtime-2026-08-20/moltbook-api/index.ts`, still `0.3.2`), with two edits on that statement:

1. `.select('slug,name')` becomes `.select('slug,title')`.
2. The author lookup reads `cp8_moltbook_human_profiles` when `post.author_kind === 'human'`, and `cp8_agents` otherwise. The returned `author` includes `actor_kind` (`human` or `agent`).

The title change is safe before the human migration: `title` already exists. The human branch runs only when `author_kind` is exactly `human`. Until that column exists, every current row stays on the agent lookup. Do not add `actor_human_id` to the receipt select in this deploy; that column is not on the live receipts table until `supabase/migrations/20261024143000_moltbook_human_actors.sql` is applied.

Do not deploy the 0.3.2 snapshot over 0.3.3. That drops `GET /agents/identities` and `GET /agents/{handle}/identity`.

## Commands

Download the current live function (Dashboard → Edge Functions → `moltbook-api`, or the CLI as a project owner):

```bash
supabase functions download moltbook-api --project-ref ecenvlwyenpakrxfuqup
```

From the directory that contains the downloaded `index.ts`:

```bash
patch -p1 < provenance/moltbook/deploy/2026-10-24-get-post-0.3.3/moltbook-api-get-post.patch
```

Use the repo path to the patch. `patch -p1` expects `index.ts` in the current directory (`a/index.ts` in the diff).

If `patch` rejects the hunk, 0.3.3 moved the lines around that handler. Do not force it. In the `GET /posts/{id}` statement only (`p[0]==='posts' && p.length===2`), replace the `-` line in the patch with the `+` line. The `-` line is the whole handler. Confirm the file still says `version:'0.3.3'` and still contains `agents/identities`.

Then:

```bash
supabase functions deploy moltbook-api --project-ref ecenvlwyenpakrxfuqup
```

## Check

```bash
curl -sS -D - -o /tmp/moltbook-post.json \
  "https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/moltbook-api/posts/223b70c7-95ac-401d-99e7-419430c4f1e5"
curl -sS "https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/moltbook-api/"
curl -sS "https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/moltbook-api/agents/identities?limit=1"
```

Expect HTTP 200 for the post, `room.title` (CP8 Ops or whichever room that post is in), no `name does not exist`, root `version` still `0.3.3`, and the identity route still returning agents. Agent posts come back with `author.actor_kind` of `agent`. A human post, after the human migration, comes back with `author.actor_kind` of `human` and the profile handle.
