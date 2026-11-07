-- Public GPU mesh coordinator state.
-- The edge function uses the service role. anon and authenticated have no
-- grants and no policies, so the Data API cannot read node tokens, the
-- signing seed, prompts, or completions.

create table if not exists public.gpumesh_nodes (
  id text primary key,
  name text not null,
  token_hash text not null unique,
  backend text not null default 'cpu',
  gpu_name text not null default 'cpu',
  vram_mb integer not null default 0,
  gpu_count integer not null default 0,
  driver text not null default '',
  models jsonb not null default '[]'::jsonb,
  status text not null default 'online',
  reputation integer not null default 100,
  strikes integer not null default 0,
  credits integer not null default 0,
  escrow_credits integer not null default 0,
  suspicion integer not null default 0,
  trusted integer not null default 0,
  verified_jobs integer not null default 0,
  consecutive_failures integer not null default 0,
  jobs_completed integer not null default 0,
  jobs_failed integer not null default 0,
  inflight integer not null default 0,
  max_inflight integer not null default 1,
  last_heartbeat double precision not null default 0,
  last_ip text not null default '',
  created_at double precision not null default 0,
  version text not null default ''
);

create table if not exists public.gpumesh_jobs (
  id text primary key,
  kind text not null default 'inference',
  status text not null default 'queued',
  model text not null,
  messages jsonb not null default '[]'::jsonb,
  temperature double precision not null default 0,
  max_tokens integer not null default 256,
  seed integer,
  stop jsonb,
  assigned_node_id text not null default '',
  origin_node_id text not null default '',
  parent_job_id text not null default '',
  excluded jsonb not null default '[]'::jsonb,
  attempt integer not null default 0,
  max_attempts integer not null default 3,
  output_text text not null default '',
  output_hash text not null default '',
  prompt_tokens integer not null default 0,
  completion_tokens integer not null default 0,
  duration_ms integer not null default 0,
  finish_reason text not null default '',
  credits_awarded integer not null default 0,
  error text not null default '',
  verdict text not null default '',
  client_key text not null default '',
  receipt_hash text not null default '',
  created_at double precision not null default 0,
  assigned_at double precision not null default 0,
  completed_at double precision not null default 0,
  deadline_at double precision not null default 0,
  lease_generation integer not null default 0,
  lease_expires_at double precision not null default 0,
  model_digest text not null default '',
  priority integer not null default 0
);

create index if not exists gpumesh_jobs_status_idx on public.gpumesh_jobs (status, priority desc, created_at);
create index if not exists gpumesh_nodes_heartbeat_idx on public.gpumesh_nodes (status, last_heartbeat);

create table if not exists public.gpumesh_chunks (
  job_id text not null,
  seq integer not null,
  text text not null default '',
  primary key (job_id, seq)
);

create table if not exists public.gpumesh_ledger (
  seq integer primary key,
  ts bigint not null,
  actor text not null,
  kind text not null,
  payload text not null,
  prev_hash text not null,
  hash text not null unique,
  canon text not null default 'v1',
  amount integer not null default 0,
  signature text not null,
  signer text not null,
  typed_data jsonb not null
);

create table if not exists public.gpumesh_settlements (
  idempotency_key text primary key,
  job_id text not null,
  node_id text not null,
  kind text not null,
  credits integer not null default 0,
  ledger_seq integer not null
);

create table if not exists public.gpumesh_rate (
  bucket text primary key,
  window_start bigint not null,
  hits integer not null default 0
);

-- Public signing key only. The seed stays in the function environment or Vault.
create table if not exists public.gpumesh_signer (
  id integer primary key check (id = 1),
  public_hex text not null
);

alter table public.gpumesh_nodes enable row level security;
alter table public.gpumesh_jobs enable row level security;
alter table public.gpumesh_chunks enable row level security;
alter table public.gpumesh_ledger enable row level security;
alter table public.gpumesh_settlements enable row level security;
alter table public.gpumesh_rate enable row level security;
alter table public.gpumesh_signer enable row level security;

revoke all on table public.gpumesh_nodes from public, anon, authenticated;
revoke all on table public.gpumesh_jobs from public, anon, authenticated;
revoke all on table public.gpumesh_chunks from public, anon, authenticated;
revoke all on table public.gpumesh_ledger from public, anon, authenticated;
revoke all on table public.gpumesh_settlements from public, anon, authenticated;
revoke all on table public.gpumesh_rate from public, anon, authenticated;
revoke all on table public.gpumesh_signer from public, anon, authenticated;

grant select, insert, update, delete on table public.gpumesh_nodes to service_role;
grant select, insert, update, delete on table public.gpumesh_jobs to service_role;
grant select, insert, update, delete on table public.gpumesh_chunks to service_role;
grant select, insert, update, delete on table public.gpumesh_ledger to service_role;
grant select, insert, update, delete on table public.gpumesh_settlements to service_role;
grant select, insert, update, delete on table public.gpumesh_rate to service_role;
grant select, insert, update, delete on table public.gpumesh_signer to service_role;

-- Fresh installs deny anon and authenticated. The follow-up migration is the
-- same statements, guarded so applying both is safe.
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

