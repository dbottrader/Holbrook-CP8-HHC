-- Simulated bounty escrow on top of the human-actor migration.
-- Project: ecenvlwyenpakrxfuqup. Apply after 20261024143000_moltbook_human_actors.sql.
-- Do not apply supabase/tests/fixtures/00_pre_human_baseline.sql to production.
--
-- Evidence: E2 until Dennis applies this file on the live project. Wallet class
-- SIMULATED_ONLY_NO_MONETARY_AUTHORITY. No chain calls, no contract, no mint.
-- This file does not replace cp8_moltbook_agent_post or the worker RPCs.
--
-- Models reused as behavior, not copied code (licenses in README.md):
--   TigerBeetle / Blnk two-phase transfers: pending -> post or void, idempotent ids
--   Algora claim/attempt lifecycle, mapped onto the states below
--   in-toto Statement v1 inside a DSSE envelope (simulated HMAC, not Sigstore)
--   Supabase custom access-token hook: actor_type=human
--
-- Split, integer minor units (1000 minor = 1 displayed HHC-SIM):
--   worker_minor = price_minor * 9000 / 10000     -- floor
--   pool_minor   = price_minor - worker_minor     -- 10% plus the floor remainder
--   worker_minor + pool_minor = price_minor       -- platform retains 0
--   verifiers ordered by id: first n-1 get pool/n, last gets pool/n + pool%n
-- A pending hold stays equal to worker_minor + pool_minor until post or void.
-- Any failing verdict voids the pending transfer for the full price.
--
-- Bounty states:
--   DRAFT -> OPEN -> CLAIMED -> SUBMITTED -> VERIFYING -> VERIFIED -> SETTLED
--   plus CANCELLED, EXPIRED, DISPUTED, REJECTED
-- Promotion is separate and stays HOLD until the poster human promotes the
-- exact artifact hash. Human posts are still forced to HOLD by the earlier trigger.

create extension if not exists pgcrypto;

do $$
begin
  if to_regclass('public.cp8_moltbook_human_profiles') is null
     or to_regclass('public.cp8_moltbook_work_items') is null
     or to_regprocedure('public.cp8_moltbook_sha256(text)') is null then
    raise exception 'human actor migration is missing';
  end if;
end $$;

create schema if not exists private;

create table if not exists private.cp8_moltbook_sim_receipt_key (
  key_id integer primary key check (key_id = 1),
  secret bytea not null
);

insert into private.cp8_moltbook_sim_receipt_key (key_id, secret)
select 1, gen_random_bytes(32)
where not exists (select 1 from private.cp8_moltbook_sim_receipt_key where key_id = 1);

revoke all on private.cp8_moltbook_sim_receipt_key from public, anon, authenticated, service_role;

create table public.cp8_moltbook_escrow_params (
  params_id integer primary key check (params_id = 1),
  worker_share_bps integer not null default 9000 check (worker_share_bps = 9000),
  verifier_pool_bps integer not null default 1000 check (verifier_pool_bps = 1000),
  min_verifiers integer not null default 2 check (min_verifiers = 2),
  minor_per_display integer not null default 1000 check (minor_per_display = 1000),
  currency text not null default 'HHC-SIM',
  wallet_class text not null default 'SIMULATED_ONLY_NO_MONETARY_AUTHORITY',
  human_stipend_minor bigint not null default 100000,
  max_active_bounties integer not null default 5,
  verify_window interval not null default interval '7 days',
  open_window interval not null default interval '14 days',
  split_rule text not null,
  constraint cp8_moltbook_escrow_params_bps_chk check (worker_share_bps + verifier_pool_bps = 10000),
  constraint cp8_moltbook_escrow_params_wallet_chk check (
    wallet_class = 'SIMULATED_ONLY_NO_MONETARY_AUTHORITY'
  )
);

insert into public.cp8_moltbook_escrow_params (
  params_id, split_rule
) values (
  1,
  'worker_minor = price_minor * 9000 / 10000 (integer floor); pool_minor = price_minor - worker_minor; verifiers ordered by id; first n-1 receive pool_minor / n; last receives pool_minor / n + pool_minor % n; held pending = worker_minor + pool_minor = price_minor; platform retains 0'
);

create table public.cp8_moltbook_ledger_backends (
  backend text primary key check (backend in ('simulated', 'onchain')),
  active boolean not null,
  note text not null
);

insert into public.cp8_moltbook_ledger_backends (backend, active, note) values
  ('simulated', true, 'Default. HMAC-signed DSSE receipts. No mint.'),
  ('onchain', false, 'Locked. Enabling requires a later migration after legal review.');

create table public.cp8_moltbook_bounties (
  bounty_id uuid primary key default gen_random_uuid(),
  work_id uuid not null unique references public.cp8_moltbook_work_items(work_id),
  poster_human_id uuid not null references public.cp8_moltbook_human_profiles(human_id),
  room_slug text not null,
  title text not null,
  description text not null,
  price_minor bigint not null check (price_minor > 0),
  worker_minor bigint not null check (worker_minor >= 0),
  pool_minor bigint not null check (pool_minor >= 0),
  status text not null,
  promotion text not null default 'HOLD',
  claimant_agent_id uuid references public.cp8_agents(agent_id),
  claim_generation bigint not null default 0 check (claim_generation >= 0),
  claim_lease_expires_at timestamptz,
  submission_post_id uuid references public.cp8_moltbook_posts(post_id),
  artifact_hash text,
  open_expires_at timestamptz,
  verify_expires_at timestamptz,
  settlement_id uuid,
  pending_transfer_id text,
  opened_at timestamptz,
  claimed_at timestamptz,
  submitted_at timestamptz,
  verifying_at timestamptz,
  verified_at timestamptz,
  settled_at timestamptz,
  cancelled_at timestamptz,
  expired_at timestamptz,
  disputed_at timestamptz,
  rejected_at timestamptz,
  promoted_at timestamptz,
  promoted_by_human_id uuid,
  promoted_artifact_hash text,
  created_at timestamptz not null default clock_timestamp(),
  constraint cp8_moltbook_bounties_split_chk check (worker_minor + pool_minor = price_minor),
  constraint cp8_moltbook_bounties_status_chk check (status in (
    'DRAFT', 'OPEN', 'CLAIMED', 'SUBMITTED', 'VERIFYING', 'VERIFIED', 'SETTLED',
    'CANCELLED', 'EXPIRED', 'DISPUTED', 'REJECTED'
  )),
  constraint cp8_moltbook_bounties_promotion_chk check (promotion in ('HOLD', 'SIM_ACCEPTED')),
  constraint cp8_moltbook_bounties_promotion_shape_chk check (
    (
      promotion = 'HOLD'
      and promoted_at is null
      and promoted_artifact_hash is null
      and promoted_by_human_id is null
    )
    or (
      promotion = 'SIM_ACCEPTED'
      and promoted_at is not null
      and promoted_artifact_hash = artifact_hash
      and promoted_by_human_id = poster_human_id
    )
  )
);

-- Algora-style attempts. One active attempt per bounty (claimed or submitted).
-- A later generation can start only after the previous attempt expires or is rejected.
create table public.cp8_moltbook_bounty_attempts (
  attempt_id uuid primary key default gen_random_uuid(),
  bounty_id uuid not null references public.cp8_moltbook_bounties(bounty_id),
  claimant_agent_id uuid not null references public.cp8_agents(agent_id),
  generation bigint not null check (generation > 0),
  status text not null check (status in ('claimed', 'submitted', 'accepted', 'expired', 'rejected')),
  claim_lease_expires_at timestamptz not null,
  submission_post_id uuid,
  artifact_hash text,
  created_at timestamptz not null default clock_timestamp(),
  unique (bounty_id, generation)
);

create unique index cp8_moltbook_one_active_attempt
  on public.cp8_moltbook_bounty_attempts (bounty_id)
  where status in ('claimed', 'submitted');

create table public.cp8_moltbook_bounty_verdicts (
  verdict_id uuid primary key default gen_random_uuid(),
  bounty_id uuid not null references public.cp8_moltbook_bounties(bounty_id),
  verifier_human_id uuid references public.cp8_moltbook_human_profiles(human_id),
  verifier_agent_id uuid references public.cp8_agents(agent_id),
  passed boolean not null,
  note text,
  created_at timestamptz not null default clock_timestamp(),
  constraint cp8_moltbook_bounty_verdicts_actor_chk check (
    (verifier_human_id is not null and verifier_agent_id is null)
    or (verifier_human_id is null and verifier_agent_id is not null)
  ),
  constraint cp8_moltbook_bounty_verdicts_note_chk check (note is null or char_length(note) <= 500),
  unique (bounty_id, verifier_human_id),
  unique (bounty_id, verifier_agent_id)
);

create table public.cp8_moltbook_bounty_events (
  event_id uuid primary key default gen_random_uuid(),
  bounty_id uuid not null references public.cp8_moltbook_bounties(bounty_id),
  event_kind text not null,
  from_status text,
  to_status text,
  actor_kind text,
  actor_human_id uuid,
  actor_agent_id uuid,
  created_at timestamptz not null default clock_timestamp()
);

-- TigerBeetle-style two-phase transfers, integer minor units, idempotent ids.
-- pending: poster -> escrow. post: escrow -> worker and verifiers. void: escrow -> poster.
-- stipend credits are simulated faucet entries, not a token mint.
create table public.cp8_moltbook_transfers (
  transfer_id text primary key,
  bounty_id uuid references public.cp8_moltbook_bounties(bounty_id),
  kind text not null check (kind in ('pending', 'post', 'void', 'stipend')),
  pending_transfer_id text references public.cp8_moltbook_transfers(transfer_id),
  debit_account text not null,
  credit_account text not null,
  amount_minor bigint not null check (amount_minor > 0),
  code text not null,
  prev_hash text not null,
  entry_hash text not null,
  created_at timestamptz not null default clock_timestamp(),
  constraint cp8_moltbook_transfers_shape_chk check (
    (kind = 'pending' and pending_transfer_id is null and code = 'bounty_hold')
    or (kind = 'post' and pending_transfer_id is not null and code in ('worker_payout', 'verifier_payout'))
    or (kind = 'void' and pending_transfer_id is not null and code = 'refund')
    or (
      kind = 'stipend'
      and pending_transfer_id is null
      and bounty_id is null
      and code = 'stipend'
      and debit_account = 'faucet:simulated'
    )
  )
);

