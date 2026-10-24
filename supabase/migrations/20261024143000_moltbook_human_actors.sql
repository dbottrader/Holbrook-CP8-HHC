-- Human actors on the existing Moltbook tables.
-- Project: ecenvlwyenpakrxfuqup
-- Apply this file only. Do not apply supabase/tests/fixtures/00_pre_human_baseline.sql.
--
-- Evidence: E2 until this file is applied on the live project and a human
-- signup/post is replayed there. Promotion of any post remains HOLD.
-- This migration does not replace cp8_moltbook_agent_post or the worker RPCs.
-- It does not deploy an Edge Function.

-- Hash in extensions (Supabase pgcrypto). Never resolve digest through public.
create schema if not exists extensions;
create extension if not exists pgcrypto with schema extensions;
do $$
begin
  if to_regprocedure('extensions.digest(bytea, text)') is null then
    raise exception 'extensions.digest(bytea, text) is required; public.digest is not used';
  end if;
end $$;

do $$
begin
  if to_regclass('auth.users') is null then
    raise exception 'auth.users is missing. Apply this on the Supabase project (or the local pre-human fixture), not an empty database.';
  end if;
  if to_regclass('public.cp8_moltbook_posts') is null
     or to_regclass('public.cp8_moltbook_rooms') is null
     or to_regclass('public.cp8_moltbook_receipts') is null then
    raise exception 'cp8_moltbook_posts/rooms/receipts are missing. This migration alters the existing Moltbook tables.';
  end if;
end $$;

create or replace function public.cp8_moltbook_sha256(p_text text)
returns text
language sql
immutable
set search_path to pg_catalog, extensions
as $$
  select encode(digest(convert_to(coalesce(p_text, ''), 'utf8'), 'sha256'), 'hex');
$$;

create table if not exists public.cp8_moltbook_human_profiles (
  human_id uuid primary key default gen_random_uuid(),
  auth_user_id uuid not null unique references auth.users(id) on delete cascade,
  handle text not null unique,
  display_name text not null,
  actor_kind text not null default 'human',
  created_at timestamptz not null default now(),
  constraint cp8_moltbook_human_profiles_kind_chk check (actor_kind = 'human'),
  constraint cp8_moltbook_human_profiles_handle_chk check (handle ~ '^[a-z0-9][a-z0-9_-]{1,62}$'),
  constraint cp8_moltbook_human_profiles_name_chk check (char_length(btrim(display_name)) between 1 and 120)
);

create table if not exists public.cp8_moltbook_identity_handles (
  handle text primary key,
  actor_kind text not null,
  human_id uuid unique references public.cp8_moltbook_human_profiles(human_id) on delete cascade,
  agent_id uuid unique,
  created_at timestamptz not null default now(),
  constraint cp8_moltbook_identity_handles_kind_chk check (actor_kind in ('human', 'agent')),
  constraint cp8_moltbook_identity_handles_shape_chk check (
    (actor_kind = 'human' and human_id is not null and agent_id is null)
    or
    (actor_kind = 'agent' and agent_id is not null and human_id is null)
  )
);

create or replace function public.cp8_moltbook_normalize_handle(p_handle text)
returns text
language plpgsql
immutable
set search_path to pg_catalog
as $$
declare
  v text;
begin
  v := lower(btrim(coalesce(p_handle, '')));
  v := regexp_replace(v, '[^a-z0-9_-]', '', 'g');
  v := regexp_replace(v, '^[^a-z0-9]+', '', 'g');
  v := left(v, 63);
  if v is null or v !~ '^[a-z0-9][a-z0-9_-]{1,62}$' then
    return null;
  end if;
  return v;
end $$;

-- Session role (SET ROLE / current_setting('role')) is authoritative.
-- request.jwt.claim.role is a GUC the caller can overwrite with set_config.
-- A claim that disagrees with anon, authenticated, or service_role is rejected.
-- Outside those roles (table owner, auth signup) the claim is only a label.
create or replace function public.cp8_moltbook_jwt_role()
returns text
language plpgsql
stable
set search_path to pg_catalog
as $$
declare
  v_session text := current_setting('role');
  v_claim text := coalesce(
    nullif(current_setting('request.jwt.claim.role', true), ''),
    nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'role',
    ''
  );
begin
  if v_session in ('anon', 'authenticated', 'service_role') then
    if v_claim <> '' and v_claim is distinct from v_session then
      raise exception 'role claim does not match session role';
    end if;
    return v_session;
  end if;
  return v_claim;
end $$;

-- Reserve existing agent handles before any human can take them.
do $$
begin
  if to_regclass('public.cp8_agents') is null then
    raise exception 'public.cp8_agents is missing. Human/agent handle separation needs the existing agent registry.';
  end if;
  if exists (
    select 1
    from public.cp8_agents a
    join public.cp8_agents b
      on public.cp8_moltbook_normalize_handle(a.handle)
       = public.cp8_moltbook_normalize_handle(b.handle)
     and public.cp8_moltbook_normalize_handle(a.handle) is not null
     and a.agent_id <> b.agent_id
  ) then
    raise exception 'cp8_agents has two rows with the same handle; resolve that before adding human identities';
  end if;
end $$;

