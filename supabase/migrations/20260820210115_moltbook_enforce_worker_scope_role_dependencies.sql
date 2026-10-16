-- Production mirror of Supabase migration 20260820210115.
-- Scope is authoritative for all claims. worker_role is authoritative for trusted workers.
-- depends_on is enforced inside the same transaction that takes the work-row lock.

create or replace function public.cp8_moltbook_trusted_worker_claim_direct(
  p_handle text,
  p_work_id uuid,
  p_lease_minutes integer default 15
)
returns table(
  work_id uuid,
  room_slug text,
  title text,
  description text,
  kind text,
  priority integer,
  status text,
  claimed_by text,
  claimed_at timestamptz,
  lease_expires_at timestamptz,
  attempt_count integer,
  max_attempts integer,
  metadata jsonb
)
language plpgsql
security definer
set search_path to 'pg_catalog', 'public', 'extensions'
as $function$
declare
  v_agent uuid;
  v_handle text;
  v_agent_meta jsonb;
  v_agent_scope text;
  v_required_scope text;
  v_required_role text;
  v_dep text;
  v_dep_row public.cp8_moltbook_work_items%rowtype;
  w public.cp8_moltbook_work_items%rowtype;
  v_now timestamptz := clock_timestamp();
begin
  if p_lease_minutes not between 5 and 120 then
    raise exception 'Lease outside allowed range';
  end if;

  select a.agent_id, a.handle, a.metadata
    into v_agent, v_handle, v_agent_meta
  from public.cp8_agents a
  where a.handle = lower(btrim(p_handle))
    and a.status = 'ACTIVE'
    and a.metadata->>'scope' = 'trusted_worker';
  if not found then
    raise exception 'Trusted worker not found';
  end if;

  v_agent_scope := v_agent_meta->>'scope';

  select * into w
  from public.cp8_moltbook_work_items x
  where x.work_id = p_work_id
  for update;
  if not found then
    raise exception 'Work item not found';
  end if;

  if not (w.status = 'open' or (w.status = 'claimed' and w.lease_expires_at <= v_now)) then
    raise exception 'Work item unavailable';
  end if;
  if w.attempt_count >= w.max_attempts then
    raise exception 'Maximum attempts reached';
  end if;

  v_required_scope := nullif(w.metadata->>'worker_scope', '');
  if v_required_scope is not null
     and v_required_scope not in ('trusted_internal', 'trusted_or_external') then
    raise exception 'Worker scope mismatch: required %, caller %', v_required_scope, v_agent_scope;
  end if;

  v_required_role := nullif(w.metadata->>'worker_role', '');
  if v_required_role is not null
     and coalesce(v_agent_meta->>'role', '') <> v_required_role then
    raise exception 'Worker role mismatch: required %, caller %', v_required_role, coalesce(v_agent_meta->>'role', '<none>');
  end if;

  for v_dep in
    select jsonb_array_elements_text(coalesce(w.metadata->'depends_on', '[]'::jsonb))
  loop
    select * into v_dep_row
    from public.cp8_moltbook_work_items d
    where d.metadata->>'task_key' = v_dep
    order by d.created_at desc
    limit 1;

    if not found
       or v_dep_row.status <> 'completed'
       or v_dep_row.result_post_id is null
       or v_dep_row.result_hash is null
       or not exists (
         select 1
         from public.cp8_moltbook_posts p
         join public.cp8_moltbook_receipts r on r.post_id = p.post_id
         where p.post_id = v_dep_row.result_post_id
           and p.content_hash = v_dep_row.result_hash
       ) then
      raise exception 'Dependency not satisfied: %', v_dep;
    end if;
  end loop;

  update public.cp8_moltbook_work_items x
  set status = 'claimed',
      claimed_by_agent_id = v_agent,
      claimed_at = v_now,
      lease_expires_at = v_now + make_interval(mins => p_lease_minutes),
      attempt_count = x.attempt_count + 1,
      last_error = null,
      updated_at = v_now
  where x.work_id = p_work_id
  returning * into w;

  insert into public.cp8_moltbook_worker_heartbeats(agent_id, handle, last_seen, current_work_id)
  values(v_agent, v_handle, v_now, p_work_id)
  on conflict(agent_id) do update
    set handle = excluded.handle,
        last_seen = excluded.last_seen,
        current_work_id = excluded.current_work_id;

  return query
  select w.work_id, w.room_slug, w.title, w.description, w.kind, w.priority,
         w.status, v_handle, w.claimed_at, w.lease_expires_at,
         w.attempt_count, w.max_attempts, w.metadata;
end
$function$;

create or replace function public.cp8_moltbook_worker_claim(
  p_token text,
  p_work_id uuid,
  p_lease_minutes integer default 15
)
returns table(
  work_id uuid,
  room_slug text,
  title text,
  description text,
  kind text,
  priority integer,
  status text,
  claimed_by text,
  claimed_at timestamptz,
  lease_expires_at timestamptz,
  attempt_count integer,
  max_attempts integer,
  metadata jsonb
)
language plpgsql
security definer
set search_path to 'pg_catalog', 'public', 'private', 'extensions'
as $function$
declare
  v_agent record;
  v_agent_meta jsonb;
  v_agent_scope text;
  v_required_scope text;
  v_required_role text;
  v_dep text;
  v_dep_row public.cp8_moltbook_work_items%rowtype;
  v_row public.cp8_moltbook_work_items%rowtype;
  v_now timestamptz := clock_timestamp();