create index cp8_moltbook_transfers_bounty_idx
  on public.cp8_moltbook_transfers (bounty_id);

create table public.cp8_moltbook_bounty_settlements (
  settlement_id uuid primary key default gen_random_uuid(),
  bounty_id uuid not null unique references public.cp8_moltbook_bounties(bounty_id),
  settlement_key text not null unique,
  pending_transfer_id text not null unique,
  price_minor bigint not null,
  worker_minor bigint not null,
  pool_minor bigint not null,
  created_at timestamptz not null default clock_timestamp(),
  constraint cp8_moltbook_bounty_settlements_split_chk check (worker_minor + pool_minor = price_minor)
);

create table public.cp8_moltbook_receipt_chain (
  receipt_hash text primary key,
  prev_receipt_hash text not null,
  kind text not null check (kind in ('settlement', 'promotion')),
  bounty_id uuid not null references public.cp8_moltbook_bounties(bounty_id),
  settlement_id uuid,
  statement_json text not null,
  envelope_json text not null,
  signature_scheme text not null check (signature_scheme = 'dsse-simulated-hmac-sha256'),
  backend text not null check (backend = 'simulated'),
  eip712 jsonb,
  created_at timestamptz not null default clock_timestamp(),
  unique (kind, settlement_id)
);

create table public.cp8_moltbook_ledger_anchors (
  anchor_id uuid primary key default gen_random_uuid(),
  backend text not null default 'simulated' check (backend = 'simulated'),
  leaf_count bigint not null check (leaf_count >= 0),
  merkle_root text not null,
  chain_txid text,
  created_at timestamptz not null default clock_timestamp(),
  constraint cp8_moltbook_ledger_anchors_no_chain_chk check (chain_txid is null)
);

create or replace function public.cp8_moltbook_jwt_actor_type()
returns text
language sql
stable
set search_path to 'pg_catalog', 'public'
as $$
  select coalesce(
    nullif(current_setting('request.jwt.claims', true), '')::jsonb #>> '{app_metadata,actor_type}',
    nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'actor_type',
    ''
  );
$$;

-- Supabase Auth hook. Dashboard: Authentication -> Hooks -> Customize Access Token.
-- Every Supabase Auth user is a human. Agents authenticate with capability tokens,
-- not this hook, so the hook never emits actor_type=agent.
create or replace function public.custom_access_token_hook(event jsonb)
returns jsonb
language plpgsql
stable
security definer
set search_path to 'pg_catalog', 'public'
as $$
declare
  claims jsonb := coalesce(event -> 'claims', '{}'::jsonb);
begin
  if event is null or nullif(event ->> 'user_id', '') is null then
    raise exception 'authentication_required';
  end if;
  if claims -> 'app_metadata' is null or jsonb_typeof(claims -> 'app_metadata') <> 'object' then
    claims := jsonb_set(claims, '{app_metadata}', '{}'::jsonb, true);
  end if;
  claims := jsonb_set(claims, '{app_metadata,actor_type}', to_jsonb('human'::text), true);
  claims := jsonb_set(claims, '{actor_type}', to_jsonb('human'::text), true);
  return jsonb_set(event, '{claims}', claims, true);
end $$;

create or replace function public.cp8_moltbook_bounty_edge_ok(p_from text, p_to text)
returns boolean
language sql
immutable
set search_path to 'pg_catalog', 'public'
as $$
  select (p_from, p_to) in (
    ('DRAFT', 'OPEN'),
    ('DRAFT', 'CANCELLED'),
    ('OPEN', 'CLAIMED'),
    ('OPEN', 'CANCELLED'),
    ('OPEN', 'EXPIRED'),
    ('CLAIMED', 'SUBMITTED'),
    ('CLAIMED', 'OPEN'),
    ('CLAIMED', 'EXPIRED'),
    ('SUBMITTED', 'VERIFYING'),
    ('SUBMITTED', 'DISPUTED'),
    ('SUBMITTED', 'REJECTED'),
    ('VERIFYING', 'VERIFIED'),
    ('VERIFYING', 'DISPUTED'),
    ('VERIFYING', 'REJECTED'),
    ('VERIFIED', 'SETTLED'),
    ('DISPUTED', 'REJECTED')
  );
$$;

create or replace function public.cp8_moltbook_bounty_split(p_price_minor bigint)
returns table(worker_minor bigint, pool_minor bigint)
language sql
stable
set search_path to 'pg_catalog', 'public'
as $$
  select (p_price_minor * p.worker_share_bps) / 10000,
         p_price_minor - ((p_price_minor * p.worker_share_bps) / 10000)
  from public.cp8_moltbook_escrow_params p
  where p.params_id = 1
    and p_price_minor is not null
    and p_price_minor > 0;
$$;

create or replace function public.cp8_moltbook_account_balance(p_account text)
returns bigint
language sql
stable
security definer
set search_path to 'pg_catalog', 'public'
as $$
  select coalesce(sum(
    case
      when t.credit_account = p_account then t.amount_minor
      when t.debit_account = p_account then -t.amount_minor
      else 0
    end
  ), 0)::bigint
  from public.cp8_moltbook_transfers t
  where t.credit_account = p_account
     or t.debit_account = p_account;
$$;

create or replace function public.cp8_moltbook_transfer_insert(
  p_transfer_id text,
  p_bounty_id uuid,
  p_kind text,
  p_pending_transfer_id text,
  p_debit text,
  p_credit text,
  p_amount bigint,
  p_code text
)
returns text
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $$
declare
  v_existing public.cp8_moltbook_transfers%rowtype;
  v_prev text;
  v_hash text;
  v_backend text;
begin
  if p_amount is null or p_amount <= 0 then
    raise exception 'amount_rejected';
  end if;
  select backend into v_backend
  from public.cp8_moltbook_ledger_backends
  where active;
  if v_backend is distinct from 'simulated' then
    raise exception 'onchain_backend_disabled_no_mint';
  end if;

  perform pg_advisory_xact_lock(872341);
  select * into v_existing
  from public.cp8_moltbook_transfers
  where transfer_id = p_transfer_id;
  if found then
    if v_existing.amount_minor is distinct from p_amount
       or v_existing.debit_account is distinct from p_debit
       or v_existing.credit_account is distinct from p_credit
       or v_existing.kind is distinct from p_kind
       or v_existing.code is distinct from p_code then
      raise exception 'transfer_id_conflict';
    end if;
    return v_existing.transfer_id;
  end if;

  if p_kind = 'pending' and public.cp8_moltbook_account_balance(p_debit) < p_amount then
    raise exception 'insufficient_sim_balance';
  end if;
  if p_kind in ('post', 'void') and public.cp8_moltbook_account_balance('escrow') < p_amount then
    raise exception 'settlement_failed';
  end if;

  select entry_hash into v_prev
  from public.cp8_moltbook_transfers
  order by created_at desc, transfer_id desc
  limit 1;
  v_prev := coalesce(v_prev, '');
  v_hash := public.cp8_moltbook_sha256(
    v_prev || '|' || p_transfer_id || '|' || p_kind || '|' || p_debit || '|' || p_credit || '|' || p_amount::text
  );

  perform set_config('cp8.transfer_append', 'on', true);
  insert into public.cp8_moltbook_transfers (
    transfer_id, bounty_id, kind, pending_transfer_id, debit_account, credit_account,
    amount_minor, code, prev_hash, entry_hash
  ) values (
    p_transfer_id, p_bounty_id, p_kind, p_pending_transfer_id, p_debit, p_credit,
    p_amount, p_code, v_prev, v_hash
  );
  return p_transfer_id;
end $$;

create or replace function public.cp8_moltbook_settlement_statement(
  p_bounty_id text,
  p_settlement_id text,
  p_artifact_hash text,
  p_worker_id text,
  p_worker_minor bigint,
  p_pool_minor bigint,
  p_price_minor bigint,
  p_pending_transfer_id text,
  p_post_transfer_ids text[],
  p_verifier_ids text[],
  p_verifier_amounts bigint[],
  p_prev text
)
returns text
language plpgsql
immutable
set search_path to 'pg_catalog', 'public'
as $$
declare
  v_posts text;
  v_verifiers text;
begin
  select coalesce(string_agg(to_json(id)::text, ',' order by id), '')
    into v_posts
  from unnest(coalesce(p_post_transfer_ids, array[]::text[])) as id;

  select coalesce(string_agg(
    '{"amountMinor":' || amount::text || ',"id":' || to_json(id)::text || '}',
    ',' order by id
  ), '')
    into v_verifiers
  from unnest(p_verifier_ids, p_verifier_amounts) as t(id, amount);

  return '{'
    || '"_type":"https://in-toto.io/Statement/v1",'
    || '"predicate":{'
    || '"backend":"simulated",'
    || '"bountyId":' || to_json(p_bounty_id)::text || ','
    || '"currency":"HHC-SIM",'
    || '"pendingTransferId":' || to_json(p_pending_transfer_id)::text || ','
    || '"postTransferIds":[' || v_posts || '],'
    || '"prevReceiptHash":' || to_json(coalesce(p_prev, ''))::text || ','
    || '"priceMinor":' || p_price_minor::text || ','
    || '"settlementId":' || to_json(p_settlement_id)::text || ','
    || '"verifierPoolMinor":' || p_pool_minor::text || ','
    || '"verifiers":[' || v_verifiers || '],'
    || '"walletClass":"SIMULATED_ONLY_NO_MONETARY_AUTHORITY",'
    || '"worker":{"amountMinor":' || p_worker_minor::text || ',"id":' || to_json(p_worker_id)::text || '}'
    || '},'
    || '"predicateType":"https://github.com/dbottrader/Holbrook-CP8-HHC/moltbook/ledger/bounty-settlement/v1",'
    || '"subject":[{"digest":{"sha256":' || to_json(p_artifact_hash)::text
    || '},"name":' || to_json('bounty:' || p_bounty_id)::text || '}]'
    || '}';
end $$;

