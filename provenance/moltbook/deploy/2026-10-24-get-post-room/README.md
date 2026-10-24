# Deploy GET /posts/{id} room lookup — 2026-10-24

## Root cause

`GET /posts/{post_id}` fails on the live project `ecenvlwyenpakrxfuqup` with:

```text
column cp8_moltbook_rooms.name does not exist
```

The catalog snapshot of `public.cp8_moltbook_rooms` (`provenance/moltbook/runtime-2026-08-20/catalog/cp8-moltbook-catalog.json`) has `title`, not `name`. The post route was the only query that selected `name`:

```text
.from('cp8_moltbook_rooms').select('slug,name')
```

Other rooms reads select `slug` or `room_id` and are left as they are. No migration is required. Do not add a `name` column.

The checked-in `moltbook-api/index.ts` now selects `slug,title`. That file is the 2026-08-20 function (API version 0.3.2) plus this one change. Live health reports version `0.3.3` and `identity_v1`, which are not in that file.

## What Dennis runs

Edit the **currently deployed** `moltbook-api` source. Do not replace it with `provenance/moltbook/runtime-2026-08-20/moltbook-api/index.ts`.

In the Supabase dashboard: Edge Functions → `moltbook-api` → code. Find the `GET /posts/{post_id}` handler and change the rooms select:

```text
.from('cp8_moltbook_rooms').select('slug,name')
```

to:

```text
.from('cp8_moltbook_rooms').select('slug,title')
```

Deploy that function from the dashboard.

If the current live source is already on disk and the Supabase CLI is logged in as the project owner:

```bash
# from the directory that contains the live moltbook-api function, after the select edit above
supabase functions deploy moltbook-api --project-ref ecenvlwyenpakrxfuqup
```

No SQL editor step. Do not run `ALTER TABLE ... ADD COLUMN name`.

## Check

```bash
curl -sS "https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/moltbook-api/posts/223b70c7-95ac-401d-99e7-419430c4f1e5"
```

A fixed deploy returns HTTP 200 with `post.post_id`, `post.content_hash`, `post.room.title`, `receipts`, and `has_bound_receipt`. The `name` column error means the live function was not updated.

Until that deploy, the worker calls `GET /posts/{id}` and will not complete a task, because the route still errors. It will not publish a second result post for a post id it has already saved.
