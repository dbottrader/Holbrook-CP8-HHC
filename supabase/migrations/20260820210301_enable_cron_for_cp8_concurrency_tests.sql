-- Production mirror of Supabase migration 20260820210301.
-- This installs Supabase Cron and a private-only race harness. It does not
-- schedule a permanent worker job and exposes no test table/function to anon
-- or authenticated roles.

create extension if not exists pg_cron with schema pg_catalog;
grant usage on schema cron to postgres;
grant all privileges on all tables in schema cron to postgres;

create table if not exists private.cp8_claim_race_results (
  race_id uuid not null,
  work_id uuid not null,
  handle text not null,
  ok boolean not null,
  detail text not null,
  started_at timestamptz not null default clock_timestamp(),
  finished_at timestamptz not null default clock_timestamp(),
  primary key (race_id, handle)
);
revoke all on private.cp8_claim_race_results from public, anon, authenticated;

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
  v_detail text;
begin
  begin
    perform * from public.cp8_moltbook_trusted_worker_claim_direct(p_handle, p_work_id, p_lease_minutes);
    v_detail := 'CLAIMED';
    insert into private.cp8_claim_race_results(race_id, work_id, handle, ok, detail, started_at, finished_at)
    values(p_race_id, p_work_id, p_handle, true, v_detail, v_started, clock_timestamp())
    on conflict (race_id, handle) do update
      set ok=excluded.ok, detail=excluded.detail, started_at=excluded.started_at, finished_at=excluded.finished_at;
  exception when others then
    insert into private.cp8_claim_race_results(race_id, work_id, handle, ok, detail, started_at, finished_at)
    values(p_race_id, p_work_id, p_handle, false, sqlerrm, v_started, clock_timestamp())
    on conflict (race_id, handle) do update
      set ok=excluded.ok, detail=excluded.detail, started_at=excluded.started_at, finished_at=excluded.finished_at;
  end;
end
$function$;
revoke all on function private.cp8_record_trusted_claim_attempt(uuid,text,uuid,integer) from public, anon, authenticated;
grant execute on function private.cp8_record_trusted_claim_attempt(uuid,text,uuid,integer) to postgres;
