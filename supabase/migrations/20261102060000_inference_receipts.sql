-- Public inference receipts for the bounded Groq test.
--
-- These rows are the GPU-mesh canon (sorted JSON, sha256, Ed25519 over the
-- EIP-712-style digest). They are not bounty settlements and they do not
-- enter cp8_moltbook_receipt_chain, which requires a bounty id and the
-- simulated HMAC envelope. An EIP-712 settlement attestation can wrap
-- typed_json once the on-chain ledger backend is enabled.
--
-- The default amount is 0. The row is simulated until that backend is enabled.
-- No contract is created here.

create table public.cp8_inference_signer (
  id integer primary key check (id = 1),
  public_key_hex text not null check (public_key_hex ~ '^[0-9a-f]{64}$')
);

insert into public.cp8_inference_signer (id, public_key_hex)
values (1, 'c30d2e6d53443bede57190391a61738dba6fc491c098cc1ac38e07d17eade905');

create table public.cp8_inference_receipts (
  receipt_id uuid primary key default gen_random_uuid(),
  seq bigint not null unique,
  ts bigint not null,
  actor text not null,
  kind text not null,
  payload text not null,
  prev_hash text not null,
  hash text not null unique check (hash ~ '^[0-9a-f]{64}$'),
  canon text not null default 'v1',
  body_json text not null,
  signature text not null check (signature ~ '^[0-9a-f]{128}$'),
  signer text not null check (signer ~ '^[0-9a-f]{64}$'),
  typed_json jsonb not null,
  amount bigint not null check (amount >= 0),
  verification jsonb not null,
  output_text text not null default '',
  output_sha256 text not null check (output_sha256 ~ '^[0-9a-f]{64}$'),
  request_id text,
  created_at timestamptz not null default clock_timestamp()
);

create table public.cp8_inference_rate (
  bucket text primary key,
  window_start timestamptz not null,
  hits integer not null check (hits >= 0)
);

alter table public.cp8_inference_signer enable row level security;
alter table public.cp8_inference_receipts enable row level security;
alter table public.cp8_inference_rate enable row level security;

revoke all on public.cp8_inference_signer from public, anon, authenticated;
revoke all on public.cp8_inference_rate from public, anon, authenticated;
revoke all on public.cp8_inference_receipts from public, anon, authenticated;
grant select on public.cp8_inference_receipts to anon, authenticated, service_role;

create policy cp8_inference_receipts_public_read
  on public.cp8_inference_receipts
  for select
  to anon, authenticated
  using (true);

create or replace function public.cp8_inference_rate_allow(
  p_bucket text,
  p_limit integer,
  p_window_seconds integer
) returns boolean
language plpgsql
security definer
set search_path to pg_catalog, public
as $$
declare
  v_start timestamptz;
  v_hits integer;
begin
  if p_bucket is null or length(p_bucket) < 1 or length(p_bucket) > 200 then
    return false;
  end if;
  if p_limit is null or p_limit < 1 or p_window_seconds is null or p_window_seconds < 1 then
    return false;
  end if;
  perform pg_advisory_xact_lock(872344, hashtext(p_bucket));
  select window_start, hits into v_start, v_hits
  from public.cp8_inference_rate
  where bucket = p_bucket
  for update;
  if v_start is null or v_start < clock_timestamp() - make_interval(secs => p_window_seconds) then
    insert into public.cp8_inference_rate (bucket, window_start, hits)
    values (p_bucket, clock_timestamp(), 1)
    on conflict (bucket) do update
      set window_start = excluded.window_start,
          hits = 1;
    return true;
  end if;
  if v_hits >= p_limit then
    return false;
  end if;
  update public.cp8_inference_rate
    set hits = hits + 1
    where bucket = p_bucket;
  return true;
end $$;

create or replace function public.cp8_inference_receipt_append(p_row jsonb)
returns uuid
language plpgsql
security definer
set search_path to pg_catalog, public
as $$
declare
  v_prev text;
  v_seq bigint;
  v_hash text;
  v_body text;
  v_signer text;
  v_expected text;
  v_tip_hash text;
  v_tip_seq bigint;
  v_id uuid;
  v_amount bigint;
  v_signature text;
begin
  if p_row is null or jsonb_typeof(p_row) <> 'object' then
    raise exception 'receipt_incomplete';
  end if;
  perform pg_advisory_xact_lock(872343);
  v_body := p_row ->> 'body_json';
  v_hash := p_row ->> 'hash';
  v_prev := p_row ->> 'prev_hash';
  v_seq := (p_row ->> 'seq')::bigint;
  v_signer := p_row ->> 'signer';
  v_amount := (p_row ->> 'amount')::bigint;
  v_signature := p_row ->> 'signature';
  if v_body is null or v_hash is null or v_signer is null or v_seq is null or v_prev is null or v_signature is null then
    raise exception 'receipt_incomplete';
  end if;
  if v_amount is null or v_amount < 0 then
    raise exception 'amount_not_integer';
  end if;
  if encode(extensions.digest(convert_to(v_body, 'UTF8'), 'sha256'), 'hex') is distinct from v_hash then
    raise exception 'receipt_hash_mismatch';
  end if;
  select public_key_hex into v_expected from public.cp8_inference_signer where id = 1;
  if v_signer is distinct from v_expected then
    raise exception 'signer_not_published';
  end if;
  select hash, seq into v_tip_hash, v_tip_seq
  from public.cp8_inference_receipts
  order by seq desc
  limit 1;
  if v_tip_seq is null then
    if v_seq <> 1 or v_prev <> repeat('0', 64) then
      raise exception 'receipt_chain_fork';
    end if;
  elsif v_prev is distinct from v_tip_hash or v_seq <> v_tip_seq + 1 then
    raise exception 'receipt_chain_fork';
  end if;
  insert into public.cp8_inference_receipts (
    seq, ts, actor, kind, payload, prev_hash, hash, canon, body_json,
    signature, signer, typed_json, amount, verification, output_text,
    output_sha256, request_id
  ) values (
    v_seq,
    (p_row ->> 'ts')::bigint,
    p_row ->> 'actor',
    p_row ->> 'kind',
    p_row ->> 'payload',
    v_prev,
    v_hash,
    coalesce(p_row ->> 'canon', 'v1'),
    v_body,
    v_signature,
    v_signer,
    coalesce(p_row -> 'typed_json', p_row -> 'typed_data'),
    v_amount,
    coalesce(p_row -> 'verification', '{}'::jsonb),
    coalesce(p_row ->> 'output_text', ''),
    p_row ->> 'output_sha256',
    nullif(p_row ->> 'request_id', '')
  )
  returning receipt_id into v_id;
  return v_id;
end $$;

revoke all on function public.cp8_inference_rate_allow(text, integer, integer) from public, anon, authenticated;
revoke all on function public.cp8_inference_receipt_append(jsonb) from public, anon, authenticated;
grant execute on function public.cp8_inference_rate_allow(text, integer, integer) to service_role;
grant execute on function public.cp8_inference_receipt_append(jsonb) to service_role;

comment on table public.cp8_inference_receipts is
  'Signed Groq/mesh inference receipts. Simulated until the on-chain ledger backend is enabled. No contract and no mint in this table.';