insert into public.cp8_moltbook_identity_handles (handle, actor_kind, agent_id)
select public.cp8_moltbook_normalize_handle(a.handle), 'agent', a.agent_id
from public.cp8_agents a
where public.cp8_moltbook_normalize_handle(a.handle) is not null
and not exists (
  select 1 from public.cp8_moltbook_identity_handles i where i.agent_id = a.agent_id
)
and not exists (
  select 1
  from public.cp8_moltbook_identity_handles i
  where i.handle = public.cp8_moltbook_normalize_handle(a.handle)
    and i.agent_id is distinct from a.agent_id
);

do $$
begin
  if exists (
    select 1
    from public.cp8_agents a
    left join public.cp8_moltbook_identity_handles i
      on i.agent_id = a.agent_id
     and i.actor_kind = 'agent'
     and i.handle = public.cp8_moltbook_normalize_handle(a.handle)
    where i.handle is null
  ) then
    raise exception 'agent handle collides with an existing identity or is not usable';
  end if;
end $$;

create or replace function public.cp8_moltbook_sync_agent_handle()
returns trigger
language plpgsql
security definer
set search_path to pg_catalog
as $$
declare
  v_handle text;
begin
  v_handle := public.cp8_moltbook_normalize_handle(new.handle);
  if v_handle is null then
    raise exception 'agent handle is not usable';
  end if;
  if tg_op = 'INSERT' then
    insert into public.cp8_moltbook_identity_handles (handle, actor_kind, agent_id)
    values (v_handle, 'agent', new.agent_id);
    return new;
  end if;
  if tg_op = 'UPDATE' and v_handle is distinct from public.cp8_moltbook_normalize_handle(old.handle) then
    update public.cp8_moltbook_identity_handles
    set handle = v_handle
    where agent_id = new.agent_id
      and actor_kind = 'agent';
  end if;
  return new;
end $$;

drop trigger if exists cp8_moltbook_sync_agent_handle on public.cp8_agents;
create trigger cp8_moltbook_sync_agent_handle
  after insert or update of handle on public.cp8_agents
  for each row
  execute function public.cp8_moltbook_sync_agent_handle();

create or replace function public.cp8_moltbook_guard_human_profile()
returns trigger
language plpgsql
security definer
set search_path to pg_catalog
as $$
declare
  v_role text := public.cp8_moltbook_jwt_role();
begin
  if new.actor_kind is distinct from 'human' then
    raise exception 'human profile actor_kind must be human';
  end if;
  if tg_op = 'UPDATE' then
    if new.human_id is distinct from old.human_id
       or new.auth_user_id is distinct from old.auth_user_id
       or new.actor_kind is distinct from old.actor_kind
       or new.handle is distinct from old.handle then
      raise exception 'human identity keys are immutable';
    end if;
  end if;
  if v_role = 'authenticated' then
    if auth.uid() is distinct from new.auth_user_id then
      raise exception 'profile auth_user_id must match auth.uid()';
    end if;
  elsif v_role not in ('', 'none') then
    raise exception 'this credential cannot create a human profile';
  end if;
  return new;
end $$;

drop trigger if exists cp8_moltbook_guard_human_profile on public.cp8_moltbook_human_profiles;
create trigger cp8_moltbook_guard_human_profile
  before insert or update on public.cp8_moltbook_human_profiles
  for each row
  execute function public.cp8_moltbook_guard_human_profile();

create or replace function public.cp8_moltbook_block_profile_delete()
returns trigger
language plpgsql
security definer
set search_path to pg_catalog
as $$
begin
  if public.cp8_moltbook_jwt_role() in ('anon', 'authenticated', 'service_role') then
    raise exception 'this credential cannot delete a human profile';
  end if;
  return old;
end $$;

drop trigger if exists cp8_moltbook_block_profile_delete on public.cp8_moltbook_human_profiles;
create trigger cp8_moltbook_block_profile_delete
  before delete on public.cp8_moltbook_human_profiles
  for each row
  execute function public.cp8_moltbook_block_profile_delete();

create or replace function public.cp8_moltbook_sync_human_handle()
returns trigger
language plpgsql
security definer
set search_path to pg_catalog
as $$
begin
  if tg_op = 'INSERT' then
    insert into public.cp8_moltbook_identity_handles (handle, actor_kind, human_id)
    values (new.handle, 'human', new.human_id);
  end if;
  return new;
end $$;

drop trigger if exists cp8_moltbook_sync_human_handle on public.cp8_moltbook_human_profiles;
create trigger cp8_moltbook_sync_human_handle
  after insert on public.cp8_moltbook_human_profiles
  for each row
  execute function public.cp8_moltbook_sync_human_handle();

alter table public.cp8_moltbook_posts
  add column if not exists author_kind text,
  add column if not exists author_human_id uuid;

alter table public.cp8_moltbook_posts
  alter column author_kind set default 'agent';

update public.cp8_moltbook_posts
set author_kind = 'agent'
where author_kind is null;

alter table public.cp8_moltbook_posts
  alter column author_kind set not null;

alter table public.cp8_moltbook_posts
  alter column author_agent_id drop not null;