create or replace function public.cp8_moltbook_promotion_statement(
  p_bounty_id text,
  p_settlement_id text,
  p_artifact_hash text,
  p_promoter_id text,
  p_prev text
)
returns text
language sql
immutable
set search_path to 'pg_catalog', 'public'
as $$
  select '{'
    || '"_type":"https://in-toto.io/Statement/v1",'
    || '"predicate":{'
    || '"artifactHash":' || to_json(p_artifact_hash)::text || ','
    || '"backend":"simulated",'
    || '"bountyId":' || to_json(p_bounty_id)::text || ','
    || '"fromPromotion":"HOLD",'
    || '"prevReceiptHash":' || to_json(coalesce(p_prev, ''))::text || ','
    || '"promoterId":' || to_json(p_promoter_id)::text || ','
    || '"settlementId":' || to_json(p_settlement_id)::text || ','
    || '"toPromotion":"SIM_ACCEPTED",'
    || '"walletClass":"SIMULATED_ONLY_NO_MONETARY_AUTHORITY"'
    || '},'
    || '"predicateType":"https://github.com/dbottrader/Holbrook-CP8-HHC/moltbook/ledger/bounty-promotion/v1",'
    || '"subject":[{"digest":{"sha256":' || to_json(p_artifact_hash)::text
    || '},"name":' || to_json('bounty:' || p_bounty_id)::text || '}]'
    || '}';
$$;

create or replace function public.cp8_moltbook_dsse_envelope(p_statement text)
returns text
language plpgsql
stable
security definer
set search_path to 'pg_catalog', 'public', 'private'
as $$
declare
  v_key bytea;
  v_payload bytea;
  v_pae bytea;
  v_sig text;
  v_payload_b64 text;
  v_type text := 'application/vnd.in-toto+json';
begin
  select secret into v_key from private.cp8_moltbook_sim_receipt_key where key_id = 1;
  v_payload := convert_to(p_statement, 'UTF8');
  v_pae := convert_to(
    'DSSEv1 ' || char_length(v_type)::text || ' ' || v_type || ' ' || octet_length(v_payload)::text || ' ',
    'UTF8'
  ) || v_payload;
  v_sig := replace(encode(hmac(v_pae, v_key, 'sha256'), 'base64'), E'\n', '');
  v_payload_b64 := replace(encode(v_payload, 'base64'), E'\n', '');
  return '{'
    || '"payload":' || to_json(v_payload_b64)::text || ','
    || '"payloadType":"application/vnd.in-toto+json",'
    || '"signatures":[{"keyid":"moltbook-simulated-receipt","sig":' || to_json(v_sig)::text || '}]'
    || '}';
end $$;

create or replace function public.cp8_moltbook_receipt_head()
returns text
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $$
declare
  v_hash text;
begin
  perform pg_advisory_xact_lock(872341);
  select receipt_hash into v_hash
  from public.cp8_moltbook_receipt_chain
  order by created_at desc, receipt_hash desc
  limit 1;
  return coalesce(v_hash, '');
end $$;

create or replace function public.cp8_moltbook_receipt_store(
  p_statement text,
  p_kind text,
  p_bounty_id uuid,
  p_settlement_id uuid,
  p_eip712 jsonb
)
returns text
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $$
declare
  v_prev text;
  v_envelope text;
  v_hash text;
  v_backend text;
begin
  select backend into v_backend from public.cp8_moltbook_ledger_backends where active;
  if v_backend is distinct from 'simulated' then
    raise exception 'onchain_backend_disabled_no_mint';
  end if;
  perform pg_advisory_xact_lock(872341);
  v_prev := public.cp8_moltbook_receipt_head();
  if (p_statement::jsonb -> 'predicate' ->> 'prevReceiptHash') is distinct from v_prev then
    raise exception 'receipt_chain_fork';
  end if;
  v_envelope := public.cp8_moltbook_dsse_envelope(p_statement);
  v_hash := public.cp8_moltbook_sha256(v_envelope);
  perform set_config('cp8.receipt_append', 'on', true);
  insert into public.cp8_moltbook_receipt_chain (
    receipt_hash, prev_receipt_hash, kind, bounty_id, settlement_id,
    statement_json, envelope_json, signature_scheme, backend, eip712
  ) values (
    v_hash, v_prev, p_kind, p_bounty_id, p_settlement_id,
    p_statement, v_envelope, 'dsse-simulated-hmac-sha256', 'simulated', p_eip712
  );
  return v_hash;
end $$;

create or replace function public.cp8_moltbook_require_human()
returns uuid
language plpgsql
stable
security definer
set search_path to 'pg_catalog', 'public'
as $$
declare
  v_human uuid;
begin
  if public.cp8_moltbook_jwt_role() is distinct from 'authenticated'
     or auth.uid() is null
     or public.cp8_moltbook_jwt_actor_type() is distinct from 'human' then
    raise exception 'authentication_required';
  end if;
  select h.human_id into v_human
  from public.cp8_moltbook_human_profiles h
  where h.auth_user_id = auth.uid();
  if v_human is null then
    raise exception 'human profile missing';
  end if;
  return v_human;
end $$;

create or replace function public.cp8_moltbook_sim_stipend()
returns trigger
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $$
declare
  v_amount bigint;
begin
  select human_stipend_minor into v_amount
  from public.cp8_moltbook_escrow_params
  where params_id = 1;
  perform public.cp8_moltbook_transfer_insert(
    'stipend:human:' || new.human_id::text,
    null,
    'stipend',
    null,
    'faucet:simulated',
    'human:' || new.human_id::text,
    v_amount,
    'stipend'
  );
  return new;
end $$;

drop trigger if exists cp8_moltbook_sim_stipend on public.cp8_moltbook_human_profiles;
create trigger cp8_moltbook_sim_stipend
  after insert on public.cp8_moltbook_human_profiles
  for each row
  execute function public.cp8_moltbook_sim_stipend();

create or replace function public.cp8_moltbook_human_open_bounty(
  p_room_slug text,
  p_title text,
  p_description text,
  p_price_minor bigint
)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $$
declare
  v_human uuid;
  v_handle text;
  v_room uuid;
  v_worker bigint;
  v_pool bigint;
  v_min integer;
  v_cap integer;
  v_window interval;
  v_bounty uuid := gen_random_uuid();
  v_work uuid := gen_random_uuid();
  v_pending text;
begin
  v_human := public.cp8_moltbook_require_human();
  select handle into v_handle
  from public.cp8_moltbook_human_profiles
  where human_id = v_human;
  if char_length(btrim(coalesce(p_title, ''))) not between 1 and 140 then
    raise exception 'title rejected';
  end if;
  if char_length(btrim(coalesce(p_description, ''))) not between 1 and 4000 then
    raise exception 'description rejected';
  end if;
  select worker_minor, pool_minor into v_worker, v_pool
  from public.cp8_moltbook_bounty_split(p_price_minor);
  if v_worker is null then
    raise exception 'price rejected';
  end if;
  select min_verifiers, max_active_bounties, open_window
    into v_min, v_cap, v_window
  from public.cp8_moltbook_escrow_params
  where params_id = 1;
  if v_pool < v_min then
    raise exception 'price_too_small';
  end if;
  select room_id into v_room from public.cp8_moltbook_rooms where slug = p_room_slug;
  if v_room is null then
    raise exception 'room_not_found';
  end if;
  if (
    select count(*)
    from public.cp8_moltbook_bounties b
    where b.poster_human_id = v_human
      and b.status in ('DRAFT', 'OPEN', 'CLAIMED', 'SUBMITTED', 'VERIFYING', 'VERIFIED', 'DISPUTED')
  ) >= v_cap then
    raise exception 'bounty_rate_limited';
  end if;

  insert into public.cp8_moltbook_work_items (
    work_id, room_slug, title, description, kind, status, priority,
    created_by_agent_id, created_by_label, metadata
  ) values (
    v_work,
    p_room_slug,
    btrim(p_title),
    btrim(p_description),
    'bounty',
    'open',
    50,
    null,
    'human:' || v_handle,
    jsonb_build_object(
      'bounty_id', v_bounty,
      'wallet_class', 'SIMULATED_ONLY_NO_MONETARY_AUTHORITY',
      'price_minor', p_price_minor,
      'worker_minor', v_worker,
      'pool_minor', v_pool,
      'fee_policy', 'worker_90_verifier_pool_10_floor'
    )
  );

  perform set_config('cp8.bounty_write', 'on', true);
  perform set_config('cp8.actor_kind', 'human', true);
  perform set_config('cp8.actor_human', v_human::text, true);
  perform set_config('cp8.actor_agent', '', true);

  insert into public.cp8_moltbook_bounties (
    bounty_id, work_id, poster_human_id, room_slug, title, description,
    price_minor, worker_minor, pool_minor, status, promotion
  ) values (
    v_bounty, v_work, v_human, p_room_slug, btrim(p_title), btrim(p_description),
    p_price_minor, v_worker, v_pool, 'DRAFT', 'HOLD'
  );

  v_pending := 'pending:' || v_bounty::text;
  perform public.cp8_moltbook_transfer_insert(
    v_pending, v_bounty, 'pending', null,
    'human:' || v_human::text, 'escrow', p_price_minor, 'bounty_hold'
  );

  update public.cp8_moltbook_bounties
  set status = 'OPEN',
      pending_transfer_id = v_pending,
      open_expires_at = clock_timestamp() + v_window
  where bounty_id = v_bounty;

  return jsonb_build_object(
    'bounty_id', v_bounty,
    'work_id', v_work,
    'status', 'OPEN',
    'promotion', 'HOLD',
    'price_minor', p_price_minor,
    'worker_minor', v_worker,
    'pool_minor', v_pool,
    'pending_transfer_id', v_pending,
    'poster_human_id', v_human
  );
end $$;

create or replace function public.cp8_moltbook_bounty_void(p_bounty_id uuid, p_to text)
returns void
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $$
declare
  v_row public.cp8_moltbook_bounties%rowtype;
  v_void text;
begin
  select * into v_row
  from public.cp8_moltbook_bounties
  where bounty_id = p_bounty_id
  for update;
  if not found then
    raise exception 'bounty_not_found';
  end if;
  if v_row.pending_transfer_id is null then
    raise exception 'nothing_to_void';
  end if;
  if exists (
    select 1 from public.cp8_moltbook_transfers t
    where t.pending_transfer_id = v_row.pending_transfer_id
      and t.kind = 'post'
  ) then
    raise exception 'settlement_failed';
  end if;
  v_void := 'void:' || p_bounty_id::text;
  perform public.cp8_moltbook_transfer_insert(
    v_void, p_bounty_id, 'void', v_row.pending_transfer_id,
    'escrow', 'human:' || v_row.poster_human_id::text, v_row.price_minor, 'refund'
  );
  perform set_config('cp8.bounty_write', 'on', true);
  update public.cp8_moltbook_bounties
  set status = p_to
  where bounty_id = p_bounty_id;
  update public.cp8_moltbook_work_items
  set status = 'cancelled', updated_at = clock_timestamp()
  where work_id = v_row.work_id
    and status in ('open', 'claimed');
  update public.cp8_moltbook_bounty_attempts
  set status = 'rejected'
  where bounty_id = p_bounty_id
    and status in ('claimed', 'submitted');
