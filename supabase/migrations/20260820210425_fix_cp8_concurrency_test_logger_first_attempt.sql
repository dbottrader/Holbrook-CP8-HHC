-- Production mirror of Supabase migration 20260820210425.
-- Preserve the first result for each race participant so repeating pg_cron
-- intervals cannot overwrite the evidentiary outcome of the initial race.

create or replace function private.cp8_record_trusted_claim_attempt(
  p_race_id uuid,
  p_handle text,
  p_work_id uuid,
  p_lease_minutes integer default 15
)
returns void
language plpgsql
security definer
set search_path to 'pg_catalog', 'public', 'private', 'extensions'
as $function$
declare
  v_started timestamptz := clock_timestamp();
begin
  if exists (
    select 1 from private.cp8_claim_race_results
    where race_id = p_race_id and handle = p_handle
  ) then
    return;
  end if;

  begin
    perform * from public.cp8_moltbook_trusted_worker_claim_direct(p_handle, p_work_id, p_lease_minutes);
    insert into private.cp8_claim_race_results(race_id, work_id, handle, ok, detail, started_at, finished_at)
    values(p_race_id, p_work_id, p_handle, true, 'CLAIMED', v_started, clock_timestamp());
  exception when others then
    insert into private.cp8_claim_race_results(race_id, work_id, handle, ok, detail, started_at, finished_at)
    values(p_race_id, p_work_id, p_handle, false, sqlerrm, v_started, clock_timestamp());
  end;
end
$function$;
revoke all on function private.cp8_record_trusted_claim_attempt(uuid,text,uuid,integer) from public, anon, authenticated;
grant execute on function private.cp8_record_trusted_claim_attempt(uuid,text,uuid,integer) to postgres;
