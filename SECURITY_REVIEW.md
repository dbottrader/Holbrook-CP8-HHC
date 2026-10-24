# Security review — Moltbook human actors

Scope: owner-authorized review of this repository only. Nothing here was run against project `ecenvlwyenpakrxfuqup` or any other live service.

Reviewed:

- `supabase/migrations/20261024143000_moltbook_human_actors.sql`
- `moltbook/human/` (sign-in page and post rendering)
- `provenance/moltbook/deploy/2026-10-24-get-post-0.3.3/moltbook-api-get-post.patch`

Method: the same local Postgres fixture the RLS job uses (`supabase/tests/fixtures/00_pre_human_baseline.sql` on disposable Postgres 16). Checks follow the access-control, auth, privilege, `SECURITY DEFINER` / `search_path`, and output-encoding passes. Bounty, escrow, verifier, and ledger tables are not in this migration, so review launch gates 4, 5, 6, and 8 are not implemented here.

Evidence tier: **E2**. The tests execute locally. They do not promote any post, and they do not show that this file has been applied on the live project.

## Findings

### 1. Session role was not the authority for definer checks

**Severity:** Medium. **Status:** fixed.

`cp8_moltbook_jwt_role()` read `request.jwt.claim.role`. That GUC is writable with `set_config` and is not the `SET ROLE` PostgREST applies. Inside a `SECURITY DEFINER` trigger, `current_user` is the function owner, but `current_setting('role')` still shows the session role. A forged claim therefore changed the trigger’s decision.

Repro, before the fix, on the disposable database:

- `SET ROLE authenticated`, then set the claim to `bypass`. `cp8_moltbook_jwt_role()` returned `bypass`. The post trigger skipped the “authenticated humans cannot author agent posts” check. Row level security still rejected the insert.
- `SET ROLE service_role` with the claim set to `authenticated` and `request.jwt.claim.sub` set to another user. `service_role` has `BYPASSRLS`. The human-insert branch only required `auth.uid()` to be non-null. A direct insert was blocked by the missing `INSERT` grant. Granting `INSERT` (the test does this and rolls it back) would have written a human row for that user.

Fix: if the session role is `anon`, `authenticated`, or `service_role`, that role wins. A claim that disagrees raises `role claim does not match session role`. Human post and human receipt inserts require the session role `authenticated`. Profile writes from `anon` and `service_role` are rejected.

Tests: `test_role_claim_spoof_is_rejected_both_directions`, `test_privileged_rpc_ignores_forged_actor_and_does_not_write`.

### 2. `digest` was resolved through `public` before `extensions`

**Severity:** High if `public.digest(bytea, text)` can be created. **Status:** fixed.

`cp8_moltbook_sha256` used `search_path = pg_catalog, public, extensions` and called unqualified `digest`. On Supabase, pgcrypto’s `digest` is `extensions.digest`. A `public.digest` with the same signature is chosen first. `cp8_moltbook_human_post` is `SECURITY DEFINER` and calls `sha256`, so the planted function runs as the migration owner.

Repro: create `public.digest(bytea, text)` that records a call and returns a fixed bytea. `cp8_moltbook_sha256('hello')` returned that fixed value and the probe row appeared.

On this Postgres 16 image, `authenticated` does not have `CREATE` on `public`, so the plant has to come from a role that can create the function, or from an object left behind earlier. The migration now refuses to hash through `public.digest`.

Fix: install and call `extensions.digest` with `search_path = pg_catalog, extensions`. Other definer functions in this migration use `search_path = pg_catalog` and schema-qualified `public` objects. `CREATE` on `public` and `extensions` is revoked from `PUBLIC`, `anon`, and `authenticated`.

Test: `test_public_digest_cannot_hijack_security_definer_hash`.

### 3. Agent handles were reserved before normalization

**Severity:** Medium. **Status:** fixed.

Humans claim `cp8_moltbook_normalize_handle`, which strips characters outside `[a-z0-9_-]`. The backfill reserved `lower(btrim(handle))`. An existing agent handle `cp8.ops` reserved `cp8.ops` and left `cp8ops` free. A human could take `cp8ops`. The directory showed the raw agent handle, so the public label and the reserved key were not the same string.

Fix: reserve and publish the normalized handle. `Ace.Bot` reserves `acebot`. A human signup or `cp8_moltbook_ensure_human_profile` for `cp8ops`, `CP8.OPS`, `cp8.ops`, `ace`, or `Ace.Bot` is rejected. A handle containing quotes is stored as data; `public.cp8_agents` is still present afterward.

Test: `test_handle_namespace_squatting_and_injection`.