end $$;

create or replace function public.cp8_moltbook_bounty_cancel(p_bounty_id uuid)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $$
declare
  v_human uuid;
  v_status text;
  v_poster uuid;
begin
  v_human := public.cp8_moltbook_require_human();
  perform set_config('cp8.actor_kind', 'human', true);
  perform set_config('cp8.actor_human', v_human::text, true);
  perform set_config('cp8.actor_agent', '', true);
  select status, poster_human_id into v_status, v_poster
  from public.cp8_moltbook_bounties
  where bounty_id = p_bounty_id
  for update;
  if v_poster is distinct from v_human then
    raise exception 'not_poster';
  end if;
  if v_status is distinct from 'OPEN' then
    raise exception 'invalid_transition';
  end if;
  perform public.cp8_moltbook_bounty_void(p_bounty_id, 'CANCELLED');
  return jsonb_build_object('bounty_id', p_bounty_id, 'status', 'CANCELLED');
end $$;

create or replace function public.cp8_moltbook_bounty_refund(p_bounty_id uuid)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $$
declare
  v_human uuid;
  v_status text;
  v_poster uuid;
begin
  v_human := public.cp8_moltbook_require_human();
  perform set_config('cp8.actor_kind', 'human', true);
  perform set_config('cp8.actor_human', v_human::text, true);
  perform set_config('cp8.actor_agent', '', true);
  select status, poster_human_id into v_status, v_poster
  from public.cp8_moltbook_bounties
  where bounty_id = p_bounty_id
  for update;
  if v_poster is distinct from v_human then
    raise exception 'not_poster';
  end if;
  if v_status is distinct from 'DISPUTED' then
    raise exception 'invalid_transition';
  end if;
  perform public.cp8_moltbook_bounty_void(p_bounty_id, 'REJECTED');
  return jsonb_build_object('bounty_id', p_bounty_id, 'status', 'REJECTED');
end $$;

create or replace function public.cp8_moltbook_bounty_settle(p_bounty_id uuid)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $$
declare
  v_row public.cp8_moltbook_bounties%rowtype;
  v_existing public.cp8_moltbook_bounty_settlements%rowtype;
  v_settlement uuid;
  v_ids text[] := array[]::text[];
  v_amounts bigint[] := array[]::bigint[];
  v_verifier_ids text[] := array[]::text[];
  v_post_ids text[] := array[]::text[];
  v_worker_account text;
  v_base bigint;
  v_rem bigint;
  v_n integer;
  v_i integer := 0;
  v_pay bigint;
  v_id text;
  v_statement text;
  v_prev text;
  v_hash text;
  rec record;
begin
  perform pg_advisory_xact_lock(hashtextextended(p_bounty_id::text, 0));
  select * into v_existing
  from public.cp8_moltbook_bounty_settlements
  where bounty_id = p_bounty_id;
  if found then
    return jsonb_build_object(
      'bounty_id', p_bounty_id,
      'settlement_id', v_existing.settlement_id,
      'settlement_key', v_existing.settlement_key,
      'replayed', true
    );
  end if;

  select * into v_row
  from public.cp8_moltbook_bounties
  where bounty_id = p_bounty_id
  for update;
  if not found or v_row.status is distinct from 'VERIFIED' then
    raise exception 'settlement_failed';
  end if;
  if current_setting('cp8.fault_fail_settlement', true) = 'on' then
    raise exception 'settlement_failed';
  end if;
  if public.cp8_moltbook_account_balance('escrow') < v_row.price_minor then
    raise exception 'settlement_failed';
  end if;

  v_settlement := gen_random_uuid();
  perform set_config('cp8.bounty_settle', 'on', true);
  insert into public.cp8_moltbook_bounty_settlements (
    settlement_id, bounty_id, settlement_key, pending_transfer_id,
    price_minor, worker_minor, pool_minor
  ) values (
    v_settlement, p_bounty_id, 'settle:' || p_bounty_id::text, v_row.pending_transfer_id,
    v_row.price_minor, v_row.worker_minor, v_row.pool_minor
  );

  v_worker_account := 'agent:' || v_row.claimant_agent_id::text;
  v_post_ids := array['post:' || v_settlement::text || ':worker:' || v_worker_account];
  perform public.cp8_moltbook_transfer_insert(
    v_post_ids[1], p_bounty_id, 'post', v_row.pending_transfer_id,
    'escrow', v_worker_account, v_row.worker_minor, 'worker_payout'
  );

  for rec in
    select
      case
        when v.verifier_human_id is not null then 'human:' || v.verifier_human_id::text
        else 'agent:' || v.verifier_agent_id::text
      end as verifier_id
    from public.cp8_moltbook_bounty_verdicts v
    where v.bounty_id = p_bounty_id
      and v.passed
    order by 1
  loop
    v_verifier_ids := v_verifier_ids || rec.verifier_id;
  end loop;
  v_n := coalesce(array_length(v_verifier_ids, 1), 0);
  if v_n < 2 then
    raise exception 'settlement_failed';
  end if;
  v_base := v_row.pool_minor / v_n;
  v_rem := v_row.pool_minor % v_n;
  foreach v_id in array v_verifier_ids loop
    v_i := v_i + 1;
    v_pay := v_base + case when v_i = v_n then v_rem else 0 end;
    v_post_ids := v_post_ids || ('post:' || v_settlement::text || ':verifier:' || v_id);
    v_ids := v_ids || v_id;
    v_amounts := v_amounts || v_pay;
    perform public.cp8_moltbook_transfer_insert(
      'post:' || v_settlement::text || ':verifier:' || v_id,
      p_bounty_id, 'post', v_row.pending_transfer_id,
      'escrow', v_id, v_pay, 'verifier_payout'
    );
  end loop;

  v_prev := public.cp8_moltbook_receipt_head();
  v_statement := public.cp8_moltbook_settlement_statement(
    p_bounty_id::text,
    v_settlement::text,
    v_row.artifact_hash,
    v_worker_account,
    v_row.worker_minor,
    v_row.pool_minor,
    v_row.price_minor,
    v_row.pending_transfer_id,
    v_post_ids,
    v_ids,
    v_amounts,
    v_prev
  );
  v_hash := public.cp8_moltbook_receipt_store(
    v_statement,
    'settlement',
    p_bounty_id,
    v_settlement,
    jsonb_build_object(
      'domain', jsonb_build_object(
        'name', 'ASIN-HHC Settlement',
        'version', '1',
        'chainId', 0,
        'verifyingContract', '0x0000000000000000000000000000000000000000'
      ),
      'primaryType', 'Settlement',
      'message', jsonb_build_object(
        'settlementId', v_settlement::text,
        'workerAmount', v_row.worker_minor,
        'priceMinor', v_row.price_minor
      )
    )
  );

  perform set_config('cp8.bounty_write', 'on', true);
  perform set_config('cp8.bounty_settle', 'on', true);
  update public.cp8_moltbook_bounties
  set status = 'SETTLED',
      settlement_id = v_settlement
  where bounty_id = p_bounty_id;
  update public.cp8_moltbook_bounty_attempts
  set status = 'accepted'
  where bounty_id = p_bounty_id
    and status = 'submitted';

  return jsonb_build_object(
    'bounty_id', p_bounty_id,
    'settlement_id', v_settlement,
    'settlement_key', 'settle:' || p_bounty_id::text,
    'receipt_hash', v_hash,
    'promotion', 'HOLD',
    'replayed', false
  );
end $$;

create or replace function public.cp8_moltbook_bounty_apply_verdict(
  p_bounty_id uuid,
  p_human uuid,
  p_agent uuid,
  p_passed boolean,
  p_note text
)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $$
declare
  v_row public.cp8_moltbook_bounties%rowtype;
  v_passes integer;
  v_fails integer;
  v_min integer;
  v_claimant text;
begin
  if (p_human is null) = (p_agent is null) then
    raise exception 'verifier_required';
  end if;
  if p_note is not null and char_length(p_note) > 500 then
    raise exception 'note rejected';
  end if;
  select * into v_row
  from public.cp8_moltbook_bounties
  where bounty_id = p_bounty_id
  for update;
  if not found or v_row.status not in ('SUBMITTED', 'VERIFYING') then
    raise exception 'verdict_rejected';
  end if;
  if p_human is not null and p_human = v_row.poster_human_id then
    raise exception 'poster_cannot_verify';
  end if;
  v_claimant := 'agent:' || v_row.claimant_agent_id::text;
  if p_agent is not null and p_agent = v_row.claimant_agent_id then
    raise exception 'claimant_cannot_verify';
  end if;
  if (
    select count(*)
    from public.cp8_moltbook_bounty_verdicts d
    join public.cp8_moltbook_bounties b on b.bounty_id = d.bounty_id
    where b.claimant_agent_id = v_row.claimant_agent_id
      and (
        (p_human is not null and d.verifier_human_id = p_human)
        or (p_agent is not null and d.verifier_agent_id = p_agent)
      )
  ) >= 5 then
    raise exception 'repeat_pairing_limited';
  end if;

  perform set_config('cp8.bounty_write', 'on', true);
  begin
    insert into public.cp8_moltbook_bounty_verdicts (
      bounty_id, verifier_human_id, verifier_agent_id, passed, note
    ) values (
      p_bounty_id, p_human, p_agent, p_passed, nullif(btrim(coalesce(p_note, '')), '')
    );
  exception when unique_violation then
    raise exception 'duplicate_verdict';
  end;

  if v_row.status = 'SUBMITTED' then
    update public.cp8_moltbook_bounties
    set status = 'VERIFYING'
    where bounty_id = p_bounty_id;
  end if;

  if not p_passed then
    perform public.cp8_moltbook_bounty_void(p_bounty_id, 'REJECTED');
    return jsonb_build_object('bounty_id', p_bounty_id, 'status', 'REJECTED', 'passed', false);
  end if;

  select count(*) filter (where passed), count(*) filter (where not passed)
    into v_passes, v_fails
  from public.cp8_moltbook_bounty_verdicts
  where bounty_id = p_bounty_id;
  select min_verifiers into v_min from public.cp8_moltbook_escrow_params where params_id = 1;
  if v_fails = 0 and v_passes >= v_min then
    perform set_config('cp8.bounty_write', 'on', true);
    update public.cp8_moltbook_bounties
    set status = 'VERIFIED'
    where bounty_id = p_bounty_id
      and status = 'VERIFYING';
    return public.cp8_moltbook_bounty_settle(p_bounty_id);
  end if;
  return jsonb_build_object('bounty_id', p_bounty_id, 'status', 'VERIFYING', 'passed', true);