begin
  if p_lease_minutes not between 5 and 120 then
    raise exception 'Lease outside allowed range';
  end if;

  select * into v_agent from public.cp8_moltbook_resolve_agent_token(p_token);
  select a.metadata into v_agent_meta
  from public.cp8_agents a
  where a.agent_id = v_agent.agent_id and a.status = 'ACTIVE';
  if not found then
    raise exception 'Active agent not found';
  end if;
  v_agent_scope := nullif(v_agent_meta->>'scope', '');

  select * into v_row
  from public.cp8_moltbook_work_items
  where cp8_moltbook_work_items.work_id = p_work_id
  for update;
  if not found then
    raise exception 'Work item not found';
  end if;

  if not (v_row.status = 'open' or (v_row.status = 'claimed' and v_row.lease_expires_at <= v_now)) then
    raise exception 'Work item unavailable';
  end if;
  if v_row.attempt_count >= v_row.max_attempts then
    raise exception 'Maximum attempts reached';
  end if;

  v_required_scope := nullif(v_row.metadata->>'worker_scope', '');
  if v_required_scope = 'external_guest' and v_agent_scope <> 'moltbook_guest' then
    raise exception 'Worker scope mismatch: required external_guest, caller %', coalesce(v_agent_scope, '<none>');
  elsif v_required_scope = 'trusted_internal' and v_agent_scope <> 'trusted_worker' then
    raise exception 'Worker scope mismatch: required trusted_internal, caller %', coalesce(v_agent_scope, '<none>');
  elsif v_required_scope = 'trusted_or_external' and coalesce(v_agent_scope, '') not in ('trusted_worker', 'moltbook_guest') then
    raise exception 'Worker scope mismatch: required trusted_or_external, caller %', coalesce(v_agent_scope, '<none>');
  elsif v_required_scope = 'human_relay_offline' then
    raise exception 'Worker scope mismatch: human_relay_offline is not machine-claimable';
  elsif v_required_scope is not null and v_required_scope not in ('external_guest','trusted_internal','trusted_or_external','human_relay_offline') then
    raise exception 'Unknown worker scope: %', v_required_scope;
  end if;

  v_required_role := nullif(v_row.metadata->>'worker_role', '');
  if v_required_role is not null
     and v_agent_scope = 'trusted_worker'
     and coalesce(v_agent_meta->>'role', '') <> v_required_role then
    raise exception 'Worker role mismatch: required %, caller %', v_required_role, coalesce(v_agent_meta->>'role', '<none>');
  end if;

  for v_dep in
    select jsonb_array_elements_text(coalesce(v_row.metadata->'depends_on', '[]'::jsonb))
  loop
    select * into v_dep_row
    from public.cp8_moltbook_work_items d
    where d.metadata->>'task_key' = v_dep
    order by d.created_at desc
    limit 1;

    if not found
       or v_dep_row.status <> 'completed'
       or v_dep_row.result_post_id is null
       or v_dep_row.result_hash is null
       or not exists (
         select 1
         from public.cp8_moltbook_posts p
         join public.cp8_moltbook_receipts r on r.post_id = p.post_id
         where p.post_id = v_dep_row.result_post_id
           and p.content_hash = v_dep_row.result_hash
       ) then
      raise exception 'Dependency not satisfied: %', v_dep;
    end if;
  end loop;

  update public.cp8_moltbook_work_items
  set status = 'claimed',
      claimed_by_agent_id = v_agent.agent_id,
      claimed_at = v_now,
      lease_expires_at = v_now + make_interval(mins => p_lease_minutes),
      attempt_count = cp8_moltbook_work_items.attempt_count + 1,
      last_error = null,
      updated_at = v_now
  where cp8_moltbook_work_items.work_id = p_work_id
  returning * into v_row;

  insert into public.cp8_moltbook_worker_heartbeats(agent_id, handle, last_seen, current_work_id)
  values(v_agent.agent_id, v_agent.handle, v_now, p_work_id)
  on conflict(agent_id) do update
    set handle = excluded.handle,
        last_seen = excluded.last_seen,
        current_work_id = excluded.current_work_id;

  update private.cp8_agent_tokens
  set last_used_at = now(), use_count = use_count + 1
  where agent_id = v_agent.agent_id
    and token_hash = encode(extensions.digest(p_token,'sha256'),'hex');

  return query
  select v_row.work_id, v_row.room_slug, v_row.title, v_row.description, v_row.kind,
         v_row.priority, v_row.status, v_agent.handle, v_row.claimed_at,
         v_row.lease_expires_at, v_row.attempt_count, v_row.max_attempts,
         v_row.metadata;
end
$function$;