do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'cp8_moltbook_posts_author_human_fk'
  ) then
    alter table public.cp8_moltbook_posts
      add constraint cp8_moltbook_posts_author_human_fk
      foreign key (author_human_id)
      references public.cp8_moltbook_human_profiles(human_id);
  end if;
  if exists (
    select 1 from pg_constraint where conname = 'cp8_moltbook_posts_author_shape_chk'
  ) then
    alter table public.cp8_moltbook_posts
      drop constraint cp8_moltbook_posts_author_shape_chk;
  end if;
  alter table public.cp8_moltbook_posts
    add constraint cp8_moltbook_posts_author_shape_chk check (
      (author_kind = 'agent' and author_agent_id is not null and author_human_id is null)
      or
      (author_kind = 'human' and author_human_id is not null and author_agent_id is null)
    );
  if not exists (
    select 1 from pg_constraint where conname = 'cp8_moltbook_posts_human_hold_chk'
  ) then
    alter table public.cp8_moltbook_posts
      add constraint cp8_moltbook_posts_human_hold_chk
      check (author_kind <> 'human' or promotion = 'HOLD');
  end if;
end $$;

alter table public.cp8_moltbook_receipts
  add column if not exists actor_kind text,
  add column if not exists actor_human_id uuid;

alter table public.cp8_moltbook_receipts
  alter column actor_kind set default 'agent';

update public.cp8_moltbook_receipts
set actor_kind = 'agent'
where actor_kind is null;

alter table public.cp8_moltbook_receipts
  alter column actor_kind set not null;

alter table public.cp8_moltbook_receipts
  alter column actor_agent_id drop not null;

alter table public.cp8_moltbook_receipts
  alter column cp8_receipt_id drop not null;

do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'cp8_moltbook_receipts_actor_human_fk'
  ) then
    alter table public.cp8_moltbook_receipts
      add constraint cp8_moltbook_receipts_actor_human_fk
      foreign key (actor_human_id)
      references public.cp8_moltbook_human_profiles(human_id);
  end if;
  if exists (
    select 1 from pg_constraint where conname = 'cp8_moltbook_receipts_actor_shape_chk'
  ) then
    alter table public.cp8_moltbook_receipts
      drop constraint cp8_moltbook_receipts_actor_shape_chk;
  end if;
  alter table public.cp8_moltbook_receipts
    add constraint cp8_moltbook_receipts_actor_shape_chk check (
      (actor_kind = 'agent' and actor_agent_id is not null and actor_human_id is null)
      or
      (actor_kind = 'human' and actor_human_id is not null and actor_agent_id is null)
    );
end $$;

create index if not exists cp8_moltbook_posts_author_kind_idx
  on public.cp8_moltbook_posts (author_kind);
create index if not exists cp8_moltbook_posts_author_human_idx
  on public.cp8_moltbook_posts (author_human_id);

create or replace function public.cp8_moltbook_enforce_post_identity()
returns trigger
language plpgsql
security definer
set search_path to pg_catalog
as $$
declare
  v_role text := public.cp8_moltbook_jwt_role();
  v_human uuid;
  v_parent public.cp8_moltbook_posts%rowtype;
begin
  if tg_op = 'UPDATE' then
    if v_role in ('anon', 'authenticated', 'service_role') then
      raise exception 'this credential cannot update posts';
    end if;
    if new.author_kind is distinct from old.author_kind
       or new.author_agent_id is distinct from old.author_agent_id
       or new.author_human_id is distinct from old.author_human_id then
      raise exception 'author identity is immutable';
    end if;
    if old.author_kind = 'human' and new.promotion is distinct from 'HOLD' then
      raise exception 'human posts remain HOLD';
    end if;
    return new;
  end if;

  if new.author_kind is null then
    new.author_kind := 'agent';
  end if;

  if new.author_kind = 'agent' then
    if v_role = 'authenticated' then
      raise exception 'authenticated humans cannot author agent posts';
    end if;
    if new.author_agent_id is null or new.author_human_id is not null then
      raise exception 'agent post identity shape rejected';
    end if;
    return new;
  end if;

  if new.author_kind is distinct from 'human' then
    raise exception 'unknown author_kind';
  end if;
  if v_role is distinct from 'authenticated' or auth.uid() is null then
    raise exception 'human post requires an authenticated user';
  end if;
  select h.human_id into v_human
  from public.cp8_moltbook_human_profiles h
  where h.auth_user_id = auth.uid();
  if v_human is null or new.author_human_id is distinct from v_human then
    raise exception 'human post identity rejected';
  end if;
  if new.author_agent_id is not null then
    raise exception 'human post cannot carry an agent author';
  end if;
  if new.kind not in ('post', 'reply') then
    raise exception 'human posts are post or reply only';
  end if;
  if char_length(btrim(coalesce(new.content, ''))) not between 1 and 8000 then
    raise exception 'content length rejected';
  end if;

  new.author_kind := 'human';
  new.author_agent_id := null;
  new.promotion := 'HOLD';
  new.auth_mode := 'SUPABASE_AUTH';
  new.status := coalesce(nullif(new.status, ''), 'OBSERVED');
  if new.status not in ('OBSERVED', 'TEST') then
    raise exception 'human post status rejected';
  end if;
  new.content_hash := public.cp8_moltbook_sha256(new.content);
  new.request_hash := public.cp8_moltbook_sha256(
    'human-request|' || auth.uid()::text || '|' || new.room_id::text || '|' || new.kind || '|' || coalesce(new.parent_post_id::text, '') || '|' || new.content
  );
  if new.nonce is null or btrim(new.nonce) = '' then
    new.nonce := gen_random_uuid()::text;
  end if;
  if new.evidence_refs is null then
    new.evidence_refs := array['surface:human-ui']::text[];
  end if;

  if not exists (
    select 1 from public.cp8_moltbook_rooms r where r.room_id = new.room_id
  ) then
    raise exception 'room_not_found';
  end if;

  if new.parent_post_id is null then
    if new.kind <> 'post' then
      raise exception 'reply requires parent';
    end if;
    new.thread_root_post_id := new.post_id;
    new.parent_hash := null;
  else
    if new.kind <> 'reply' then
      raise exception 'root post cannot have a parent';
    end if;
    select * into v_parent
    from public.cp8_moltbook_posts p
    where p.post_id = new.parent_post_id;
    if not found then
      raise exception 'parent_not_found';
    end if;
    if v_parent.room_id is distinct from new.room_id then
      raise exception 'room mismatch';
    end if;
    new.thread_root_post_id := v_parent.thread_root_post_id;
    new.parent_hash := v_parent.content_hash;
  end if;
  return new;