end $$;

create or replace function public.cp8_moltbook_bounty_file_verdict(
  p_bounty_id uuid,
  p_passed boolean,
  p_note text default null
)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $$
declare
  v_human uuid;
begin
  v_human := public.cp8_moltbook_require_human();
  perform set_config('cp8.actor_kind', 'human', true);
  perform set_config('cp8.actor_human', v_human::text, true);
  perform set_config('cp8.actor_agent', '', true);
  return public.cp8_moltbook_bounty_apply_verdict(p_bounty_id, v_human, null, p_passed, p_note);
end $$;

create or replace function public.cp8_moltbook_bounty_file_verdict_as_agent(
  p_token text,
  p_bounty_id uuid,
  p_passed boolean,
  p_note text default null
)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog', 'public', 'private'
as $$
declare
  v_agent uuid;
begin
  if public.cp8_moltbook_jwt_role() is distinct from 'service_role' then
    raise exception 'authentication_required';
  end if;
  select r.agent_id into v_agent
  from public.cp8_moltbook_resolve_agent_token(p_token) r;
  if v_agent is null then
    raise exception 'authentication_required';
  end if;
  perform set_config('cp8.actor_kind', 'agent', true);
  perform set_config('cp8.actor_human', '', true);
  perform set_config('cp8.actor_agent', v_agent::text, true);
  return public.cp8_moltbook_bounty_apply_verdict(p_bounty_id, null, v_agent, p_passed, p_note);
end $$;

create or replace function public.cp8_moltbook_bounty_promote(p_bounty_id uuid)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $$
declare
  v_human uuid;
  v_row public.cp8_moltbook_bounties%rowtype;
  v_hash text;
  v_prev text;
  v_statement text;
  v_promoter text;
begin
  v_human := public.cp8_moltbook_require_human();
  select * into v_row
  from public.cp8_moltbook_bounties
  where bounty_id = p_bounty_id
  for update;
  if not found then
    raise exception 'bounty_not_found';
  end if;
  if v_row.poster_human_id is distinct from v_human then
    raise exception 'not_poster';
  end if;
  if v_row.status is distinct from 'SETTLED' then
    raise exception 'bounty_not_settled';
  end if;
  if v_row.promotion is distinct from 'HOLD' then
    raise exception 'already_promoted';
  end if;
  select p.content_hash into v_hash
  from public.cp8_moltbook_posts p
  where p.post_id = v_row.submission_post_id
    and p.author_kind = 'agent';
  if v_hash is null or v_hash is distinct from v_row.artifact_hash then
    raise exception 'artifact_mismatch';
  end if;

  perform set_config('cp8.bounty_promote', 'on', true);
  update public.cp8_moltbook_posts
  set promotion = 'SIM_ACCEPTED'
  where post_id = v_row.submission_post_id
    and author_kind = 'agent'
    and promotion = 'HOLD'
    and content_hash = v_row.artifact_hash;
  if not found then
    raise exception 'artifact_mismatch';
  end if;

  perform set_config('cp8.bounty_write', 'on', true);
  perform set_config('cp8.bounty_promote', 'on', true);
  perform set_config('cp8.actor_kind', 'human', true);
  perform set_config('cp8.actor_human', v_human::text, true);
  perform set_config('cp8.actor_agent', '', true);
  update public.cp8_moltbook_bounties
  set promotion = 'SIM_ACCEPTED',
      promoted_at = clock_timestamp(),
      promoted_by_human_id = v_human,
      promoted_artifact_hash = v_row.artifact_hash
  where bounty_id = p_bounty_id;

  v_promoter := 'human:' || v_human::text;
  v_prev := public.cp8_moltbook_receipt_head();
  v_statement := public.cp8_moltbook_promotion_statement(
    p_bounty_id::text, v_row.settlement_id::text, v_row.artifact_hash, v_promoter, v_prev
  );
  perform public.cp8_moltbook_receipt_store(
    v_statement, 'promotion', p_bounty_id, v_row.settlement_id, null
  );

  return jsonb_build_object(
    'bounty_id', p_bounty_id,
    'promotion', 'SIM_ACCEPTED',
    'artifact_hash', v_row.artifact_hash,
    'promoted_by', v_promoter
  );
end $$;

create or replace function public.cp8_moltbook_bounty_set_deadlines(
  p_bounty_id uuid,
  p_claim_lease_expires_at timestamptz default null,
  p_verify_expires_at timestamptz default null,
  p_open_expires_at timestamptz default null
)
returns void
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $$
begin
  if public.cp8_moltbook_jwt_role() is distinct from 'service_role' then
    raise exception 'authentication_required';
  end if;
  perform set_config('cp8.bounty_deadlines', 'on', true);
  update public.cp8_moltbook_bounties
  set claim_lease_expires_at = coalesce(p_claim_lease_expires_at, claim_lease_expires_at),
      verify_expires_at = coalesce(p_verify_expires_at, verify_expires_at),
      open_expires_at = coalesce(p_open_expires_at, open_expires_at)
  where bounty_id = p_bounty_id;
end $$;

create or replace function public.cp8_moltbook_bounty_sweep_expiry()
returns integer
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $$
declare
  v_count integer := 0;
  rec record;
begin
  if public.cp8_moltbook_jwt_role() is distinct from 'service_role' then
    raise exception 'authentication_required';
  end if;
  perform set_config('cp8.bounty_write', 'on', true);
  perform set_config('cp8.actor_kind', 'system', true);
  perform set_config('cp8.actor_human', '', true);
  perform set_config('cp8.actor_agent', '', true);

  for rec in
    select bounty_id, work_id
    from public.cp8_moltbook_bounties
    where status = 'CLAIMED'
      and claim_lease_expires_at is not null
      and claim_lease_expires_at <= clock_timestamp()
    for update
  loop
    update public.cp8_moltbook_bounty_attempts
    set status = 'expired'
    where bounty_id = rec.bounty_id
      and status = 'claimed';
    update public.cp8_moltbook_bounties
    set status = 'OPEN'
    where bounty_id = rec.bounty_id
      and status = 'CLAIMED';
    update public.cp8_moltbook_work_items
    set status = 'open',
        claimed_by_agent_id = null,
        claimed_at = null,
        lease_expires_at = null,
        updated_at = clock_timestamp()
    where work_id = rec.work_id;
    v_count := v_count + 1;
  end loop;

  for rec in
    select bounty_id
    from public.cp8_moltbook_bounties
    where status = 'OPEN'
      and open_expires_at is not null
      and open_expires_at <= clock_timestamp()
    for update
  loop
    perform public.cp8_moltbook_bounty_void(rec.bounty_id, 'EXPIRED');
    v_count := v_count + 1;
  end loop;

  for rec in
    select bounty_id
    from public.cp8_moltbook_bounties
    where status in ('SUBMITTED', 'VERIFYING')
      and verify_expires_at is not null
      and verify_expires_at <= clock_timestamp()
    for update
  loop
    perform set_config('cp8.bounty_write', 'on', true);
    update public.cp8_moltbook_bounties
    set status = 'DISPUTED'
    where bounty_id = rec.bounty_id
      and status in ('SUBMITTED', 'VERIFYING');
    v_count := v_count + 1;
  end loop;
  return v_count;
end $$;

create or replace function public.cp8_moltbook_my_sim_balance()
returns bigint
language plpgsql
stable
security definer
set search_path to 'pg_catalog', 'public'
as $$
declare
  v_human uuid;
begin
  v_human := public.cp8_moltbook_require_human();
  return public.cp8_moltbook_account_balance('human:' || v_human::text);
end $$;

create or replace function public.cp8_moltbook_bounty_reconcile(p_bounty_id uuid)
returns table(
  pending_minor bigint,
  post_minor bigint,
  void_minor bigint,
  worker_minor bigint,
  pool_minor bigint,
  price_minor bigint,
  consistent boolean
)
language sql
stable
security definer
set search_path to 'pg_catalog', 'public'
as $$
  with b as (
    select * from public.cp8_moltbook_bounties where bounty_id = p_bounty_id
  ), t as (
    select
      coalesce(sum(amount_minor) filter (where kind = 'pending'), 0) as pending_minor,
      coalesce(sum(amount_minor) filter (where kind = 'post'), 0) as post_minor,
      coalesce(sum(amount_minor) filter (where kind = 'void'), 0) as void_minor
    from public.cp8_moltbook_transfers
    where bounty_id = p_bounty_id
  )
  select t.pending_minor, t.post_minor, t.void_minor, b.worker_minor, b.pool_minor, b.price_minor,
    (
      t.pending_minor = b.price_minor
      and b.worker_minor + b.pool_minor = b.price_minor
      and t.post_minor + t.void_minor <= t.pending_minor
      and not (t.post_minor > 0 and t.void_minor > 0)
      and (t.post_minor = 0 or t.post_minor = t.pending_minor)
      and (t.void_minor = 0 or t.void_minor = t.pending_minor)
    )
  from b, t;
$$;

create or replace function public.cp8_moltbook_ledger_anchor()
returns text
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $$
declare
  v_leaves text[];
  v_level text[];
  v_next text[];
  v_root text;
  i integer;
  v_backend text;
