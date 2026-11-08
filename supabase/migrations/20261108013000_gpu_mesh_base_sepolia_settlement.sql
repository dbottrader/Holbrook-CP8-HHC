-- Base Sepolia settlement queue for the public GPU mesh.
-- The edge function records payout addresses and queues a settlement after
-- two distinct verifiers agree. It does not hold the deployer key.
-- Settlement.sol mints to the worker and the two verifiers. It has no escrow.
-- A missing payout address is marked skipped_missing_payout and is not minted.
-- The row becomes pending again when that node registers an address.
-- anon and authenticated have no grants and no policies.

alter table public.gpumesh_nodes
  add column if not exists payout_address text not null default '';

alter table public.gpumesh_jobs
  add column if not exists settlement_tx_hash text not null default '';

alter table public.gpumesh_jobs
  add column if not exists settlement_tx_url text not null default '';

alter table public.gpumesh_jobs
  add column if not exists settlement_status text not null default '';

create table if not exists public.gpumesh_chain_settlements (
  id text primary key,
  job_id text not null unique,
  worker_id text not null,
  verifier1_id text not null default '',
  verifier2_id text not null default '',
  amount integer not null default 0,
  mesh_credits integer not null default 0,
  status text not null default 'awaiting_second_verifier',
  receipt jsonb,
  receipt_hash text not null default '',
  tx_hash text not null default '',
  tx_url text not null default '',
  detail text not null default '',
  created_at double precision not null default 0,
  updated_at double precision not null default 0
);

create index if not exists gpumesh_chain_settlements_status_idx
  on public.gpumesh_chain_settlements (status, created_at);

comment on table public.gpumesh_chain_settlements is
  'Queue for HHCW Settlement.settle on Base Sepolia. The deployer key is not stored here.';

alter table public.gpumesh_chain_settlements enable row level security;

revoke all on table public.gpumesh_chain_settlements from public, anon, authenticated;
grant select, insert, update, delete on table public.gpumesh_chain_settlements to service_role;

do $$
begin
  if not exists (
    select 1 from pg_policies
    where schemaname = 'public'
      and tablename = 'gpumesh_chain_settlements'
      and policyname = 'gpumesh_chain_settlements_no_client'
  ) then
    execute $policy$
      create policy gpumesh_chain_settlements_no_client
      on public.gpumesh_chain_settlements
      as restrictive
      for all
      to anon, authenticated
      using (false)
      with check (false)
    $policy$;
  end if;
end $$;