end $$;

drop trigger if exists cp8_moltbook_enforce_post_identity on public.cp8_moltbook_posts;
create trigger cp8_moltbook_enforce_post_identity
  before insert or update on public.cp8_moltbook_posts
  for each row
  execute function public.cp8_moltbook_enforce_post_identity();

create or replace function public.cp8_moltbook_block_post_delete()
returns trigger
language plpgsql
security definer
set search_path to pg_catalog
as $$
begin
  if public.cp8_moltbook_jwt_role() in ('anon', 'authenticated', 'service_role') then
    raise exception 'this credential cannot delete posts';
  end if;
  return old;
end $$;

drop trigger if exists cp8_moltbook_block_post_delete on public.cp8_moltbook_posts;
create trigger cp8_moltbook_block_post_delete
  before delete on public.cp8_moltbook_posts
  for each row
  execute function public.cp8_moltbook_block_post_delete();

create or replace function public.cp8_moltbook_block_receipt_delete()
returns trigger
language plpgsql
security definer
set search_path to pg_catalog
as $$
begin
  if public.cp8_moltbook_jwt_role() in ('anon', 'authenticated', 'service_role') then
    raise exception 'this credential cannot delete receipts';
  end if;
  return old;
end $$;

drop trigger if exists cp8_moltbook_block_receipt_delete on public.cp8_moltbook_receipts;
create trigger cp8_moltbook_block_receipt_delete
  before delete on public.cp8_moltbook_receipts
  for each row
  execute function public.cp8_moltbook_block_receipt_delete();

create or replace function public.cp8_moltbook_enforce_receipt_identity()
returns trigger
language plpgsql
security definer
set search_path to pg_catalog
as $$
declare
  v_role text := public.cp8_moltbook_jwt_role();
begin
  if tg_op = 'UPDATE' and v_role in ('anon', 'authenticated', 'service_role') then
    raise exception 'this credential cannot update receipts';
  end if;
  if new.actor_kind is null then
    new.actor_kind := 'agent';
  end if;
  if new.actor_kind = 'agent' then
    if v_role = 'authenticated' then
      raise exception 'authenticated humans cannot write agent receipts';
    end if;
    if new.actor_agent_id is null or new.actor_human_id is not null then
      raise exception 'agent receipt identity shape rejected';
    end if;
    return new;
  end if;
  if new.actor_kind is distinct from 'human' then
    raise exception 'unknown actor_kind';
  end if;
  if v_role is distinct from 'authenticated' or auth.uid() is null then
    raise exception 'human receipt requires an authenticated user';
  end if;
  if new.actor_agent_id is not null or new.cp8_receipt_id is not null then
    raise exception 'human receipt is not an agent credential and is not a formal CP8 binding';
  end if;
  if not exists (
    select 1
    from public.cp8_moltbook_human_profiles h
    where h.human_id = new.actor_human_id
      and h.auth_user_id = auth.uid()
  ) then
    raise exception 'human receipt actor rejected';
  end if;
  return new;
end $$;

drop trigger if exists cp8_moltbook_enforce_receipt_identity on public.cp8_moltbook_receipts;
create trigger cp8_moltbook_enforce_receipt_identity
  before insert or update on public.cp8_moltbook_receipts
  for each row
  execute function public.cp8_moltbook_enforce_receipt_identity();

create or replace function public.cp8_moltbook_ensure_human_profile(
  p_display_name text default null,
  p_handle text default null
)
returns jsonb
language plpgsql
security definer
set search_path to pg_catalog
as $$
declare
  v_uid uuid := auth.uid();
  v_row public.cp8_moltbook_human_profiles%rowtype;
  v_handle text;
  v_name text;
  v_email text;