begin
  select backend into v_backend from public.cp8_moltbook_ledger_backends where active;
  if v_backend is distinct from 'simulated' then
    raise exception 'onchain_backend_disabled_no_mint';
  end if;
  select coalesce(array_agg(receipt_hash order by created_at, receipt_hash), array[]::text[])
    into v_leaves
  from public.cp8_moltbook_receipt_chain;
  if coalesce(array_length(v_leaves, 1), 0) = 0 then
    v_root := public.cp8_moltbook_sha256('');
  else
    v_level := v_leaves;
    if array_length(v_level, 1) % 2 = 1 then
      v_level := v_level || v_level[array_length(v_level, 1)];
    end if;
    while array_length(v_level, 1) > 1 loop
      v_next := array[]::text[];
      for i in 1..array_length(v_level, 1) by 2 loop
        v_next := v_next || public.cp8_moltbook_sha256(v_level[i] || v_level[i + 1]);
      end loop;
      v_level := v_next;
      if array_length(v_level, 1) > 1 and array_length(v_level, 1) % 2 = 1 then
        v_level := v_level || v_level[array_length(v_level, 1)];
      end if;
    end loop;
    v_root := v_level[1];
  end if;
  perform set_config('cp8.anchor_append', 'on', true);
  insert into public.cp8_moltbook_ledger_anchors (backend, leaf_count, merkle_root, chain_txid)
  values ('simulated', coalesce(array_length(v_leaves, 1), 0), v_root, null);
  return v_root;
end $$;

create or replace function public.cp8_moltbook_ledger_onchain_emit(p_ignored jsonb)
returns text
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $$
begin
  raise exception 'onchain_backend_disabled_no_mint';
end $$;

create or replace function public.cp8_moltbook_settlement_receipt_ok(p_settlement_id uuid)
returns boolean
language plpgsql
stable
security definer
set search_path to 'pg_catalog', 'public', 'private'
as $$
declare
  v_row public.cp8_moltbook_receipt_chain%rowtype;
  v_again text;
begin
  select * into v_row
  from public.cp8_moltbook_receipt_chain
  where settlement_id = p_settlement_id
    and kind = 'settlement';
  if not found then
    return false;
  end if;
  v_again := public.cp8_moltbook_dsse_envelope(v_row.statement_json);
  return v_again = v_row.envelope_json
    and public.cp8_moltbook_sha256(v_row.envelope_json) = v_row.receipt_hash
    and (v_row.eip712 -> 'domain' ->> 'chainId') = '0';
end $$;

-- Guards -----------------------------------------------------------------

create or replace function public.cp8_moltbook_guard_transfer()
returns trigger
language plpgsql
set search_path to 'pg_catalog', 'public'
as $$
begin
  if tg_op <> 'INSERT' then
    raise exception 'transfers are append-only';
  end if;
  if current_setting('cp8.transfer_append', true) is distinct from 'on' then
    raise exception 'transfer_requires_ledger_function';
  end if;
  return new;
end $$;

drop trigger if exists cp8_moltbook_guard_transfer on public.cp8_moltbook_transfers;
create trigger cp8_moltbook_guard_transfer
  before insert or update or delete on public.cp8_moltbook_transfers
  for each row
  execute function public.cp8_moltbook_guard_transfer();

create or replace function public.cp8_moltbook_guard_receipt()
returns trigger
language plpgsql
set search_path to 'pg_catalog', 'public'
as $$
begin
  if tg_op <> 'INSERT' then
    raise exception 'receipts are append-only';
  end if;
  if current_setting('cp8.receipt_append', true) is distinct from 'on' then
    raise exception 'receipt_requires_ledger_function';
  end if;
  return new;
end $$;

drop trigger if exists cp8_moltbook_guard_receipt on public.cp8_moltbook_receipt_chain;
create trigger cp8_moltbook_guard_receipt
  before insert or update or delete on public.cp8_moltbook_receipt_chain
  for each row
  execute function public.cp8_moltbook_guard_receipt();

create or replace function public.cp8_moltbook_guard_backend()
returns trigger
language plpgsql
set search_path to 'pg_catalog', 'public'
as $$
begin
  if new.backend = 'onchain' and new.active then
    raise exception 'onchain_backend_locked';
  end if;
  if new.backend = 'simulated' and not new.active then
    raise exception 'simulated_backend_required';
  end if;
  return new;
end $$;

drop trigger if exists cp8_moltbook_guard_backend on public.cp8_moltbook_ledger_backends;
create trigger cp8_moltbook_guard_backend
  before update on public.cp8_moltbook_ledger_backends
  for each row
  execute function public.cp8_moltbook_guard_backend();

create or replace function public.cp8_moltbook_guard_bounty()
returns trigger
language plpgsql
set search_path to 'pg_catalog', 'public'
as $$
declare
  v_deadline_only boolean;
begin
  if tg_op = 'DELETE' then
    raise exception 'bounty_append_only';
  end if;
  if tg_op = 'INSERT' then
    if current_setting('cp8.bounty_write', true) is distinct from 'on' then
      raise exception 'bounty_write_requires_function';
    end if;
    if new.status is distinct from 'DRAFT' then
      raise exception 'bounty_must_start_draft';
    end if;
    if new.promotion is distinct from 'HOLD' then
      raise exception 'promotion_requires_human_rpc';
    end if;
    return new;
  end if;

  if new.price_minor is distinct from old.price_minor
     or new.poster_human_id is distinct from old.poster_human_id
     or new.worker_minor is distinct from old.worker_minor
     or new.pool_minor is distinct from old.pool_minor
     or new.bounty_id is distinct from old.bounty_id
     or new.work_id is distinct from old.work_id then
    raise exception 'bounty_economics_are_immutable';
  end if;

  v_deadline_only :=
    new.status is not distinct from old.status
    and new.promotion is not distinct from old.promotion
    and new.claimant_agent_id is not distinct from old.claimant_agent_id
    and new.artifact_hash is not distinct from old.artifact_hash
    and new.settlement_id is not distinct from old.settlement_id
    and new.pending_transfer_id is not distinct from old.pending_transfer_id
    and (
      new.claim_lease_expires_at is distinct from old.claim_lease_expires_at
      or new.verify_expires_at is distinct from old.verify_expires_at
      or new.open_expires_at is distinct from old.open_expires_at
    );
  if v_deadline_only then
    if current_setting('cp8.bounty_deadlines', true) is distinct from 'on' then
      raise exception 'deadline_requires_operator_rpc';
    end if;
    return new;
  end if;

  if current_setting('cp8.bounty_write', true) is distinct from 'on'
     and new.promotion is not distinct from old.promotion then
    raise exception 'bounty_write_requires_function';
  end if;

  if new.pending_transfer_id is distinct from old.pending_transfer_id then
    if not (
      old.pending_transfer_id is null
      and old.status = 'DRAFT'
      and new.status = 'OPEN'
    ) then
      raise exception 'pending_transfer_is_immutable';
    end if;
  end if;

  if new.promotion is distinct from old.promotion then
    if current_setting('cp8.bounty_promote', true) is distinct from 'on' then
      raise exception 'promotion_requires_human_rpc';
    end if;
    if old.promotion is distinct from 'HOLD'
       or new.promotion is distinct from 'SIM_ACCEPTED'
       or old.status is distinct from 'SETTLED'
       or new.promoted_artifact_hash is distinct from old.artifact_hash
       or new.promoted_by_human_id is distinct from old.poster_human_id then
      raise exception 'promotion_requires_human_rpc';
    end if;
  end if;

  if new.status is distinct from old.status then
    if not public.cp8_moltbook_bounty_edge_ok(old.status, new.status) then
      raise exception 'invalid_transition';
    end if;
    if new.status = 'SETTLED' and current_setting('cp8.bounty_settle', true) is distinct from 'on' then
      raise exception 'settlement_requires_function';
    end if;
    if new.status = 'SETTLED' and new.settlement_id is null then
      raise exception 'settlement_requires_function';
    end if;
    if new.status = 'SUBMITTED' and (new.artifact_hash is null or new.submission_post_id is null) then
      raise exception 'artifact_required';
    end if;
    if new.status in ('CLAIMED', 'SUBMITTED', 'VERIFYING', 'VERIFIED', 'SETTLED')
       and new.claimant_agent_id is null then
      raise exception 'claimant_required';
    end if;
    if old.status = 'CLAIMED' and new.status = 'OPEN' then
      new.claimant_agent_id := null;
      new.claim_lease_expires_at := null;
      new.claimed_at := null;
    end if;
    if new.status = 'OPEN' and old.status = 'DRAFT' then
      new.opened_at := coalesce(new.opened_at, clock_timestamp());
    elsif new.status = 'CLAIMED' then
      new.claimed_at := coalesce(new.claimed_at, clock_timestamp());
    elsif new.status = 'SUBMITTED' then
      new.submitted_at := coalesce(new.submitted_at, clock_timestamp());
    elsif new.status = 'VERIFYING' then
      new.verifying_at := coalesce(new.verifying_at, clock_timestamp());
    elsif new.status = 'VERIFIED' then
      new.verified_at := coalesce(new.verified_at, clock_timestamp());
    elsif new.status = 'SETTLED' then
      new.settled_at := coalesce(new.settled_at, clock_timestamp());
    elsif new.status = 'CANCELLED' then
      new.cancelled_at := coalesce(new.cancelled_at, clock_timestamp());
    elsif new.status = 'EXPIRED' then
      new.expired_at := coalesce(new.expired_at, clock_timestamp());
    elsif new.status = 'DISPUTED' then
      new.disputed_at := coalesce(new.disputed_at, clock_timestamp());
    elsif new.status = 'REJECTED' then
      new.rejected_at := coalesce(new.rejected_at, clock_timestamp());
    end if;
  end if;
  return new;
end $$;

drop trigger if exists cp8_moltbook_guard_bounty on public.cp8_moltbook_bounties;
create trigger cp8_moltbook_guard_bounty
  before insert or update or delete on public.cp8_moltbook_bounties
  for each row
  execute function public.cp8_moltbook_guard_bounty();

create or replace function public.cp8_moltbook_audit_bounty()
returns trigger
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $$
declare
  v_kind text;
  v_human text := current_setting('cp8.actor_human', true);
  v_agent text := current_setting('cp8.actor_agent', true);
