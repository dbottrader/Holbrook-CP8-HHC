-- Explicit deny for browser roles. The edge function uses the service role,
-- which bypasses RLS. No client policy is granted.

do $$
declare
  t text;
begin
  foreach t in array array[
    'gpumesh_nodes',
    'gpumesh_jobs',
    'gpumesh_chunks',
    'gpumesh_ledger',
    'gpumesh_settlements',
    'gpumesh_rate',
    'gpumesh_signer'
  ]
  loop
    if not exists (
      select 1 from pg_policies
      where schemaname = 'public' and tablename = t and policyname = t || '_no_client'
    ) then
      execute format(
        'create policy %I on public.%I as restrictive for all to anon, authenticated using (false) with check (false)',
        t || '_no_client',
        t
      );
    end if;
  end loop;
end $$;