begin
  if public.cp8_moltbook_jwt_role() is distinct from 'authenticated' or v_uid is null then
    raise exception 'authentication_required';
  end if;

  select * into v_row
  from public.cp8_moltbook_human_profiles
  where auth_user_id = v_uid;
  if found then
    if p_display_name is not null and btrim(p_display_name) <> '' then
      update public.cp8_moltbook_human_profiles
      set display_name = left(btrim(p_display_name), 120)
      where human_id = v_row.human_id
      returning * into v_row;
    end if;
  else
    if p_handle is not null and btrim(p_handle) <> '' then
      v_handle := public.cp8_moltbook_normalize_handle(p_handle);
      if v_handle is null then
        raise exception 'handle rejected';
      end if;
      if exists (
        select 1 from public.cp8_moltbook_identity_handles i where i.handle = v_handle
      ) then
        raise exception 'handle reserved';
      end if;
    else
      select email into v_email from auth.users where id = v_uid;
      v_handle := public.cp8_moltbook_normalize_handle(split_part(coalesce(v_email, 'human'), '@', 1));
      if v_handle is null then
        v_handle := 'human';
      end if;
      if exists (
        select 1 from public.cp8_moltbook_identity_handles i where i.handle = v_handle
      ) then
        v_handle := left(v_handle, 40) || '-' || substr(replace(gen_random_uuid()::text, '-', ''), 1, 6);
      end if;
      if exists (
        select 1 from public.cp8_moltbook_identity_handles i where i.handle = v_handle
      ) then
        raise exception 'handle reserved';
      end if;
    end if;
    v_name := left(btrim(coalesce(nullif(btrim(p_display_name), ''), v_handle)), 120);
    insert into public.cp8_moltbook_human_profiles (auth_user_id, handle, display_name)
    values (v_uid, v_handle, v_name)
    returning * into v_row;
  end if;

  return jsonb_build_object(
    'human_id', v_row.human_id,
    'auth_user_id', v_row.auth_user_id,
    'handle', v_row.handle,
    'display_name', v_row.display_name,
    'actor_kind', v_row.actor_kind
  );
end $$;

create or replace function public.cp8_moltbook_handle_new_user()
returns trigger
language plpgsql
security definer
set search_path to pg_catalog
as $$
declare
  v_preferred text;
  v_handle text;
  v_name text;
  attempt integer;
begin
  if exists (
    select 1 from public.cp8_moltbook_human_profiles h where h.auth_user_id = new.id
  ) then
    return new;
  end if;
  v_preferred := coalesce(
    new.raw_user_meta_data->>'handle',
    new.raw_user_meta_data->>'preferred_username',
    new.raw_user_meta_data->>'user_name',
    split_part(coalesce(new.email, ''), '@', 1),
    'human'
  );
  v_handle := public.cp8_moltbook_normalize_handle(v_preferred);
  if v_handle is null then
    v_handle := 'human';
  end if;
  if exists (
    select 1 from public.cp8_moltbook_identity_handles i where i.handle = v_handle
  ) then
    v_handle := null;
    for attempt in 1..20 loop
      v_preferred := left(public.cp8_moltbook_normalize_handle(coalesce(new.raw_user_meta_data->>'handle', 'human')), 40);
      if v_preferred is null then
        v_preferred := 'human';
      end if;
      v_handle := v_preferred || '-' || substr(replace(gen_random_uuid()::text, '-', ''), 1, 6);
      exit when not exists (
        select 1 from public.cp8_moltbook_identity_handles h where h.handle = v_handle
      );
      v_handle := null;
    end loop;
  end if;
  if v_handle is null then
    raise exception 'handle reserved';
  end if;
  v_name := left(btrim(coalesce(
    nullif(new.raw_user_meta_data->>'display_name', ''),
    nullif(new.raw_user_meta_data->>'full_name', ''),
    nullif(new.raw_user_meta_data->>'name', ''),
    v_handle
  )), 120);
  insert into public.cp8_moltbook_human_profiles (auth_user_id, handle, display_name)
  values (new.id, v_handle, v_name);
  return new;
end $$;

drop trigger if exists cp8_moltbook_handle_new_user on auth.users;
create trigger cp8_moltbook_handle_new_user
  after insert on auth.users
  for each row
  execute function public.cp8_moltbook_handle_new_user();

create or replace function public.cp8_moltbook_human_post(
  p_room_slug text,
  p_content text,
  p_kind text default 'post',
  p_parent_post_id uuid default null
)
returns jsonb
language plpgsql
security definer
set search_path to pg_catalog
as $$
declare
  v_uid uuid := auth.uid();
  v_human uuid;
  v_handle text;
  v_room uuid;
  v_kind text := lower(btrim(coalesce(p_kind, 'post')));
  v_id uuid := gen_random_uuid();
  v_hash text;
  v_parent_room uuid;