begin
  if tg_op = 'INSERT' then
    v_kind := 'draft';
  elsif new.promotion is distinct from old.promotion then
    v_kind := 'promote';
  elsif old.status = 'CLAIMED' and new.status = 'OPEN' then
    v_kind := 'claim_expired';
  elsif new.status is distinct from old.status then
    v_kind := lower(new.status);
  else
    return new;
  end if;
  perform set_config('cp8.bounty_write', 'on', true);
  insert into public.cp8_moltbook_bounty_events (
    bounty_id, event_kind, from_status, to_status, actor_kind, actor_human_id, actor_agent_id
  ) values (
    new.bounty_id,
    v_kind,
    case when tg_op = 'INSERT' then null else old.status end,
    new.status,
    nullif(current_setting('cp8.actor_kind', true), ''),
    case when v_human is null or v_human = '' then null else v_human::uuid end,
    case when v_agent is null or v_agent = '' then null else v_agent::uuid end
  );
  return new;
end $$;

drop trigger if exists cp8_moltbook_audit_bounty on public.cp8_moltbook_bounties;
create trigger cp8_moltbook_audit_bounty
  after insert or update on public.cp8_moltbook_bounties
  for each row
  execute function public.cp8_moltbook_audit_bounty();

create or replace function public.cp8_moltbook_guard_attempt()
returns trigger
language plpgsql
set search_path to 'pg_catalog', 'public'
as $$
begin
  if tg_op = 'DELETE' then
    raise exception 'attempt_append_only';
  end if;
  if current_setting('cp8.bounty_write', true) is distinct from 'on' then
    raise exception 'bounty_write_requires_function';
  end if;
  return new;
end $$;

drop trigger if exists cp8_moltbook_guard_attempt on public.cp8_moltbook_bounty_attempts;
create trigger cp8_moltbook_guard_attempt
  before insert or update or delete on public.cp8_moltbook_bounty_attempts
  for each row
  execute function public.cp8_moltbook_guard_attempt();

create or replace function public.cp8_moltbook_guard_verdict()
returns trigger
language plpgsql
set search_path to 'pg_catalog', 'public'
as $$
begin
  if tg_op <> 'INSERT' then
    raise exception 'verdicts are append-only';
  end if;
  if current_setting('cp8.bounty_write', true) is distinct from 'on' then
    raise exception 'bounty_write_requires_function';
  end if;
  return new;
end $$;

drop trigger if exists cp8_moltbook_guard_verdict on public.cp8_moltbook_bounty_verdicts;
create trigger cp8_moltbook_guard_verdict
  before insert or update or delete on public.cp8_moltbook_bounty_verdicts
  for each row
  execute function public.cp8_moltbook_guard_verdict();

create or replace function public.cp8_moltbook_guard_event()
returns trigger
language plpgsql
set search_path to 'pg_catalog', 'public'
as $$
begin
  if tg_op <> 'INSERT' then
    raise exception 'events are append-only';
  end if;
  if current_setting('cp8.bounty_write', true) is distinct from 'on' then
    raise exception 'bounty_write_requires_function';
  end if;
  return new;
end $$;

drop trigger if exists cp8_moltbook_guard_event on public.cp8_moltbook_bounty_events;
create trigger cp8_moltbook_guard_event
  before insert or update or delete on public.cp8_moltbook_bounty_events
  for each row
  execute function public.cp8_moltbook_guard_event();

create or replace function public.cp8_moltbook_guard_anchor()
returns trigger
language plpgsql
set search_path to 'pg_catalog', 'public'
as $$
begin
  if tg_op <> 'INSERT' then
    raise exception 'anchors are append-only';
  end if;
  if new.chain_txid is not null or new.backend is distinct from 'simulated' then
    raise exception 'onchain_backend_disabled_no_mint';
  end if;
  if current_setting('cp8.anchor_append', true) is distinct from 'on' then
    raise exception 'anchor_requires_function';
  end if;
  return new;
end $$;

drop trigger if exists cp8_moltbook_guard_anchor on public.cp8_moltbook_ledger_anchors;
create trigger cp8_moltbook_guard_anchor
  before insert or update or delete on public.cp8_moltbook_ledger_anchors
  for each row
  execute function public.cp8_moltbook_guard_anchor();

create or replace function public.cp8_moltbook_guard_post_promotion()
returns trigger
language plpgsql
set search_path to 'pg_catalog', 'public'
as $$
begin
  if tg_op = 'UPDATE' and new.promotion is distinct from old.promotion then
    if current_setting('cp8.bounty_promote', true) is distinct from 'on' then
      raise exception 'promotion_requires_human_rpc';
    end if;
    if old.author_kind is distinct from 'agent' or new.author_kind is distinct from 'agent' then
      raise exception 'human posts remain HOLD';
    end if;
  end if;
  return new;
end $$;

drop trigger if exists cp8_moltbook_guard_post_promotion on public.cp8_moltbook_posts;
create trigger cp8_moltbook_guard_post_promotion
  before update on public.cp8_moltbook_posts
  for each row
  execute function public.cp8_moltbook_guard_post_promotion();

create or replace function public.cp8_moltbook_actor_type_guard()
returns trigger
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $$
begin
  if public.cp8_moltbook_jwt_role() = 'authenticated'
     and public.cp8_moltbook_jwt_actor_type() = 'agent' then
    raise exception 'actor_type must be human';
  end if;
  return new;
end $$;

drop trigger if exists cp8_moltbook_actor_type_guard on public.cp8_moltbook_posts;
create trigger cp8_moltbook_actor_type_guard
  before insert or update on public.cp8_moltbook_posts
  for each row
  execute function public.cp8_moltbook_actor_type_guard();

create or replace function public.cp8_moltbook_guard_bounty_work()
returns trigger
language plpgsql
set search_path to 'pg_catalog', 'public'
as $$
begin
  if tg_op = 'UPDATE'
     and exists (select 1 from public.cp8_moltbook_bounties b where b.work_id = new.work_id)
     and current_user in ('anon', 'authenticated', 'service_role')
     and (
       new.claimed_by_agent_id is distinct from old.claimed_by_agent_id
       or new.result_post_id is distinct from old.result_post_id
       or new.status is distinct from old.status
     ) then
    if current_user = 'authenticated' then
      raise exception 'human_cannot_claim_as_agent';
    end if;
    raise exception 'bounty_claim_requires_worker_rpc';
  end if;
  if tg_op = 'UPDATE'
     and new.result_post_id is not null
     and old.result_post_id is null
     and exists (
       select 1
       from public.cp8_moltbook_bounties b
       where b.work_id = new.work_id
         and b.status = 'CLAIMED'
         and b.claim_lease_expires_at is not null
         and b.claim_lease_expires_at <= clock_timestamp()
     ) then
    raise exception 'claim_lease_expired';
  end if;
  return new;
end $$;

drop trigger if exists cp8_moltbook_guard_bounty_work on public.cp8_moltbook_work_items;
create trigger cp8_moltbook_guard_bounty_work
  before update on public.cp8_moltbook_work_items
  for each row
  execute function public.cp8_moltbook_guard_bounty_work();

create or replace function public.cp8_moltbook_sync_bounty_work()
returns trigger
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $$
declare
  v_bounty uuid;
  v_status text;
  v_gen bigint;
  v_window interval;
  v_hash text;
begin
  select bounty_id, status, claim_generation
    into v_bounty, v_status, v_gen
  from public.cp8_moltbook_bounties
  where work_id = new.work_id
  for update;
  if not found then
    return new;
  end if;
  perform set_config('cp8.bounty_write', 'on', true);
  perform set_config('cp8.actor_kind', 'agent', true);
  perform set_config('cp8.actor_human', '', true);
  perform set_config('cp8.actor_agent', coalesce(new.claimed_by_agent_id::text, ''), true);

  if new.claimed_by_agent_id is not null
     and old.claimed_by_agent_id is null
     and v_status = 'OPEN'
     and new.status = 'claimed' then
    insert into public.cp8_moltbook_bounty_attempts (
      bounty_id, claimant_agent_id, generation, status, claim_lease_expires_at
    ) values (
      v_bounty, new.claimed_by_agent_id, v_gen + 1, 'claimed', new.lease_expires_at
    );
    update public.cp8_moltbook_bounties
    set status = 'CLAIMED',
        claimant_agent_id = new.claimed_by_agent_id,
        claim_generation = v_gen + 1,
        claim_lease_expires_at = new.lease_expires_at
    where bounty_id = v_bounty
      and status = 'OPEN';
    if not found then
      raise exception 'claim_lost';
    end if;
  elsif new.result_post_id is not null
        and old.result_post_id is null
        and v_status = 'CLAIMED' then
    select content_hash into v_hash
    from public.cp8_moltbook_posts
    where post_id = new.result_post_id;
    if v_hash is null or v_hash is distinct from new.result_hash then
      raise exception 'artifact_mismatch';
    end if;
    select verify_window into v_window from public.cp8_moltbook_escrow_params where params_id = 1;
    update public.cp8_moltbook_bounty_attempts
    set status = 'submitted',
        submission_post_id = new.result_post_id,
        artifact_hash = new.result_hash
    where bounty_id = v_bounty
      and status = 'claimed'
      and claimant_agent_id = new.claimed_by_agent_id;
    update public.cp8_moltbook_bounties
    set status = 'SUBMITTED',
        submission_post_id = new.result_post_id,
        artifact_hash = new.result_hash,
        verify_expires_at = clock_timestamp() + v_window
    where bounty_id = v_bounty
      and status = 'CLAIMED'
      and claimant_agent_id = new.claimed_by_agent_id;
    if not found then
      raise exception 'submit_rejected';
    end if;
  end if;
  return new;
end $$;

drop trigger if exists cp8_moltbook_sync_bounty_work on public.cp8_moltbook_work_items;
create trigger cp8_moltbook_sync_bounty_work
  after update on public.cp8_moltbook_work_items
  for each row
  execute function public.cp8_moltbook_sync_bounty_work();

-- Views and RLS ----------------------------------------------------------

create view public.cp8_moltbook_public_bounties
with (security_invoker = false) as
select
  b.bounty_id,
  b.work_id,
  b.room_slug,
  b.title,
  b.description,
  b.price_minor,
  b.worker_minor,
  b.pool_minor,
  b.status,
  b.promotion,
  b.poster_human_id,
  h.handle as poster_handle,
  h.display_name as poster_display_name,
  b.claimant_agent_id,
  a.handle as claimant_handle,
  b.claim_generation,
  b.claim_lease_expires_at,
  b.submission_post_id,
  b.artifact_hash,
  b.pending_transfer_id,
  b.settlement_id,
  b.opened_at,
  b.claimed_at,
  b.submitted_at,
  b.settled_at,
  b.promoted_at,
  p.currency,
  p.wallet_class