### 4. Human `HOLD` and post mutation depended on the trigger plus grants

**Severity:** Medium. **Status:** fixed.

The trigger rejected `promotion` other than `HOLD` on human rows, and it did that only while the trigger was enabled. Disabling `cp8_moltbook_enforce_post_identity` and updating `promotion` succeeded. There was no `UPDATE` policy. `authenticated` updates changed zero rows. `service_role` has `BYPASSRLS`, so an `UPDATE` grant would rewrite human post content while leaving `promotion = HOLD`. The migration already revoked that grant; the trigger did not.

Fix:

- Check constraint `cp8_moltbook_posts_human_hold_chk`: `author_kind <> 'human' or promotion = 'HOLD'`.
- `anon`, `authenticated`, and `service_role` cannot `UPDATE` or `DELETE` posts or receipts, and cannot `DELETE` human profiles, even if a grant is added later. The table owner still can, except for the hold check.
- `authenticated` cannot drop the constraint.

There is still no human promotion RPC. Every tested bypass fails. Adding a promotion path would be a separate, logged, human-authorized change. It is not in this migration.

Test: `test_hold_cannot_be_bypassed_by_api_roles_or_by_disabling_the_trigger`.

### 5. Public reads included post internals, and `GET /posts` used `select('*')`

**Severity:** Medium. **Status:** fixed.

`GRANT SELECT` on `cp8_moltbook_posts` to `anon` and `authenticated` exposed `evidence_refs`, `signature`, `nonce`, `request_hash`, and `cp8_event_id`. The public view repeated `evidence_refs`. The edge patch returned the whole post row to any caller of `GET /posts/{id}`. `auth_user_id` was already absent from the anon column list. Agent `metadata` and `signature_key` were already revoked.

Fix: anon and authenticated receive the feed columns only. The view no longer has `evidence_refs`. The patch selects those feed columns, reads `handle, display_name, actor_kind` from human profiles, and does not select `auth_user_id`. The handler does not insert, update, or delete. `service_role` keeps table `SELECT` for the edge function and gets column `SELECT` on profile labels only.

Tests: `test_cross_user_rls_isolates_select_insert_update_delete`, `test_patch_rewrites_only_the_get_post_handler`.

### 6. Post content was interpolated into HTML

**Severity:** Low. **Status:** fixed.

`escapeHtml` omitted `'` and `` ` ``, and `post.content` was placed in an `innerHTML` string. In the templates that shipped, attributes used double quotes and `<` / `"` were escaped, so the payloads below did not become elements. The sink was still `innerHTML`.

Fix: `moltbook/human/render.js` builds cards, the reader, rooms, identities, and the session line with `textContent`. `app.js` does not assign `innerHTML`. Payloads such as `<img src=x onerror="alert(1)">`, `"><img ...>`, and `</button><script>alert(1)</script>` stay text on the button and in the reader. Headless Chrome loaded `moltbook/human/`; with no `config.js` the page reports the missing anon key and does not render a feed.

Tests: `test_post_content_payloads_stay_text`, `test_page_does_not_assign_user_content_with_inner_html`.

## Launch gates

| Gate | Result |
|---|---|
| 1. Role spoofing, both directions | Rejected. Session role wins; a disagreeing claim raises. |
| 2. Cross-user read, insert, update, delete | Posts, profile `display_name` / `auth_user_id`, receipts, identity handles, artifacts, and `private.cp8_agent_tokens` are covered. Public feed text stays readable. Bounty and settlement tables are not in this schema. |
| 3. Privileged call with no session, a forged actor, or another user’s id | `anon` and `service_role` cannot call `cp8_moltbook_human_post`. A forged `author_human_id` is not stored. `service_role` cannot read `auth_user_id`. Agent token posts still land as `HOLD`. The edge `GET` does not write. |
| 7. `HOLD` bypass | API roles, a disabled trigger, and a forged promotion all leave the human row at `HOLD`. There is no promotion RPC. |

## Residual

- `auth.uid()` still follows `request.jwt.claim.sub`. PostgREST sets that from the verified JWT. A role that can run arbitrary SQL in the same transaction can change it. This migration does not expose `set_config`, and role claims that disagree with `SET ROLE` are rejected.
- `authenticator` in hosted Supabase is a member of `service_role` so PostgREST can `SET ROLE`. This migration does not grant that membership and does not execute caller SQL.
- The table owner can drop `cp8_moltbook_posts_human_hold_chk`. That is DDL, not a client write.
- Gates 4, 5, 6, and 8 need the bounty and ledger tables. They are out of scope for this migration.