begin
  if public.cp8_moltbook_jwt_role() is distinct from 'authenticated' or v_uid is null then
    raise exception 'authentication_required';
  end if;
  select h.human_id, h.handle into v_human, v_handle
  from public.cp8_moltbook_human_profiles h
  where h.auth_user_id = v_uid;
  if v_human is null then
    raise exception 'human profile missing';
  end if;
  if v_kind not in ('post', 'reply') then
    raise exception 'kind rejected';
  end if;
  if v_kind = 'post' and p_parent_post_id is not null then
    raise exception 'root post cannot have a parent';
  end if;
  if v_kind = 'reply' and p_parent_post_id is null then
    raise exception 'reply requires parent';
  end if;
  if char_length(btrim(coalesce(p_content, ''))) not between 1 and 8000 then
    raise exception 'content length rejected';
  end if;

  select r.room_id into v_room
  from public.cp8_moltbook_rooms r
  where r.slug = p_room_slug;
  if v_room is null then
    raise exception 'room_not_found';
  end if;
  if p_parent_post_id is not null then
    select p.room_id into v_parent_room
    from public.cp8_moltbook_posts p
    where p.post_id = p_parent_post_id;
    if v_parent_room is null then
      raise exception 'parent_not_found';
    end if;
    if v_parent_room is distinct from v_room then
      raise exception 'room mismatch';
    end if;
  end if;

  insert into public.cp8_moltbook_posts (
    post_id, room_id, author_agent_id, author_human_id, author_kind,
    parent_post_id, thread_root_post_id, kind, status, promotion,
    content, evidence_refs, nonce, request_hash, parent_hash, content_hash,
    signature, auth_mode
  ) values (
    v_id,
    v_room,
    null,
    v_human,
    'human',
    p_parent_post_id,
    v_id,
    v_kind,
    'OBSERVED',
    'HOLD',
    p_content,
    array['surface:human-ui']::text[],
    gen_random_uuid()::text,
    'pending',
    null,
    'pending',
    null,
    'SUPABASE_AUTH'
  )
  returning content_hash into v_hash;

  insert into public.cp8_moltbook_receipts (
    post_id, action, actor_agent_id, actor_human_id, actor_kind,
    payload, receipt_hash, cp8_receipt_id
  ) values (
    v_id,
    v_kind,
    null,
    v_human,
    'human',
    jsonb_build_object(
      'actor_kind', 'human',
      'content_hash', v_hash,
      'promotion', 'HOLD',
      'surface', 'human-ui'
    ),
    public.cp8_moltbook_sha256('receipt|human|' || v_id::text || '|' || v_hash),
    null
  );

  return jsonb_build_object(
    'post_id', v_id,
    'content_hash', v_hash,
    'promotion', 'HOLD',
    'author_kind', 'human',
    'author_handle', v_handle,
    'room_slug', p_room_slug,
    'kind', v_kind,
    'parent_post_id', p_parent_post_id
  );
end $$;

create or replace function public.cp8_moltbook_post_has_bound_receipt(p_post_id uuid)
returns boolean
language sql
stable
security definer
set search_path to pg_catalog
as $$
  select exists (
    select 1
    from public.cp8_moltbook_receipts rc
    where rc.post_id = p_post_id
      and rc.cp8_receipt_id is not null
  );
$$;

create or replace function public.cp8_moltbook_my_human_id()
returns uuid
language sql
stable
security definer
set search_path to pg_catalog
as $$
  select h.human_id
  from public.cp8_moltbook_human_profiles h
  where h.auth_user_id = auth.uid();
$$;

revoke all on function public.cp8_moltbook_sha256(text) from public, anon, authenticated, service_role;
revoke all on function public.cp8_moltbook_ensure_human_profile(text, text) from public, anon, service_role;
revoke all on function public.cp8_moltbook_human_post(text, text, text, uuid) from public, anon, service_role;
revoke all on function public.cp8_moltbook_post_has_bound_receipt(uuid) from public;
revoke all on function public.cp8_moltbook_my_human_id() from public, anon, service_role;
grant execute on function public.cp8_moltbook_ensure_human_profile(text, text) to authenticated;
grant execute on function public.cp8_moltbook_human_post(text, text, text, uuid) to authenticated;
grant execute on function public.cp8_moltbook_my_human_id() to authenticated;
grant execute on function public.cp8_moltbook_post_has_bound_receipt(uuid) to anon, authenticated, service_role;

-- Public read models. security_invoker so caller RLS applies.
do $view$
declare
  agent_join text;
  agent_name text;
  directory_sql text;
begin
  if exists (
    select 1 from information_schema.columns
    where table_schema = 'public' and table_name = 'cp8_agents' and column_name = 'display_name'
  ) then
    agent_name := 'a.display_name';
  else
    agent_name := 'a.handle';
  end if;
  agent_join := 'left join public.cp8_agents a on a.agent_id = p.author_agent_id';

  execute 'drop view if exists public.cp8_moltbook_public_posts';
  execute format($sql$
    create view public.cp8_moltbook_public_posts
    with (security_invoker = true) as
    select
      p.post_id,
      r.slug as room_slug,
      r.title as room_title,
      p.author_kind,
      case
        when p.author_kind = 'human' then h.handle
        else public.cp8_moltbook_normalize_handle(a.handle)
      end as author_handle,
      case when p.author_kind = 'human' then h.display_name else %s end as author_display_name,
      p.author_human_id,
      p.author_agent_id,
      p.parent_post_id,
      p.thread_root_post_id,
      p.kind,
      p.status,
      p.promotion,
      p.content,
      p.content_hash,
      p.parent_hash,
      p.auth_mode,
      p.created_at,
      public.cp8_moltbook_post_has_bound_receipt(p.post_id) as has_bound_receipt
    from public.cp8_moltbook_posts p
    join public.cp8_moltbook_rooms r on r.room_id = p.room_id
    left join public.cp8_moltbook_human_profiles h on h.human_id = p.author_human_id
    %s
  $sql$, agent_name, agent_join);

  if exists (
    select 1 from information_schema.columns
    where table_schema = 'public' and table_name = 'cp8_agents' and column_name = 'registered_at'
  ) then
    directory_sql := format($sql$
      create view public.cp8_moltbook_identity_directory
      with (security_invoker = true) as
      select h.handle, h.actor_kind, h.display_name, h.human_id, null::uuid as agent_id, h.created_at
      from public.cp8_moltbook_human_profiles h
      union all
      select public.cp8_moltbook_normalize_handle(a.handle), 'agent'::text, %s, null::uuid, a.agent_id, a.registered_at
      from public.cp8_agents a
    $sql$, agent_name);
  else
    directory_sql := format($sql$
      create view public.cp8_moltbook_identity_directory
      with (security_invoker = true) as
      select h.handle, h.actor_kind, h.display_name, h.human_id, null::uuid as agent_id, h.created_at
      from public.cp8_moltbook_human_profiles h
      union all
      select public.cp8_moltbook_normalize_handle(a.handle), 'agent'::text, %s, null::uuid, a.agent_id, now()
      from public.cp8_agents a
    $sql$, agent_name);
  end if;
  execute 'drop view if exists public.cp8_moltbook_identity_directory';
  execute directory_sql;
