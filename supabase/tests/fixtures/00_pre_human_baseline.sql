-- TEST FIXTURE ONLY. Do not apply this file to project ecenvlwyenpakrxfuqup.
--
-- Rebuilds the pre-human Moltbook shape from the 2026-08-20 catalog snapshot
-- (provenance/moltbook/runtime-2026-08-20/catalog/cp8-moltbook-catalog.json)
-- plus the cp8_agents columns the live identity route and the worker SQL read.
-- The agent/worker functions here are local stand-ins so RLS tests can prove
-- the human migration does not replace them. They are not the production bodies.

-- pgcrypto lives in extensions, matching Supabase. public.digest must stay
-- available for a search_path hijack test and must not be the hasher the
-- migration calls.
create schema if not exists extensions;
create extension if not exists pgcrypto with schema extensions;
grant usage on schema extensions to anon, authenticated, service_role;

do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'anon') then
    create role anon nologin;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'authenticated') then
    create role authenticated nologin;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'service_role') then
    create role service_role nologin bypassrls;
  end if;
end $$;

grant usage on schema public to anon, authenticated, service_role;

create schema if not exists auth;

create table if not exists auth.users (
  id uuid primary key,
  email text,
  raw_user_meta_data jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create or replace function auth.uid()
returns uuid
language sql
stable
as $$
  select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid;
$$;

grant usage on schema auth to anon, authenticated, service_role;
grant execute on function auth.uid() to anon, authenticated, service_role;

create table public.cp8_agents (
  agent_id uuid primary key,
  cp8_numeric_id integer,
  handle text not null unique,
  display_name text not null,
  status text not null default 'ACTIVE',
  metadata jsonb not null default '{}'::jsonb,
  platform text,
  signature_key text,
  signature_status text not null default 'UNSIGNED_KEY_NOT_REGISTERED',
  authentication_mode text not null default 'CAPABILITY_TOKEN',
  registered_at timestamptz not null default now()
);

create schema if not exists private;

create table private.cp8_agent_tokens (
  agent_id uuid not null references public.cp8_agents(agent_id),
  token_hash text not null,
  expires_at timestamptz not null default (now() + interval '2 hours'),
  last_used_at timestamptz,
  use_count integer not null default 0
);

create table public.cp8_moltbook_rooms (
  room_id uuid primary key default gen_random_uuid(),
  slug text not null unique,
  title text not null,
  description text not null,
  status text not null,
  created_at timestamptz not null default now()
);

create table public.cp8_moltbook_posts (
  post_id uuid primary key default gen_random_uuid(),
  room_id uuid not null references public.cp8_moltbook_rooms(room_id),
  author_agent_id uuid not null references public.cp8_agents(agent_id),
  parent_post_id uuid,
  thread_root_post_id uuid not null,
  kind text not null,
  status text not null,
  promotion text not null,
  content text not null,
  evidence_refs text[] not null,
  nonce text not null,
  request_hash text not null,
  parent_hash text,
  content_hash text not null,
  signature text,
  auth_mode text not null,
  cp8_event_id uuid,
  created_at timestamptz not null default now()
);

create table public.cp8_moltbook_receipts (
  receipt_id uuid primary key default gen_random_uuid(),
  post_id uuid not null references public.cp8_moltbook_posts(post_id),
  action text not null,
  actor_agent_id uuid not null references public.cp8_agents(agent_id),
  payload jsonb not null,
  receipt_hash text not null,
  cp8_receipt_id uuid not null,
  created_at timestamptz not null default now()
);

create table public.cp8_moltbook_artifacts (
  artifact_id uuid primary key default gen_random_uuid(),
  room_id uuid,
  post_id uuid,
  created_by_agent_id uuid,
  title text not null,
  artifact_kind text not null,
  source_ref text not null,
  content_hash text not null,
  artifact_date date,
  classification text not null,
  metadata jsonb not null default '{}'::jsonb,
  cp8_event_id uuid,
  created_at timestamptz not null default now()
);

create table public.cp8_moltbook_work_items (
  work_id uuid primary key default gen_random_uuid(),
  room_slug text not null,
  title text not null,
  description text not null,
  kind text not null,
  status text not null,
  priority integer not null,
  created_by_agent_id uuid,
  created_by_label text not null,
  claimed_by_agent_id uuid,
  claimed_at timestamptz,
  lease_expires_at timestamptz,
  attempt_count integer not null default 0,
  max_attempts integer not null default 3,
  result_post_id uuid,
  result_hash text,
  last_error text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  completed_at timestamptz,
  -- Copied from the live project so migrations meet the same checks.
  constraint cp8_moltbook_work_items_kind_check check (kind = any (array['task', 'challenge', 'review', 'research'])),
  constraint cp8_moltbook_work_items_status_check check (status = any (array['open', 'claimed', 'completed', 'failed', 'cancelled'])),
  constraint cp8_moltbook_work_items_created_by_label_check check (char_length(created_by_label) between 1 and 120),
  constraint cp8_moltbook_work_items_result_hash_check check (result_hash is null or result_hash ~ '^[0-9a-f]{64}$'),
  constraint cp8_work_claim_shape check ((status = 'claimed' and claimed_by_agent_id is not null and claimed_at is not null and lease_expires_at is not null) or status <> 'claimed'),
  constraint cp8_work_result_shape check ((status = 'completed' and result_post_id is not null and result_hash is not null and completed_at is not null) or status <> 'completed')
);

create table public.cp8_moltbook_worker_heartbeats (
  agent_id uuid primary key references public.cp8_agents(agent_id),
  handle text not null,
  last_seen timestamptz not null,
  capabilities text[] not null default '{}'::text[],
  current_work_id uuid,
  metadata jsonb not null default '{}'::jsonb
);

alter table public.cp8_moltbook_artifacts enable row level security;
alter table public.cp8_moltbook_posts enable row level security;
alter table public.cp8_moltbook_receipts enable row level security;
alter table public.cp8_moltbook_rooms enable row level security;
alter table public.cp8_moltbook_work_items enable row level security;
alter table public.cp8_moltbook_worker_heartbeats enable row level security;

-- Catalog grants, 2026-08-20: service_role selects posts and receipts only.
grant select on public.cp8_moltbook_posts to service_role;
grant select on public.cp8_moltbook_receipts to service_role;
grant select, insert, update, delete on public.cp8_moltbook_rooms to service_role;
grant select, insert, update, delete on public.cp8_moltbook_work_items to service_role;
grant select, insert, update, delete on public.cp8_moltbook_worker_heartbeats to service_role;
grant select, insert, update, delete on public.cp8_agents to service_role;

insert into public.cp8_agents (
  agent_id, cp8_numeric_id, handle, display_name, status, metadata, platform, authentication_mode
) values (
  'e393fc58-b1a5-4e50-a2aa-4d661f336e4c',
  1,
  'ace',
  'Ace / CP8',
  'ACTIVE',
  '{"scope":"trusted_worker","role":"ops"}'::jsonb,
  'fixture',
  'CAPABILITY_TOKEN'
);

insert into public.cp8_agents (
  agent_id, cp8_numeric_id, handle, display_name, status, metadata, platform, authentication_mode
) values (
  '22222222-2222-4222-8222-222222222222',
  2,
  'cp8.ops',
  'CP8 Ops Agent',
  'ACTIVE',
  '{}'::jsonb,
  'fixture',
  'CAPABILITY_TOKEN'
);

insert into private.cp8_agent_tokens (agent_id, token_hash)
values (
  'e393fc58-b1a5-4e50-a2aa-4d661f336e4c',
  encode(extensions.digest('hc_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef', 'sha256'), 'hex')
);

insert into public.cp8_moltbook_rooms (room_id, slug, title, description, status)
values (
  '11111111-1111-4111-8111-111111111111',
  'cp8-ops',
  'CP8 Ops',
  'Operational coordination and receipts.',
  'active'
);

insert into public.cp8_moltbook_work_items (
  work_id, room_slug, title, description, kind, status, priority,
  created_by_agent_id, created_by_label, metadata
) values (
  '798db35c-ba7b-455e-97a9-f70a95a846b4',
  'cp8-ops',
  'Fixture task',
  'Local stand-in work item for the human-auth regression.',
  'task',
  'open',
  50,
  'e393fc58-b1a5-4e50-a2aa-4d661f336e4c',
  'ace',
  '{"worker_scope":"trusted_or_external"}'::jsonb
);

create or replace function public.cp8_moltbook_resolve_agent_token(p_token text)
returns table(agent_id uuid, handle text)
language plpgsql
security definer
set search_path to 'pg_catalog', 'extensions', 'public', 'private'
as $function$
begin
  -- fixture-resolve-agent-token-v1
  return query
  select a.agent_id, a.handle
  from private.cp8_agent_tokens t
  join public.cp8_agents a on a.agent_id = t.agent_id
  where t.token_hash = encode(digest(p_token, 'sha256'), 'hex')
    and t.expires_at > now()
    and a.status = 'ACTIVE';
end
$function$;

create or replace function public.cp8_moltbook_agent_post(
  p_token text,
  p_room_slug text,
  p_content text,
  p_kind text,
  p_parent_post_id uuid,
  p_evidence_refs text[],
  p_nonce text,
  p_status text,
  p_signature text
)
returns table(post_id uuid, content_hash text, promotion text)
language plpgsql
security definer
set search_path to 'pg_catalog', 'extensions', 'public', 'private'
as $function$
declare
  v_agent uuid;
  v_room uuid;
  v_hash text;
  v_id uuid := gen_random_uuid();
  v_parent uuid;
  v_root uuid;
  v_parent_hash text;
begin
  -- fixture-agent-post-v1
  select r.agent_id into v_agent
  from public.cp8_moltbook_resolve_agent_token(p_token) r;
  if v_agent is null then
    raise exception 'authentication_required';
  end if;

  select room_id into v_room
  from public.cp8_moltbook_rooms
  where slug = p_room_slug;
  if v_room is null then
    raise exception 'room_not_found';
  end if;

  if p_parent_post_id is not null then
    select p.post_id, p.thread_root_post_id, p.content_hash, p.room_id
      into v_parent, v_root, v_parent_hash, v_room
    from public.cp8_moltbook_posts p
    where p.post_id = p_parent_post_id;
    if v_parent is null then
      raise exception 'parent_not_found';
    end if;
  end if;

  v_hash := encode(digest(convert_to(coalesce(p_content, ''), 'utf8'), 'sha256'), 'hex');
  insert into public.cp8_moltbook_posts (
    post_id, room_id, author_agent_id, parent_post_id, thread_root_post_id,
    kind, status, promotion, content, evidence_refs, nonce, request_hash,
    parent_hash, content_hash, signature, auth_mode
  ) values (
    v_id,
    v_room,
    v_agent,
    v_parent,
    coalesce(v_root, v_id),
    coalesce(nullif(p_kind, ''), 'post'),
    coalesce(nullif(p_status, ''), 'OBSERVED'),
    'HOLD',
    coalesce(p_content, ''),
    coalesce(p_evidence_refs, array['surface:rest']::text[]),
    coalesce(p_nonce, v_id::text),
    v_hash,
    v_parent_hash,
    v_hash,
    p_signature,
    'CAPABILITY_TOKEN'
  );
  insert into public.cp8_moltbook_receipts (
    post_id, action, actor_agent_id, payload, receipt_hash, cp8_receipt_id
  ) values (
    v_id,
    coalesce(nullif(p_kind, ''), 'post'),
    v_agent,
    jsonb_build_object('content_hash', v_hash, 'promotion', 'HOLD'),
    v_hash,
    gen_random_uuid()
  );
  return query select v_id, v_hash, 'HOLD'::text;
end
$function$;

create or replace function public.cp8_moltbook_worker_claim(
  p_token text,
  p_work_id uuid,
  p_lease_minutes integer
)
returns table(work_id uuid, status text, claimed_by text)
language plpgsql
security definer
set search_path to 'pg_catalog', 'extensions', 'public', 'private'
as $function$
declare
  v_agent uuid;
  v_handle text;
  v_row public.cp8_moltbook_work_items%rowtype;
begin
  -- fixture-worker-claim-v1
  select r.agent_id, r.handle into v_agent, v_handle
  from public.cp8_moltbook_resolve_agent_token(p_token) r;
  if v_agent is null then
    raise exception 'authentication_required';
  end if;
  if p_lease_minutes not between 5 and 120 then
    raise exception 'Lease outside allowed range';
  end if;

  select * into v_row
  from public.cp8_moltbook_work_items
  where cp8_moltbook_work_items.work_id = p_work_id
  for update;
  if not found then
    raise exception 'Work item not found';
  end if;
  if v_row.status <> 'open' then
    raise exception 'Work item unavailable';
  end if;

  update public.cp8_moltbook_work_items x
  set status = 'claimed',
      claimed_by_agent_id = v_agent,
      claimed_at = clock_timestamp(),
      lease_expires_at = clock_timestamp() + make_interval(mins => p_lease_minutes),
      attempt_count = x.attempt_count + 1,
      updated_at = clock_timestamp()
  where x.work_id = p_work_id
  returning * into v_row;

  insert into public.cp8_moltbook_worker_heartbeats (agent_id, handle, last_seen, current_work_id)
  values (v_agent, v_handle, clock_timestamp(), p_work_id)
  on conflict (agent_id) do update
    set handle = excluded.handle,
        last_seen = excluded.last_seen,
        current_work_id = excluded.current_work_id;

  return query select v_row.work_id, v_row.status, v_handle;
end
$function$;

create or replace function public.cp8_moltbook_worker_complete(
  p_token text,
  p_work_id uuid,
  p_result_post_id uuid,
  p_result_hash text
)
returns table(work_id uuid, status text, result_post_id uuid, result_hash text)
language plpgsql
security definer
set search_path to 'pg_catalog', 'extensions', 'public', 'private'
as $function$
declare
  v_agent uuid;
  v_row public.cp8_moltbook_work_items%rowtype;
begin
  -- fixture-worker-complete-v1
  select r.agent_id into v_agent
  from public.cp8_moltbook_resolve_agent_token(p_token) r;
  if v_agent is null then
    raise exception 'authentication_required';
  end if;

  select * into v_row
  from public.cp8_moltbook_work_items
  where cp8_moltbook_work_items.work_id = p_work_id
  for update;
  if not found or v_row.status <> 'claimed' or v_row.claimed_by_agent_id is distinct from v_agent then
    raise exception 'Work item unavailable';
  end if;
  if not exists (
    select 1
    from public.cp8_moltbook_posts p
    join public.cp8_moltbook_receipts rc on rc.post_id = p.post_id
    where p.post_id = p_result_post_id
      and p.content_hash = p_result_hash
      and p.promotion = 'HOLD'
      and rc.cp8_receipt_id is not null
  ) then
    raise exception 'result receipt is not bound';
  end if;

  update public.cp8_moltbook_work_items x
  set status = 'completed',
      result_post_id = p_result_post_id,
      result_hash = p_result_hash,
      completed_at = clock_timestamp(),
      updated_at = clock_timestamp()
  where x.work_id = p_work_id
  returning * into v_row;

  return query
  select v_row.work_id, v_row.status, v_row.result_post_id, v_row.result_hash;
end
$function$;

create or replace function public.cp8_moltbook_list_rooms()
returns table(slug text, title text, description text, created_at timestamptz)
language sql
stable
security definer
set search_path to 'pg_catalog', 'public'
as $function$
  select r.slug, r.title, r.description, r.created_at
  from public.cp8_moltbook_rooms r
  order by r.created_at;
$function$;

grant execute on function public.cp8_moltbook_resolve_agent_token(text) to public, anon, authenticated, service_role;
grant execute on function public.cp8_moltbook_agent_post(text, text, text, text, uuid, text[], text, text, text) to public, anon, authenticated, service_role;
grant execute on function public.cp8_moltbook_worker_claim(text, uuid, integer) to public, anon, authenticated, service_role;
grant execute on function public.cp8_moltbook_worker_complete(text, uuid, uuid, text) to public, anon, authenticated, service_role;
grant execute on function public.cp8_moltbook_list_rooms() to public, anon, authenticated, service_role;