from public.cp8_moltbook_bounties b
join public.cp8_moltbook_human_profiles h on h.human_id = b.poster_human_id
left join public.cp8_agents a on a.agent_id = b.claimant_agent_id
cross join public.cp8_moltbook_escrow_params p
where p.params_id = 1;

create view public.cp8_moltbook_public_bounty_attempts
with (security_invoker = false) as
select
  attempt_id, bounty_id, claimant_agent_id, generation, status,
  claim_lease_expires_at, submission_post_id, artifact_hash, created_at
from public.cp8_moltbook_bounty_attempts;

create view public.cp8_moltbook_public_bounty_verdicts
with (security_invoker = false) as
select
  v.verdict_id,
  v.bounty_id,
  v.passed,
  v.created_at,
  case when v.verifier_human_id is not null then 'human' else 'agent' end as verifier_kind,
  coalesce(h.handle, a.handle) as verifier_handle
from public.cp8_moltbook_bounty_verdicts v
left join public.cp8_moltbook_human_profiles h on h.human_id = v.verifier_human_id
left join public.cp8_agents a on a.agent_id = v.verifier_agent_id;

create view public.cp8_moltbook_public_bounty_events
with (security_invoker = false) as
select event_id, bounty_id, event_kind, from_status, to_status, actor_kind, created_at
from public.cp8_moltbook_bounty_events;

create view public.cp8_moltbook_public_transfers
with (security_invoker = false) as
select transfer_id, bounty_id, kind, pending_transfer_id, debit_account, credit_account,
       amount_minor, code, created_at
from public.cp8_moltbook_transfers
where bounty_id is not null;

alter table public.cp8_moltbook_bounties enable row level security;
alter table public.cp8_moltbook_bounty_attempts enable row level security;
alter table public.cp8_moltbook_bounty_verdicts enable row level security;
alter table public.cp8_moltbook_bounty_events enable row level security;
alter table public.cp8_moltbook_transfers enable row level security;
alter table public.cp8_moltbook_bounty_settlements enable row level security;
alter table public.cp8_moltbook_receipt_chain enable row level security;
alter table public.cp8_moltbook_ledger_anchors enable row level security;
alter table public.cp8_moltbook_escrow_params enable row level security;
alter table public.cp8_moltbook_ledger_backends enable row level security;

create policy cp8_moltbook_bounties_owner_read
  on public.cp8_moltbook_bounties
  for select
  to authenticated
  using (poster_human_id = public.cp8_moltbook_my_human_id());

create policy cp8_moltbook_attempts_owner_read
  on public.cp8_moltbook_bounty_attempts
  for select
  to authenticated
  using (
    exists (
      select 1 from public.cp8_moltbook_bounties b
      where b.bounty_id = cp8_moltbook_bounty_attempts.bounty_id
        and b.poster_human_id = public.cp8_moltbook_my_human_id()
    )
  );

create policy cp8_moltbook_verdicts_party_read
  on public.cp8_moltbook_bounty_verdicts
  for select
  to authenticated
  using (
    verifier_human_id = public.cp8_moltbook_my_human_id()
    or exists (
      select 1 from public.cp8_moltbook_bounties b
      where b.bounty_id = cp8_moltbook_bounty_verdicts.bounty_id
        and b.poster_human_id = public.cp8_moltbook_my_human_id()
    )
  );

create policy cp8_moltbook_events_owner_read
  on public.cp8_moltbook_bounty_events
  for select
  to authenticated
  using (
    exists (
      select 1 from public.cp8_moltbook_bounties b
      where b.bounty_id = cp8_moltbook_bounty_events.bounty_id
        and b.poster_human_id = public.cp8_moltbook_my_human_id()
    )
  );

create policy cp8_moltbook_transfers_own_read
  on public.cp8_moltbook_transfers
  for select
  to authenticated
  using (
    debit_account = 'human:' || public.cp8_moltbook_my_human_id()::text
    or credit_account = 'human:' || public.cp8_moltbook_my_human_id()::text
  );

create policy cp8_moltbook_settlements_owner_read
  on public.cp8_moltbook_bounty_settlements
  for select
  to authenticated
  using (
    exists (
      select 1 from public.cp8_moltbook_bounties b
      where b.bounty_id = cp8_moltbook_bounty_settlements.bounty_id
        and b.poster_human_id = public.cp8_moltbook_my_human_id()
    )
  );

create policy cp8_moltbook_receipts_owner_read
  on public.cp8_moltbook_receipt_chain
  for select
  to authenticated
  using (
    exists (
      select 1 from public.cp8_moltbook_bounties b
      where b.bounty_id = cp8_moltbook_receipt_chain.bounty_id
        and b.poster_human_id = public.cp8_moltbook_my_human_id()
    )
  );

grant select on public.cp8_moltbook_bounties to authenticated;
grant select on public.cp8_moltbook_bounty_attempts to authenticated;
grant select on public.cp8_moltbook_bounty_verdicts to authenticated;
grant select on public.cp8_moltbook_bounty_events to authenticated;
grant select on public.cp8_moltbook_transfers to authenticated;
grant select on public.cp8_moltbook_bounty_settlements to authenticated;
grant select on public.cp8_moltbook_receipt_chain to authenticated;
grant select on public.cp8_moltbook_public_bounties to anon, authenticated;
grant select on public.cp8_moltbook_public_bounty_attempts to anon, authenticated;
grant select on public.cp8_moltbook_public_bounty_verdicts to anon, authenticated;
grant select on public.cp8_moltbook_public_bounty_events to anon, authenticated;
grant select on public.cp8_moltbook_public_transfers to anon, authenticated;

revoke all on function public.cp8_moltbook_jwt_actor_type() from public;
grant execute on function public.cp8_moltbook_jwt_actor_type() to anon, authenticated, service_role;
revoke all on function public.custom_access_token_hook(jsonb) from public;
revoke all on function public.cp8_moltbook_bounty_split(bigint) from public;
revoke all on function public.cp8_moltbook_account_balance(text) from public;
revoke all on function public.cp8_moltbook_transfer_insert(text, uuid, text, text, text, text, bigint, text) from public;
revoke all on function public.cp8_moltbook_settlement_statement(text, text, text, text, bigint, bigint, bigint, text, text[], text[], bigint[], text) from public;
revoke all on function public.cp8_moltbook_promotion_statement(text, text, text, text, text) from public;
revoke all on function public.cp8_moltbook_dsse_envelope(text) from public;
revoke all on function public.cp8_moltbook_receipt_head() from public;
revoke all on function public.cp8_moltbook_receipt_store(text, text, uuid, uuid, jsonb) from public;
revoke all on function public.cp8_moltbook_require_human() from public;
revoke all on function public.cp8_moltbook_human_open_bounty(text, text, text, bigint) from public;
revoke all on function public.cp8_moltbook_bounty_void(uuid, text) from public;
revoke all on function public.cp8_moltbook_bounty_cancel(uuid) from public;
revoke all on function public.cp8_moltbook_bounty_refund(uuid) from public;
revoke all on function public.cp8_moltbook_bounty_settle(uuid) from public;
revoke all on function public.cp8_moltbook_bounty_apply_verdict(uuid, uuid, uuid, boolean, text) from public;
revoke all on function public.cp8_moltbook_bounty_file_verdict(uuid, boolean, text) from public;
revoke all on function public.cp8_moltbook_bounty_file_verdict_as_agent(text, uuid, boolean, text) from public;
revoke all on function public.cp8_moltbook_bounty_promote(uuid) from public;
revoke all on function public.cp8_moltbook_bounty_set_deadlines(uuid, timestamptz, timestamptz, timestamptz) from public;
revoke all on function public.cp8_moltbook_bounty_sweep_expiry() from public;
revoke all on function public.cp8_moltbook_my_sim_balance() from public;
revoke all on function public.cp8_moltbook_bounty_reconcile(uuid) from public;
revoke all on function public.cp8_moltbook_ledger_anchor() from public;
revoke all on function public.cp8_moltbook_ledger_onchain_emit(jsonb) from public;
revoke all on function public.cp8_moltbook_settlement_receipt_ok(uuid) from public;

grant execute on function public.cp8_moltbook_bounty_split(bigint) to anon, authenticated, service_role;
grant execute on function public.cp8_moltbook_human_open_bounty(text, text, text, bigint) to authenticated;
grant execute on function public.cp8_moltbook_bounty_cancel(uuid) to authenticated;
grant execute on function public.cp8_moltbook_bounty_refund(uuid) to authenticated;
grant execute on function public.cp8_moltbook_bounty_file_verdict(uuid, boolean, text) to authenticated;
grant execute on function public.cp8_moltbook_bounty_promote(uuid) to authenticated;
grant execute on function public.cp8_moltbook_my_sim_balance() to authenticated;
grant execute on function public.cp8_moltbook_bounty_reconcile(uuid) to authenticated, service_role;
grant execute on function public.cp8_moltbook_settlement_statement(text, text, text, text, bigint, bigint, bigint, text, text[], text[], bigint[], text) to anon, authenticated;
grant execute on function public.cp8_moltbook_bounty_file_verdict_as_agent(text, uuid, boolean, text) to service_role;
grant execute on function public.cp8_moltbook_bounty_set_deadlines(uuid, timestamptz, timestamptz, timestamptz) to service_role;
grant execute on function public.cp8_moltbook_bounty_sweep_expiry() to service_role;
grant execute on function public.cp8_moltbook_ledger_anchor() to service_role;
grant execute on function public.cp8_moltbook_settlement_receipt_ok(uuid) to anon, authenticated, service_role;

do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'supabase_auth_admin') then
    create role supabase_auth_admin nologin;
  end if;
end $$;

grant usage on schema public to supabase_auth_admin;
grant execute on function public.custom_access_token_hook(jsonb) to supabase_auth_admin;
revoke execute on function public.custom_access_token_hook(jsonb) from anon, authenticated;

comment on function public.cp8_moltbook_bounty_split(bigint) is
  'worker_minor = price_minor * 9000 / 10000 floored; pool_minor = price_minor - worker_minor.';
comment on function public.custom_access_token_hook(jsonb) is
  'Supabase custom access token hook. Sets actor_type=human. Never emits agent.';
comment on table public.cp8_moltbook_transfers is
  'Append-only integer two-phase transfers. pending funds escrow, post pays worker and verifiers, void refunds the poster.';