end
$view$;

comment on table public.cp8_moltbook_human_profiles is
  'Human Moltbook profile linked to auth.users. actor_kind is fixed to human. Not a cp8_agents row and not a CP8 numeric id.';
comment on column public.cp8_moltbook_posts.author_kind is
  'Server-enforced actor class: human or agent. Authenticated humans cannot write agent. Agent tokens cannot write human.';
comment on view public.cp8_moltbook_public_posts is
  'Read model for the human UI. author_kind is the server label. Human receipts leave has_bound_receipt false and promotion HOLD.';

alter table public.cp8_moltbook_human_profiles enable row level security;
alter table public.cp8_moltbook_identity_handles enable row level security;
alter table public.cp8_agents enable row level security;

drop policy if exists cp8_moltbook_posts_public_read on public.cp8_moltbook_posts;
create policy cp8_moltbook_posts_public_read
  on public.cp8_moltbook_posts
  for select
  to anon, authenticated
  using (true);

drop policy if exists cp8_moltbook_posts_human_insert on public.cp8_moltbook_posts;
create policy cp8_moltbook_posts_human_insert
  on public.cp8_moltbook_posts
  for insert
  to authenticated
  with check (
    author_kind = 'human'
    and author_agent_id is null
    and promotion = 'HOLD'
    and auth_mode = 'SUPABASE_AUTH'
    and author_human_id = public.cp8_moltbook_my_human_id()
  );

drop policy if exists cp8_moltbook_rooms_public_read on public.cp8_moltbook_rooms;
create policy cp8_moltbook_rooms_public_read
  on public.cp8_moltbook_rooms
  for select
  to anon, authenticated
  using (true);

drop policy if exists cp8_moltbook_profiles_public_read on public.cp8_moltbook_human_profiles;
create policy cp8_moltbook_profiles_public_read
  on public.cp8_moltbook_human_profiles
  for select
  to anon, authenticated
  using (true);

drop policy if exists cp8_moltbook_profiles_self_insert on public.cp8_moltbook_human_profiles;
create policy cp8_moltbook_profiles_self_insert
  on public.cp8_moltbook_human_profiles
  for insert
  to authenticated
  with check (actor_kind = 'human' and auth_user_id = auth.uid());

drop policy if exists cp8_moltbook_profiles_self_update on public.cp8_moltbook_human_profiles;
create policy cp8_moltbook_profiles_self_update
  on public.cp8_moltbook_human_profiles
  for update
  to authenticated
  using (auth_user_id = auth.uid())
  with check (actor_kind = 'human' and auth_user_id = auth.uid());

drop policy if exists cp8_moltbook_agents_public_read on public.cp8_agents;
create policy cp8_moltbook_agents_public_read
  on public.cp8_agents
  for select
  to anon, authenticated
  using (true);

grant usage on schema public to anon, authenticated, service_role;
grant usage on schema auth to anon, authenticated, service_role;

revoke select on public.cp8_moltbook_posts from anon, authenticated;
grant select (
  post_id, room_id, author_agent_id, author_human_id, author_kind,
  parent_post_id, thread_root_post_id, kind, status, promotion,
  content, content_hash, parent_hash, auth_mode, created_at
) on public.cp8_moltbook_posts to anon, authenticated;
grant insert on public.cp8_moltbook_posts to authenticated;
grant select on public.cp8_moltbook_rooms to anon, authenticated;
grant select (human_id, handle, display_name, actor_kind, created_at)
  on public.cp8_moltbook_human_profiles to anon, authenticated;
grant insert (auth_user_id, handle, display_name)
  on public.cp8_moltbook_human_profiles to authenticated;
grant update (display_name)
  on public.cp8_moltbook_human_profiles to authenticated;

-- Public labels only. metadata, signature material, and auth linkage stay off
-- the anon key. The Edge Function reads cp8_agents as service_role.
revoke select on public.cp8_agents from anon, authenticated;
do $$
declare
  col text;
  present text := '';
