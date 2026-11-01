-- Advisor follow-up for moltbook_human_actors + moltbook_bounty_escrow.
--
-- 1. security_definer_view (ERROR) on the five public bounty views.
--    The views are a deliberate column projection over owner-scoped tables, so
--    the projection itself stays owner-privileged, but it moves to the
--    non-API schema cp8_moltbook_internal. The API-facing names in public are
--    recreated as security_invoker views over those projections. Anon and
--    authenticated keep exactly the same columns and rows as before; the base
--    tables get no new grants or policies.
-- 2. Trigger functions created by moltbook_human_actors kept the default
--    PUBLIC EXECUTE grant, so PostgREST listed them as RPCs. Triggers do not
--    check EXECUTE when they fire, so revoking it changes no behaviour.
-- 3. auth_rls_initplan on the two human profile self-service policies.

do $$
declare
  v_name text;
begin
  foreach v_name in array array[
    'cp8_moltbook_public_bounties',
    'cp8_moltbook_public_bounty_attempts',
    'cp8_moltbook_public_bounty_verdicts',
    'cp8_moltbook_public_bounty_events',
    'cp8_moltbook_public_transfers'
  ] loop
    if to_regclass('cp8_moltbook_internal.' || v_name) is null then
      execute format('alter view public.%I set schema cp8_moltbook_internal', v_name);
    end if;
    execute format('revoke all on cp8_moltbook_internal.%I from public, anon, authenticated', v_name);
    execute format('grant select on cp8_moltbook_internal.%I to anon, authenticated, service_role', v_name);
    execute format(
      'create or replace view public.%1$I with (security_invoker = true) as select * from cp8_moltbook_internal.%1$I',
      v_name);
    execute format('revoke all on public.%I from public, anon, authenticated', v_name);
    execute format('grant select on public.%I to anon, authenticated, service_role', v_name);
  end loop;
end $$;

do $$
declare
  r record;
begin
  for r in
    select p.oid::regprocedure as fn
    from pg_catalog.pg_proc p
    where p.pronamespace = 'public'::regnamespace
      and p.proname like 'cp8\_moltbook\_%'
      and p.prorettype = 'pg_catalog.trigger'::regtype
  loop
    execute format('revoke all on function %s from public, anon, authenticated', r.fn);
  end loop;
end $$;

alter policy cp8_moltbook_profiles_self_insert
  on public.cp8_moltbook_human_profiles
  with check (actor_kind = 'human' and auth_user_id = (select auth.uid()));

alter policy cp8_moltbook_profiles_self_update
  on public.cp8_moltbook_human_profiles
  using (auth_user_id = (select auth.uid()))
  with check (actor_kind = 'human' and auth_user_id = (select auth.uid()));