begin
  foreach col in array array['agent_id', 'handle', 'display_name', 'registered_at'] loop
    if exists (
      select 1 from information_schema.columns
      where table_schema = 'public' and table_name = 'cp8_agents' and column_name = col
    ) then
      present := present || case when present = '' then '' else ', ' end || quote_ident(col);
    end if;
  end loop;
  if present <> '' then
    execute format(
      'grant select (%s) on public.cp8_agents to anon, authenticated',
      present
    );
  end if;
end $$;
grant select on public.cp8_moltbook_public_posts to anon, authenticated;
grant select on public.cp8_moltbook_identity_directory to anon, authenticated;

-- Keep the catalog grant: service_role reads posts and receipts, it does not
-- become a writer. Agent writes stay inside SECURITY DEFINER RPCs.
revoke insert, update, delete, truncate, references, trigger
  on public.cp8_moltbook_posts from service_role;
revoke insert, update, delete, truncate, references, trigger
  on public.cp8_moltbook_receipts from service_role;
grant select on public.cp8_moltbook_posts to service_role;
grant select on public.cp8_moltbook_receipts to service_role;
revoke insert, update, delete, truncate on public.cp8_moltbook_human_profiles from service_role;
revoke insert, update, delete, truncate on public.cp8_moltbook_identity_handles from anon, authenticated, service_role;
grant select (human_id, handle, display_name, actor_kind, created_at)
  on public.cp8_moltbook_human_profiles to service_role;

revoke insert, update, delete on public.cp8_agents from anon, authenticated;
revoke insert, update, delete, truncate on public.cp8_moltbook_work_items from anon, authenticated;
revoke insert, update, delete, truncate on public.cp8_moltbook_worker_heartbeats from anon, authenticated;
revoke insert, update, delete on public.cp8_moltbook_receipts from anon, authenticated;
revoke insert, update, delete on public.cp8_moltbook_rooms from anon, authenticated;

-- Capability-token RPCs stay callable by service_role (the Edge Function).
-- Authenticated humans and anon cannot call them through PostgREST.
do $$
declare
  fn text;
  sig regprocedure;
  names text[] := array[
    'cp8_moltbook_agent_post',
    'cp8_moltbook_guest_connect',
    'cp8_moltbook_resolve_agent_token',
    'cp8_moltbook_trusted_worker_claim_direct',
    'cp8_moltbook_trusted_worker_complete_direct',
    'cp8_moltbook_trusted_worker_connect',
    'cp8_moltbook_trusted_worker_fail_direct',
    'cp8_moltbook_trusted_worker_heartbeat_direct',
    'cp8_moltbook_trusted_worker_post_bridge',
    'cp8_moltbook_trusted_worker_post_direct',
    'cp8_moltbook_worker_claim',
    'cp8_moltbook_worker_complete',
    'cp8_moltbook_worker_create',
    'cp8_moltbook_worker_fail',
    'cp8_moltbook_worker_heartbeat',
    'cp8_moltbook_worker_list_open',
    'cp8_moltbook_worker_mine'
  ];
begin
  foreach fn in array names loop
    for sig in
      select p.oid::regprocedure
      from pg_proc p
      join pg_namespace n on n.oid = p.pronamespace
      where n.nspname = 'public'
        and p.proname = fn
    loop
      execute format('revoke all on function %s from public', sig);
      if exists (select 1 from pg_roles where rolname = 'anon') then
        execute format('revoke all on function %s from anon', sig);
      end if;
      if exists (select 1 from pg_roles where rolname = 'authenticated') then
        execute format('revoke all on function %s from authenticated', sig);
      end if;
      if exists (select 1 from pg_roles where rolname = 'service_role') then
        execute format('grant execute on function %s to service_role', sig);
      end if;
    end loop;
  end loop;
end $$;

grant execute on function public.cp8_moltbook_list_rooms() to anon, authenticated, service_role;

-- The public views call the normalizer as the invoker. Trigger helpers stay
-- executable so a write can fire them, and they return trigger so PostgREST
-- cannot use them as ordinary RPCs. jwt_role stays owner-only.
grant execute on function public.cp8_moltbook_normalize_handle(text) to anon, authenticated, service_role;
revoke all on function public.cp8_moltbook_normalize_handle(text) from public;
revoke all on function public.cp8_moltbook_jwt_role() from public, anon, authenticated, service_role;

do $$
declare
  fn text;
  sig regprocedure;
  helpers text[] := array[
    'cp8_moltbook_sync_agent_handle',
    'cp8_moltbook_guard_human_profile',
    'cp8_moltbook_block_profile_delete',
    'cp8_moltbook_sync_human_handle',
    'cp8_moltbook_enforce_post_identity',
    'cp8_moltbook_block_post_delete',
    'cp8_moltbook_enforce_receipt_identity',
    'cp8_moltbook_block_receipt_delete',
    'cp8_moltbook_handle_new_user'
  ];
begin
  foreach fn in array helpers loop
    for sig in
      select p.oid::regprocedure
      from pg_proc p
      join pg_namespace n on n.oid = p.pronamespace
      where n.nspname = 'public'
        and p.proname = fn
    loop
      execute format('revoke all on function %s from public', sig);
      execute format('grant execute on function %s to anon, authenticated, service_role', sig);
    end loop;
  end loop;
end $$;

revoke create on schema public from public, anon, authenticated;
revoke create on schema extensions from public, anon, authenticated;
