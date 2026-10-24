-- Proof-of-Work Commons hardening.
-- Apply after 20261024160000_moltbook_bounty_escrow.sql.
-- Not applied on project ecenvlwyenpakrxfuqup. Ledger stays HHC-SIM.
-- No chain, no contract, no mint.
--
-- New columns on posts, receipts, and the receipt chain use ADD COLUMN ...
-- DEFAULT. This file does not UPDATE those append-only tables.
--
-- Gates added here:
--   9  verifiers must be N distinct unrevoked operators
--   10 Ed25519 DSSE attribution; HMAC stays labeled SIMULATED
--   11 claim_generation + lease_token fence on submit, heartbeat, settle
--   12 job manifest echo, TOPLOC tier is a stub
--   13 exactly-once settlement legs and idempotency keys

create schema if not exists extensions;
grant usage on schema extensions to public;

do $cp8_pgcrypto_compat$
begin
  if to_regprocedure('extensions.gen_random_bytes(integer)') is null
     and to_regprocedure('public.gen_random_bytes(integer)') is not null then
    execute $fn$
      create function extensions.gen_random_bytes(n integer)
      returns bytea language sql immutable
      as $body$ select public.gen_random_bytes(n) $body$
    $fn$;
  end if;
  if to_regprocedure('extensions.hmac(bytea,bytea,text)') is null
     and to_regprocedure('public.hmac(bytea,bytea,text)') is not null then
    execute $fn$
      create function extensions.hmac(data bytea, key bytea, type text)
      returns bytea language sql immutable
      as $body$ select public.hmac(data, key, type) $body$
    $fn$;
  end if;
  if to_regprocedure('extensions.digest(bytea,text)') is null
     and to_regprocedure('public.digest(bytea,text)') is not null then
    execute $fn$
      create function extensions.digest(data bytea, type text)
      returns bytea language sql immutable
      as $body$ select public.digest(data, type) $body$
    $fn$;
  end if;
  if to_regprocedure('extensions.digest(text,text)') is null
     and to_regprocedure('public.digest(text,text)') is not null then
    execute $fn$
      create function extensions.digest(data text, type text)
      returns bytea language sql immutable
      as $body$ select public.digest(data, type) $body$
    $fn$;
  end if;
end
$cp8_pgcrypto_compat$;

-- Ed25519 (RFC 8032). Numeric division rounds, so halving uses div().
-- The migration self-check below pins the RFC empty-message vector.

create or replace function public.cp8_moltbook_ed_norm(n numeric, modulus numeric)
returns numeric
language sql
immutable
set search_path to 'pg_catalog', 'public'
as $$
  select case
    when mod(n, modulus) < 0 then mod(n, modulus) + modulus
    else mod(n, modulus)
  end
$$;

create or replace function public.cp8_moltbook_ed_le_num(b bytea)
returns numeric
language plpgsql
immutable
set search_path to 'pg_catalog', 'public'
as $$
declare
  i int;
  n numeric := 0;
  base numeric := 1;
begin
  for i in 0..octet_length(b) - 1 loop
    n := n + get_byte(b, i) * base;
    base := base * 256;
  end loop;
  return n;
end $$;

create or replace function public.cp8_moltbook_ed_num_le(n numeric, len int)
returns bytea
language plpgsql
immutable
set search_path to 'pg_catalog', 'public'
as $$
declare
  i int;
  out bytea := decode(repeat('00', len), 'hex');
  byte int;
begin
  for i in 0..len - 1 loop
    byte := mod(n, 256)::int;
    if byte < 0 then
      byte := byte + 256;
    end if;
    out := set_byte(out, i, byte);
    n := div(n, 256);
  end loop;
  return out;
end $$;

create or replace function public.cp8_moltbook_ed_add(
  x1 numeric, y1 numeric, z1 numeric, t1 numeric,
  x2 numeric, y2 numeric, z2 numeric, t2 numeric,
  out x3 numeric, out y3 numeric, out z3 numeric, out t3 numeric
)
language plpgsql
immutable
set search_path to 'pg_catalog', 'public'
as $$
declare
  modulus numeric := 57896044618658097711785492504343953926634992332820282019728792003956564819949;
  dconst numeric := 37095705934669439343138083508754565189542113879843219016388785533085940283555;
  a numeric; b numeric; c numeric; dd numeric; e numeric; f numeric; g numeric; h numeric;
begin
  a := public.cp8_moltbook_ed_norm((y1 - x1) * (y2 - x2), modulus);
  b := public.cp8_moltbook_ed_norm((y1 + x1) * (y2 + x2), modulus);
  c := public.cp8_moltbook_ed_norm((2 * dconst) * t1 * t2, modulus);
  dd := public.cp8_moltbook_ed_norm(2 * z1 * z2, modulus);
  e := public.cp8_moltbook_ed_norm(b - a, modulus);
  f := public.cp8_moltbook_ed_norm(dd - c, modulus);
  g := public.cp8_moltbook_ed_norm(dd + c, modulus);
  h := public.cp8_moltbook_ed_norm(b + a, modulus);
  x3 := public.cp8_moltbook_ed_norm(e * f, modulus);
  y3 := public.cp8_moltbook_ed_norm(g * h, modulus);
  z3 := public.cp8_moltbook_ed_norm(f * g, modulus);
  t3 := public.cp8_moltbook_ed_norm(e * h, modulus);
end $$;

create or replace function public.cp8_moltbook_ed_scalarmult(
  bx numeric, byy numeric, bz numeric, bt numeric, e numeric,
  out x3 numeric, out y3 numeric, out z3 numeric, out t3 numeric
)
language plpgsql
immutable
set search_path to 'pg_catalog', 'public'
as $$
declare
  qx numeric := 0;
  qy numeric := 1;
  qz numeric := 1;
  qt numeric := 0;
  px numeric := bx;
  py numeric := byy;
  pz numeric := bz;
  pt numeric := bt;
begin
  while e > 0 loop
    if mod(e, 2) = 1 then
      select a.x3, a.y3, a.z3, a.t3 into qx, qy, qz, qt
      from public.cp8_moltbook_ed_add(qx, qy, qz, qt, px, py, pz, pt) a;
    end if;
    select a.x3, a.y3, a.z3, a.t3 into px, py, pz, pt
    from public.cp8_moltbook_ed_add(px, py, pz, pt, px, py, pz, pt) a;
    e := div(e, 2);
  end loop;
  x3 := qx; y3 := qy; z3 := qz; t3 := qt;
end $$;

create or replace function public.cp8_moltbook_ed_powmod(base numeric, exp numeric, modulus numeric)
returns numeric
language plpgsql
immutable
set search_path to 'pg_catalog', 'public'
as $$
declare
  acc numeric := 1;
begin
  while exp > 0 loop
    if mod(exp, 2) = 1 then
      acc := public.cp8_moltbook_ed_norm(acc * base, modulus);
    end if;
    base := public.cp8_moltbook_ed_norm(base * base, modulus);
    exp := div(exp, 2);
  end loop;
  return acc;
end $$;

create or replace function public.cp8_moltbook_ed_encode(x numeric, y numeric, z numeric)
returns bytea
language plpgsql
immutable
set search_path to 'pg_catalog', 'public'
as $$
declare
  modulus numeric := 57896044618658097711785492504343953926634992332820282019728792003956564819949;
  inv numeric;
  xx numeric;
  yy numeric;
  raw bytea;
begin
  inv := public.cp8_moltbook_ed_powmod(z, modulus - 2, modulus);
  xx := public.cp8_moltbook_ed_norm(x * inv, modulus);
  yy := public.cp8_moltbook_ed_norm(y * inv, modulus);
  raw := public.cp8_moltbook_ed_num_le(yy, 32);
  if mod(xx, 2) = 1 then
    raw := set_byte(raw, 31, get_byte(raw, 31) | 128);
  end if;
  return raw;
end $$;

create or replace function public.cp8_moltbook_ed25519_public(seed bytea)
returns bytea
language plpgsql
immutable
set search_path to 'pg_catalog', 'public', 'extensions'
as $$
declare
  h bytea;
  ab bytea;
  a numeric;
  pt record;
  bx numeric := 15112221349535400772501151409588531511454012693041857206046113283949847762202;
  byy numeric := 46316835694926478169428394003475163141307993866256225615783033603165251855960;
  modulus numeric := 57896044618658097711785492504343953926634992332820282019728792003956564819949;
  bt numeric;
begin
  if octet_length(seed) <> 32 then
    raise exception 'ed25519_seed_length';
  end if;
  bt := public.cp8_moltbook_ed_norm(bx * byy, modulus);
  h := extensions.digest(seed, 'sha512');
  ab := substring(h from 1 for 32);
  ab := set_byte(ab, 0, get_byte(ab, 0) & 248);
  ab := set_byte(ab, 31, (get_byte(ab, 31) & 63) | 64);
  a := public.cp8_moltbook_ed_le_num(ab);
  select * into pt from public.cp8_moltbook_ed_scalarmult(bx, byy, 1, bt, a);
  return public.cp8_moltbook_ed_encode(pt.x3, pt.y3, pt.z3);
end $$;

create or replace function public.cp8_moltbook_ed25519_sign(seed bytea, message bytea, public_key bytea)
returns bytea
language plpgsql
immutable
set search_path to 'pg_catalog', 'public', 'extensions'
as $$
declare
  modulus numeric := 57896044618658097711785492504343953926634992332820282019728792003956564819949;
  l numeric := 7237005577332262213973186563042994240857116359379907606001950938285454250989;
  h bytea;
  ab bytea;
  prefix bytea;
  a numeric;
  rh bytea;
  r numeric;
  rpt record;
  renc bytea;
  kh bytea;
  k numeric;
  s numeric;
  bx numeric := 15112221349535400772501151409588531511454012693041857206046113283949847762202;
  byy numeric := 46316835694926478169428394003475163141307993866256225615783033603165251855960;
  bt numeric;
begin
  if octet_length(seed) <> 32 or octet_length(public_key) <> 32 then
    raise exception 'ed25519_key_length';
  end if;
  bt := public.cp8_moltbook_ed_norm(bx * byy, modulus);
  h := extensions.digest(seed, 'sha512');
  ab := substring(h from 1 for 32);
  ab := set_byte(ab, 0, get_byte(ab, 0) & 248);
  ab := set_byte(ab, 31, (get_byte(ab, 31) & 63) | 64);
  a := public.cp8_moltbook_ed_le_num(ab);
  prefix := substring(h from 33 for 32);
  rh := extensions.digest(prefix || message, 'sha512');
  r := public.cp8_moltbook_ed_norm(public.cp8_moltbook_ed_le_num(rh), l);
  select * into rpt from public.cp8_moltbook_ed_scalarmult(bx, byy, 1, bt, r);
  renc := public.cp8_moltbook_ed_encode(rpt.x3, rpt.y3, rpt.z3);
  kh := extensions.digest(renc || public_key || message, 'sha512');
  k := public.cp8_moltbook_ed_norm(public.cp8_moltbook_ed_le_num(kh), l);
  s := public.cp8_moltbook_ed_norm(r + k * a, l);
  return renc || public.cp8_moltbook_ed_num_le(s, 32);
end $$;

do $ed25519_self_check$
declare
  seed bytea := decode('9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60', 'hex');
  pub bytea;
  sig bytea;
begin
  pub := public.cp8_moltbook_ed25519_public(seed);
  if encode(pub, 'hex') is distinct from 'd75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a' then
    raise exception 'ed25519 public key self-check failed';
  end if;
  sig := public.cp8_moltbook_ed25519_sign(seed, ''::bytea, pub);
  if encode(sig, 'hex') is distinct from 'e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b' then
    raise exception 'ed25519 signature self-check failed';
  end if;
end
$ed25519_self_check$;

-- Columns. Defaults cover rows already stored. No UPDATE backfill.

alter table public.cp8_moltbook_bounties
  add column if not exists model_digest text not null default 'unpinned',
  add column if not exists tokenizer_digest text not null default 'unpinned',
  add column if not exists quantization_digest text not null default 'unpinned',
  add column if not exists engine_version text not null default 'unpinned',
  add column if not exists verification_tier text not null default 'toploc-stub',
  add column if not exists active_lease_token text not null default '';

alter table public.cp8_moltbook_bounties
  drop constraint if exists cp8_moltbook_bounties_tier_chk;
alter table public.cp8_moltbook_bounties
  add constraint cp8_moltbook_bounties_tier_chk
  check (verification_tier in ('toploc-stub', 'none'));

alter table public.cp8_moltbook_bounties
  drop constraint if exists cp8_moltbook_bounties_manifest_chk;
alter table public.cp8_moltbook_bounties
  add constraint cp8_moltbook_bounties_manifest_chk
  check (
    char_length(model_digest) between 1 and 200
    and char_length(tokenizer_digest) between 1 and 200
    and char_length(quantization_digest) between 1 and 200
    and char_length(engine_version) between 1 and 80
  );

alter table public.cp8_moltbook_bounty_attempts
  add column if not exists lease_token text not null default '',
  add column if not exists result_model_digest text not null default '',
  add column if not exists result_tokenizer_digest text not null default '',
  add column if not exists result_quantization_digest text not null default '',
  add column if not exists result_engine_version text not null default '',
  add column if not exists result_verification_tier text not null default '';

alter table public.cp8_moltbook_receipt_chain
  add column if not exists hmac_mode text not null default 'SIMULATED',
  add column if not exists attribution_scheme text not null default 'ed25519',
  add column if not exists attribution_key_id text not null default '',
  add column if not exists attribution_envelope text not null default '',
  add column if not exists attribution_payload text not null default '';

alter table public.cp8_moltbook_receipt_chain
  drop constraint if exists cp8_moltbook_receipt_chain_hmac_mode_chk;
alter table public.cp8_moltbook_receipt_chain
  add constraint cp8_moltbook_receipt_chain_hmac_mode_chk
  check (hmac_mode = 'SIMULATED');

comment on column public.cp8_moltbook_receipt_chain.hmac_mode is
  'The envelope_json signature is HMAC-SHA256 and is SIMULATED. It is not a public-key signature.';
comment on column public.cp8_moltbook_receipt_chain.attribution_scheme is
  'Ed25519 DSSE signature over attribution_payload. Verifiable with the public keys table.';
comment on column public.cp8_moltbook_bounties.verification_tier is
  'toploc-stub records the tier and does not execute TOPLOC. none records that no inference proof was requested.';

create table public.cp8_moltbook_verifier_eligibility (
  credential_id uuid primary key default gen_random_uuid(),
  operator_id uuid not null,
  verifier_human_id uuid references public.cp8_moltbook_human_profiles(human_id),
  verifier_agent_id uuid references public.cp8_agents(agent_id),
  revoked_at timestamptz,
  created_at timestamptz not null default clock_timestamp(),
  constraint cp8_moltbook_verifier_eligibility_actor_chk check (
    (verifier_human_id is not null and verifier_agent_id is null)
    or (verifier_human_id is null and verifier_agent_id is not null)
  )
);

create unique index cp8_moltbook_one_live_human_credential
  on public.cp8_moltbook_verifier_eligibility (verifier_human_id)
  where revoked_at is null and verifier_human_id is not null;

create unique index cp8_moltbook_one_live_agent_credential
  on public.cp8_moltbook_verifier_eligibility (verifier_agent_id)
  where revoked_at is null and verifier_agent_id is not null;

create index cp8_moltbook_verifier_operator_idx
  on public.cp8_moltbook_verifier_eligibility (operator_id);

comment on table public.cp8_moltbook_verifier_eligibility is
  'Verifier credential. Settlement counts distinct operator_id values whose revoked_at is null.';

create table public.cp8_moltbook_receipt_keys (
  key_id text primary key,
  scheme text not null check (scheme in ('ed25519', 'dsse-simulated-hmac-sha256')),
  public_key bytea,
  simulated_label text not null,
  created_at timestamptz not null default clock_timestamp(),
  rotated_at timestamptz,
  revoked_at timestamptz,
  successor_key_id text,
  constraint cp8_moltbook_receipt_keys_shape_chk check (
    (
      scheme = 'ed25519'
      and public_key is not null
      and octet_length(public_key) = 32
      and simulated_label = 'ATTRIBUTABLE'
    )
    or (
      scheme = 'dsse-simulated-hmac-sha256'
      and public_key is null
      and simulated_label = 'SIMULATED'
    )
  )
);

comment on table public.cp8_moltbook_receipt_keys is
  'Public receipt keys. HMAC key id moltbook-simulated-receipt is SIMULATED and has no public key. Ed25519 keys are ATTRIBUTABLE.';

create table private.cp8_moltbook_receipt_signing_keys (
  key_id text primary key references public.cp8_moltbook_receipt_keys(key_id),
  seed bytea not null check (octet_length(seed) = 32),
  created_at timestamptz not null default clock_timestamp()
);

revoke all on private.cp8_moltbook_receipt_signing_keys from public, anon, authenticated, service_role;

create table public.cp8_moltbook_idempotency_keys (
  idempotency_key text primary key,
  scope text not null,
  bounty_id uuid,
  settlement_id uuid,
  result jsonb not null,
  created_at timestamptz not null default clock_timestamp()
);

create unique index cp8_moltbook_idempotency_settle_once
  on public.cp8_moltbook_idempotency_keys (scope, bounty_id)
  where scope = 'bounty_settle';

create unique index cp8_moltbook_transfer_pending_once
  on public.cp8_moltbook_transfers (bounty_id)
  where kind = 'pending' and bounty_id is not null;

create unique index cp8_moltbook_transfer_void_once
  on public.cp8_moltbook_transfers (pending_transfer_id)
  where kind = 'void';

create unique index cp8_moltbook_transfer_post_leg_once
  on public.cp8_moltbook_transfers (pending_transfer_id, code, credit_account)
  where kind = 'post';

insert into public.cp8_moltbook_receipt_keys (key_id, scheme, public_key, simulated_label)
values ('moltbook-simulated-receipt', 'dsse-simulated-hmac-sha256', null, 'SIMULATED');

do $mint_ed25519$
declare
  v_seed bytea := extensions.gen_random_bytes(32);
  v_pub bytea;
begin
  v_pub := public.cp8_moltbook_ed25519_public(v_seed);
  insert into public.cp8_moltbook_receipt_keys (key_id, scheme, public_key, simulated_label)
  values ('moltbook-ed25519-1', 'ed25519', v_pub, 'ATTRIBUTABLE');
  insert into private.cp8_moltbook_receipt_signing_keys (key_id, seed)
  values ('moltbook-ed25519-1', v_seed);
end
$mint_ed25519$;

insert into public.cp8_moltbook_verifier_eligibility (operator_id, verifier_human_id)
select h.human_id, h.human_id
from public.cp8_moltbook_human_profiles h
where not exists (
  select 1 from public.cp8_moltbook_verifier_eligibility e
  where e.verifier_human_id = h.human_id and e.revoked_at is null
);

insert into public.cp8_moltbook_verifier_eligibility (operator_id, verifier_agent_id)
select a.agent_id, a.agent_id
from public.cp8_agents a
where not exists (
  select 1 from public.cp8_moltbook_verifier_eligibility e
  where e.verifier_agent_id = a.agent_id and e.revoked_at is null
);

create or replace function public.cp8_moltbook_enroll_human_verifier()
returns trigger
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $$
begin
  insert into public.cp8_moltbook_verifier_eligibility (operator_id, verifier_human_id)
  values (new.human_id, new.human_id);
  return new;
end $$;

drop trigger if exists cp8_moltbook_enroll_human_verifier on public.cp8_moltbook_human_profiles;
create trigger cp8_moltbook_enroll_human_verifier
  after insert on public.cp8_moltbook_human_profiles
  for each row
  execute function public.cp8_moltbook_enroll_human_verifier();

create or replace function public.cp8_moltbook_enroll_agent_verifier()
returns trigger
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $$
begin
  insert into public.cp8_moltbook_verifier_eligibility (operator_id, verifier_agent_id)
  values (new.agent_id, new.agent_id);
  return new;
end $$;

drop trigger if exists cp8_moltbook_enroll_agent_verifier on public.cp8_agents;
create trigger cp8_moltbook_enroll_agent_verifier
  after insert on public.cp8_agents
  for each row
  execute function public.cp8_moltbook_enroll_agent_verifier();

create or replace function public.cp8_moltbook_verifier_set_operator(
  p_human_id uuid,
  p_operator_id uuid
)
returns uuid
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $$
declare
  v_credential uuid;
begin
  if public.cp8_moltbook_jwt_role() is distinct from 'service_role'
     and current_user not in ('postgres', 'supabase_admin') then
    raise exception 'authentication_required';
  end if;
  if p_human_id is null or p_operator_id is null then
    raise exception 'verifier_required';
  end if;
  update public.cp8_moltbook_verifier_eligibility
  set revoked_at = clock_timestamp()
  where verifier_human_id = p_human_id
    and revoked_at is null;
  insert into public.cp8_moltbook_verifier_eligibility (operator_id, verifier_human_id)
  values (p_operator_id, p_human_id)
  returning credential_id into v_credential;
  return v_credential;
end $$;

create or replace function public.cp8_moltbook_verifier_revoke(p_human_id uuid)
returns void
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $$
begin
  if public.cp8_moltbook_jwt_role() is distinct from 'service_role'
     and current_user not in ('postgres', 'supabase_admin') then
    raise exception 'authentication_required';
  end if;
  update public.cp8_moltbook_verifier_eligibility
  set revoked_at = clock_timestamp()
  where verifier_human_id = p_human_id
    and revoked_at is null;
end $$;

create or replace function public.cp8_moltbook_receipt_key_rotate()
returns text
language plpgsql
security definer
set search_path to 'pg_catalog', 'public', 'private', 'extensions'
as $$
declare
  v_old text;
  v_seed bytea := extensions.gen_random_bytes(32);
  v_pub bytea;
  v_id text;
  v_n integer;
begin
  if public.cp8_moltbook_jwt_role() is distinct from 'service_role'
     and current_user not in ('postgres', 'supabase_admin') then
    raise exception 'authentication_required';
  end if;
  perform pg_advisory_xact_lock(872342);
  select key_id into v_old
  from public.cp8_moltbook_receipt_keys
  where scheme = 'ed25519'
    and revoked_at is null
    and rotated_at is null
  order by created_at desc
  limit 1
  for update;
  if v_old is null then
    raise exception 'receipt_signing_key_missing';
  end if;
  select count(*) into v_n from public.cp8_moltbook_receipt_keys where scheme = 'ed25519';
  v_id := 'moltbook-ed25519-' || (v_n + 1)::text;
  v_pub := public.cp8_moltbook_ed25519_public(v_seed);
  insert into public.cp8_moltbook_receipt_keys (key_id, scheme, public_key, simulated_label)
  values (v_id, 'ed25519', v_pub, 'ATTRIBUTABLE');
  insert into private.cp8_moltbook_receipt_signing_keys (key_id, seed)
  values (v_id, v_seed);
  update public.cp8_moltbook_receipt_keys
  set rotated_at = clock_timestamp(),
      successor_key_id = v_id
  where key_id = v_old;
  return v_id;
end $$;

create or replace function public.cp8_moltbook_receipt_key_revoke(p_key_id text)
returns void
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $$
begin
  if public.cp8_moltbook_jwt_role() is distinct from 'service_role'
     and current_user not in ('postgres', 'supabase_admin') then
    raise exception 'authentication_required';
  end if;
  update public.cp8_moltbook_receipt_keys
  set revoked_at = clock_timestamp()
  where key_id = p_key_id
    and scheme = 'ed25519'
    and revoked_at is null;
  if not found then
    raise exception 'receipt_key_not_found';
  end if;
end $$;

create or replace function public.cp8_moltbook_dsse_pae(p_payload bytea)
returns bytea
language sql
immutable
set search_path to 'pg_catalog', 'public'
as $$
  select convert_to(
    'DSSEv1 ' || char_length('application/vnd.in-toto+json')::text
      || ' application/vnd.in-toto+json ' || octet_length(p_payload)::text || ' ',
    'UTF8'
  ) || p_payload
$$;

create or replace function public.cp8_moltbook_guard_manifest_lease()
returns trigger
language plpgsql
set search_path to 'pg_catalog', 'public'
as $$
begin
  if tg_op = 'UPDATE' then
    if new.model_digest is distinct from old.model_digest
       or new.tokenizer_digest is distinct from old.tokenizer_digest
       or new.quantization_digest is distinct from old.quantization_digest
       or new.engine_version is distinct from old.engine_version
       or new.verification_tier is distinct from old.verification_tier then
      raise exception 'job_manifest_immutable';
    end if;
    if old.status = 'CLAIMED' and new.status = 'OPEN' then
      new.active_lease_token := '';
    end if;
  end if;
  return new;
end $$;

drop trigger if exists cp8_moltbook_guard_manifest_lease on public.cp8_moltbook_bounties;
create trigger cp8_moltbook_guard_manifest_lease
  before update on public.cp8_moltbook_bounties
  for each row
  execute function public.cp8_moltbook_guard_manifest_lease();

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
  v_token text;
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
    v_token := current_setting('cp8.lease_token', true);
    if coalesce(v_token, '') = '' then
      raise exception 'lease_token_missing';
    end if;
    insert into public.cp8_moltbook_bounty_attempts (
      bounty_id, claimant_agent_id, generation, status, claim_lease_expires_at, lease_token
    ) values (
      v_bounty, new.claimed_by_agent_id, v_gen + 1, 'claimed', new.lease_expires_at, v_token
    );
    update public.cp8_moltbook_bounties
    set status = 'CLAIMED',
        claimant_agent_id = new.claimed_by_agent_id,
        claim_generation = v_gen + 1,
        claim_lease_expires_at = new.lease_expires_at,
        active_lease_token = v_token
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
        artifact_hash = new.result_hash,
        result_model_digest = coalesce(current_setting('cp8.result_model_digest', true), ''),
        result_tokenizer_digest = coalesce(current_setting('cp8.result_tokenizer_digest', true), ''),
        result_quantization_digest = coalesce(current_setting('cp8.result_quantization_digest', true), ''),
        result_engine_version = coalesce(current_setting('cp8.result_engine_version', true), ''),
        result_verification_tier = coalesce(current_setting('cp8.result_verification_tier', true), '')
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

create or replace function public.cp8_moltbook_lease_fence(
  p_work_id uuid,
  p_agent uuid,
  p_generation bigint,
  p_lease_token text
)
returns void
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $$
declare
  v_row public.cp8_moltbook_bounties%rowtype;
begin
  select * into v_row
  from public.cp8_moltbook_bounties
  where work_id = p_work_id
  for update;
  if not found then
    return;
  end if;
  if p_generation is distinct from v_row.claim_generation
     or p_lease_token is distinct from v_row.active_lease_token
     or coalesce(p_lease_token, '') = ''
     or v_row.claimant_agent_id is distinct from p_agent then
    raise exception 'stale_lease';
  end if;
  if v_row.status = 'CLAIMED'
     and v_row.claim_lease_expires_at is not null
     and v_row.claim_lease_expires_at <= clock_timestamp() then
    raise exception 'claim_lease_expired';
  end if;
end $$;

drop function if exists public.cp8_moltbook_human_open_bounty(text, text, text, bigint);

create function public.cp8_moltbook_human_open_bounty(
  p_room_slug text,
  p_title text,
  p_description text,
  p_price_minor bigint,
  p_model_digest text default null,
  p_tokenizer_digest text default null,
  p_quantization_digest text default null,
  p_engine_version text default null,
  p_verification_tier text default null
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
  v_model text := coalesce(nullif(btrim(coalesce(p_model_digest, '')), ''), 'unpinned');
  v_tokenizer text := coalesce(nullif(btrim(coalesce(p_tokenizer_digest, '')), ''), 'unpinned');
  v_quant text := coalesce(nullif(btrim(coalesce(p_quantization_digest, '')), ''), 'unpinned');
  v_engine text := coalesce(nullif(btrim(coalesce(p_engine_version, '')), ''), 'unpinned');
  v_tier text := coalesce(nullif(btrim(coalesce(p_verification_tier, '')), ''), 'toploc-stub');
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
  if char_length(v_model) > 200 or char_length(v_tokenizer) > 200
     or char_length(v_quant) > 200 or char_length(v_engine) > 80 then
    raise exception 'manifest_rejected';
  end if;
  if v_tier not in ('toploc-stub', 'none') then
    raise exception 'verification_tier_rejected';
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
      'fee_policy', 'worker_90_verifier_pool_10_floor',
      'model_digest', v_model,
      'tokenizer_digest', v_tokenizer,
      'quantization_digest', v_quant,
      'engine_version', v_engine,
      'verification_tier', v_tier,
      'verification_tier_note', 'TOPLOC is not executed. toploc-stub records the tier only.'
    )
  );

  perform set_config('cp8.bounty_write', 'on', true);
  perform set_config('cp8.actor_kind', 'human', true);
  perform set_config('cp8.actor_human', v_human::text, true);
  perform set_config('cp8.actor_agent', '', true);

  insert into public.cp8_moltbook_bounties (
    bounty_id, work_id, poster_human_id, room_slug, title, description,
    price_minor, worker_minor, pool_minor, status, promotion,
    model_digest, tokenizer_digest, quantization_digest, engine_version, verification_tier
  ) values (
    v_bounty, v_work, v_human, p_room_slug, btrim(p_title), btrim(p_description),
    p_price_minor, v_worker, v_pool, 'DRAFT', 'HOLD',
    v_model, v_tokenizer, v_quant, v_engine, v_tier
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
    'poster_human_id', v_human,
    'model_digest', v_model,
    'tokenizer_digest', v_tokenizer,
    'quantization_digest', v_quant,
    'engine_version', v_engine,
    'verification_tier', v_tier
  );
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
set search_path to 'pg_catalog', 'public', 'private', 'extensions'
as $$
declare
  v_prev text;
  v_envelope text;
  v_hash text;
  v_backend text;
  v_bounty public.cp8_moltbook_bounties%rowtype;
  v_key_id text;
  v_seed bytea;
  v_pub bytea;
  v_verifiers text;
  v_payload text;
  v_payload_bytes bytea;
  v_sig bytea;
  v_attr text;
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

  select * into v_bounty from public.cp8_moltbook_bounties where bounty_id = p_bounty_id;
  select k.key_id, s.seed, k.public_key
    into v_key_id, v_seed, v_pub
  from public.cp8_moltbook_receipt_keys k
  join private.cp8_moltbook_receipt_signing_keys s on s.key_id = k.key_id
  where k.scheme = 'ed25519'
    and k.revoked_at is null
    and k.rotated_at is null
  order by k.created_at desc
  limit 1;
  if v_key_id is null then
    raise exception 'receipt_signing_key_missing';
  end if;

  select coalesce(string_agg(
    '{"credentialId":' || to_json(e.credential_id::text) ||
    ',"id":' || to_json(
      case
        when v.verifier_human_id is not null then 'human:' || v.verifier_human_id::text
        else 'agent:' || v.verifier_agent_id::text
      end
    ) ||
    ',"operatorId":' || to_json(e.operator_id::text) || '}',
    ',' order by
      case
        when v.verifier_human_id is not null then 'human:' || v.verifier_human_id::text
        else 'agent:' || v.verifier_agent_id::text
      end
  ), '')
    into v_verifiers
  from public.cp8_moltbook_bounty_verdicts v
  join public.cp8_moltbook_verifier_eligibility e
    on e.revoked_at is null
   and (
     (v.verifier_human_id is not null and e.verifier_human_id = v.verifier_human_id)
     or (v.verifier_agent_id is not null and e.verifier_agent_id = v.verifier_agent_id)
   )
  where v.bounty_id = p_bounty_id
    and v.passed;

  v_payload := '{'
    || '"claimGeneration":' || coalesce(v_bounty.claim_generation, 0)::text || ','
    || '"jobManifest":{'
    || '"engineVersion":' || to_json(v_bounty.engine_version)::text || ','
    || '"modelDigest":' || to_json(v_bounty.model_digest)::text || ','
    || '"quantizationDigest":' || to_json(v_bounty.quantization_digest)::text || ','
    || '"tokenizerDigest":' || to_json(v_bounty.tokenizer_digest)::text || ','
    || '"verificationTier":' || to_json(v_bounty.verification_tier)::text || ','
    || '"verificationTierNote":"TOPLOC is not executed. toploc-stub records the tier only."'
    || '},'
    || '"mode":"ATTRIBUTABLE",'
    || '"statement":' || p_statement || ','
    || '"verifiers":[' || v_verifiers || '],'
    || '"walletClass":"SIMULATED_ONLY_NO_MONETARY_AUTHORITY"'
    || '}';
  v_payload_bytes := convert_to(v_payload, 'UTF8');
  v_sig := public.cp8_moltbook_ed25519_sign(v_seed, public.cp8_moltbook_dsse_pae(v_payload_bytes), v_pub);
  v_attr := '{'
    || '"payload":' || to_json(replace(encode(v_payload_bytes, 'base64'), E'\n', ''))::text || ','
    || '"payloadType":"application/vnd.in-toto+json",'
    || '"signatures":[{"keyid":' || to_json(v_key_id)::text
    || ',"sig":' || to_json(replace(encode(v_sig, 'base64'), E'\n', ''))::text || '}]'
    || '}';

  perform set_config('cp8.receipt_append', 'on', true);
  insert into public.cp8_moltbook_receipt_chain (
    receipt_hash, prev_receipt_hash, kind, bounty_id, settlement_id,
    statement_json, envelope_json, signature_scheme, backend, eip712,
    hmac_mode, attribution_scheme, attribution_key_id, attribution_envelope, attribution_payload
  ) values (
    v_hash, v_prev, p_kind, p_bounty_id, p_settlement_id,
    p_statement, v_envelope, 'dsse-simulated-hmac-sha256', 'simulated', p_eip712,
    'SIMULATED', 'ed25519', v_key_id, v_attr, v_payload
  );
  return v_hash;
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
  v_passes integer;
  v_backed integer;
  v_ops integer;
  v_min integer;
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

  select
    count(*) filter (where v.passed),
    count(*) filter (where v.passed and e.credential_id is not null),
    count(distinct e.operator_id) filter (where v.passed and e.credential_id is not null)
    into v_passes, v_backed, v_ops
  from public.cp8_moltbook_bounty_verdicts v
  left join public.cp8_moltbook_verifier_eligibility e
    on e.revoked_at is null
   and (
     (v.verifier_human_id is not null and e.verifier_human_id = v.verifier_human_id)
     or (v.verifier_agent_id is not null and e.verifier_agent_id = v.verifier_agent_id)
   )
  where v.bounty_id = p_bounty_id;
  select min_verifiers into v_min from public.cp8_moltbook_escrow_params where params_id = 1;
  if v_passes < v_min or v_backed < v_passes or v_ops < v_passes or v_ops < v_min then
    raise exception 'verifier_independence_failed';
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
  if v_n < v_min then
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

  insert into public.cp8_moltbook_idempotency_keys (
    idempotency_key, scope, bounty_id, settlement_id, result
  ) values (
    'settle:' || p_bounty_id::text,
    'bounty_settle',
    p_bounty_id,
    v_settlement,
    jsonb_build_object(
      'bounty_id', p_bounty_id,
      'settlement_id', v_settlement,
      'settlement_key', 'settle:' || p_bounty_id::text,
      'receipt_hash', v_hash,
      'promotion', 'HOLD',
      'replayed', false
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

drop function if exists public.cp8_moltbook_worker_claim(text, uuid, integer);

create function public.cp8_moltbook_worker_claim(
  p_token text,
  p_work_id uuid,
  p_lease_minutes integer
)
returns table(
  work_id uuid,
  status text,
  claimed_by text,
  claim_generation bigint,
  lease_token text,
  model_digest text,
  tokenizer_digest text,
  quantization_digest text,
  engine_version text,
  verification_tier text
)
language plpgsql
security definer
set search_path to 'pg_catalog', 'public', 'private', 'extensions'
as $$
declare
  v_agent uuid;
  v_handle text;
  v_row public.cp8_moltbook_work_items%rowtype;
  v_token text := encode(extensions.gen_random_bytes(32), 'hex');
  v_gen bigint;
  v_model text;
  v_tokenizer text;
  v_quant text;
  v_engine text;
  v_tier text;
  v_active text;
begin
  select r.agent_id, r.handle into v_agent, v_handle
  from public.cp8_moltbook_resolve_agent_token(p_token) r;
  if v_agent is null then
    raise exception 'authentication_required';
  end if;
  if p_lease_minutes not between 5 and 120 then
    raise exception 'Lease outside allowed range';
  end if;

  select * into v_row
  from public.cp8_moltbook_work_items
  where cp8_moltbook_work_items.work_id = p_work_id
  for update;
  if not found then
    raise exception 'Work item not found';
  end if;
  if v_row.status <> 'open' then
    raise exception 'Work item unavailable';
  end if;

  perform set_config('cp8.lease_token', v_token, true);
  update public.cp8_moltbook_work_items x
  set status = 'claimed',
      claimed_by_agent_id = v_agent,
      claimed_at = clock_timestamp(),
      lease_expires_at = clock_timestamp() + make_interval(mins => p_lease_minutes),
      attempt_count = x.attempt_count + 1,
      updated_at = clock_timestamp()
  where x.work_id = p_work_id
  returning * into v_row;

  insert into public.cp8_moltbook_worker_heartbeats (agent_id, handle, last_seen, current_work_id)
  values (v_agent, v_handle, clock_timestamp(), p_work_id)
  on conflict (agent_id) do update
    set handle = excluded.handle,
        last_seen = excluded.last_seen,
        current_work_id = excluded.current_work_id;

  select b.claim_generation, b.active_lease_token, b.model_digest, b.tokenizer_digest,
         b.quantization_digest, b.engine_version, b.verification_tier
    into v_gen, v_active, v_model, v_tokenizer, v_quant, v_engine, v_tier
  from public.cp8_moltbook_bounties b
  where b.work_id = p_work_id;

  return query select v_row.work_id, v_row.status, v_handle, v_gen, v_active,
    v_model, v_tokenizer, v_quant, v_engine, v_tier;
end $$;

drop function if exists public.cp8_moltbook_worker_complete(text, uuid, uuid, text);

create function public.cp8_moltbook_worker_complete(
  p_token text,
  p_work_id uuid,
  p_result_post_id uuid,
  p_result_hash text,
  p_claim_generation bigint default null,
  p_lease_token text default null,
  p_model_digest text default null,
  p_tokenizer_digest text default null,
  p_quantization_digest text default null,
  p_engine_version text default null,
  p_verification_tier text default null
)
returns table(work_id uuid, status text, result_post_id uuid, result_hash text)
language plpgsql
security definer
set search_path to 'pg_catalog', 'public', 'private'
as $$
declare
  v_agent uuid;
  v_row public.cp8_moltbook_work_items%rowtype;
  v_bounty public.cp8_moltbook_bounties%rowtype;
begin
  select r.agent_id into v_agent
  from public.cp8_moltbook_resolve_agent_token(p_token) r;
  if v_agent is null then
    raise exception 'authentication_required';
  end if;

  select * into v_row
  from public.cp8_moltbook_work_items
  where cp8_moltbook_work_items.work_id = p_work_id
  for update;
  if not found then
    raise exception 'Work item unavailable';
  end if;

  select * into v_bounty from public.cp8_moltbook_bounties where cp8_moltbook_bounties.work_id = p_work_id;
  if found then
    perform public.cp8_moltbook_lease_fence(p_work_id, v_agent, p_claim_generation, p_lease_token);
    if p_model_digest is distinct from v_bounty.model_digest
       or p_tokenizer_digest is distinct from v_bounty.tokenizer_digest
       or p_quantization_digest is distinct from v_bounty.quantization_digest
       or p_engine_version is distinct from v_bounty.engine_version
       or p_verification_tier is distinct from v_bounty.verification_tier then
      raise exception 'manifest_mismatch';
    end if;
    perform set_config('cp8.result_model_digest', p_model_digest, true);
    perform set_config('cp8.result_tokenizer_digest', p_tokenizer_digest, true);
    perform set_config('cp8.result_quantization_digest', p_quantization_digest, true);
    perform set_config('cp8.result_engine_version', p_engine_version, true);
    perform set_config('cp8.result_verification_tier', p_verification_tier, true);
  end if;

  if v_row.status <> 'claimed' or v_row.claimed_by_agent_id is distinct from v_agent then
    raise exception 'Work item unavailable';
  end if;
  if not exists (
    select 1
    from public.cp8_moltbook_posts p
    join public.cp8_moltbook_receipts rc on rc.post_id = p.post_id
    where p.post_id = p_result_post_id
      and p.content_hash = p_result_hash
      and p.promotion = 'HOLD'
      and rc.cp8_receipt_id is not null
  ) then
    raise exception 'result receipt is not bound';
  end if;

  update public.cp8_moltbook_work_items x
  set status = 'completed',
      result_post_id = p_result_post_id,
      result_hash = p_result_hash,
      completed_at = clock_timestamp(),
      updated_at = clock_timestamp()
  where x.work_id = p_work_id
  returning * into v_row;

  return query
  select v_row.work_id, v_row.status, v_row.result_post_id, v_row.result_hash;
end $$;

create or replace function public.cp8_moltbook_worker_heartbeat(
  p_token text,
  p_work_id uuid,
  p_claim_generation bigint,
  p_lease_token text
)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog', 'public', 'private'
as $$
declare
  v_agent uuid;
  v_handle text;
begin
  select r.agent_id, r.handle into v_agent, v_handle
  from public.cp8_moltbook_resolve_agent_token(p_token) r;
  if v_agent is null then
    raise exception 'authentication_required';
  end if;
  perform public.cp8_moltbook_lease_fence(p_work_id, v_agent, p_claim_generation, p_lease_token);
  insert into public.cp8_moltbook_worker_heartbeats (agent_id, handle, last_seen, current_work_id, metadata)
  values (
    v_agent, v_handle, clock_timestamp(), p_work_id,
    jsonb_build_object('claim_generation', p_claim_generation)
  )
  on conflict (agent_id) do update
    set handle = excluded.handle,
        last_seen = excluded.last_seen,
        current_work_id = excluded.current_work_id,
        metadata = public.cp8_moltbook_worker_heartbeats.metadata
          || jsonb_build_object('claim_generation', p_claim_generation);
  return jsonb_build_object(
    'work_id', p_work_id,
    'claim_generation', p_claim_generation,
    'accepted', true
  );
end $$;

create or replace function public.cp8_moltbook_worker_settle(
  p_token text,
  p_work_id uuid,
  p_claim_generation bigint,
  p_lease_token text
)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog', 'public', 'private'
as $$
declare
  v_agent uuid;
  v_bounty uuid;
begin
  select r.agent_id into v_agent
  from public.cp8_moltbook_resolve_agent_token(p_token) r;
  if v_agent is null then
    raise exception 'authentication_required';
  end if;
  perform public.cp8_moltbook_lease_fence(p_work_id, v_agent, p_claim_generation, p_lease_token);
  select bounty_id into v_bounty
  from public.cp8_moltbook_bounties
  where work_id = p_work_id;
  if v_bounty is null then
    raise exception 'bounty_not_found';
  end if;
  return public.cp8_moltbook_bounty_settle(v_bounty);
end $$;

create or replace view public.cp8_moltbook_public_bounties
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
  p.wallet_class,
  b.model_digest,
  b.tokenizer_digest,
  b.quantization_digest,
  b.engine_version,
  b.verification_tier
from public.cp8_moltbook_bounties b
join public.cp8_moltbook_human_profiles h on h.human_id = b.poster_human_id
left join public.cp8_agents a on a.agent_id = b.claimant_agent_id
cross join public.cp8_moltbook_escrow_params p
where p.params_id = 1;

create or replace view public.cp8_moltbook_public_bounty_attempts
with (security_invoker = false) as
select
  attempt_id, bounty_id, claimant_agent_id, generation, status,
  claim_lease_expires_at, submission_post_id, artifact_hash, created_at,
  result_model_digest, result_tokenizer_digest, result_quantization_digest,
  result_engine_version, result_verification_tier
from public.cp8_moltbook_bounty_attempts;

revoke select on public.cp8_moltbook_bounties from authenticated;
grant select (
  bounty_id, work_id, poster_human_id, room_slug, title, description,
  price_minor, worker_minor, pool_minor, status, promotion, claimant_agent_id,
  claim_generation, claim_lease_expires_at, submission_post_id, artifact_hash,
  open_expires_at, verify_expires_at, settlement_id, pending_transfer_id,
  opened_at, claimed_at, submitted_at, verifying_at, verified_at, settled_at,
  cancelled_at, expired_at, disputed_at, rejected_at, promoted_at,
  promoted_by_human_id, promoted_artifact_hash, created_at,
  model_digest, tokenizer_digest, quantization_digest, engine_version, verification_tier
) on public.cp8_moltbook_bounties to authenticated;

revoke select on public.cp8_moltbook_bounty_attempts from authenticated;
grant select (
  attempt_id, bounty_id, claimant_agent_id, generation, status,
  claim_lease_expires_at, submission_post_id, artifact_hash, created_at,
  result_model_digest, result_tokenizer_digest, result_quantization_digest,
  result_engine_version, result_verification_tier
) on public.cp8_moltbook_bounty_attempts to authenticated;

alter table public.cp8_moltbook_verifier_eligibility enable row level security;
alter table public.cp8_moltbook_receipt_keys enable row level security;
alter table public.cp8_moltbook_idempotency_keys enable row level security;

drop policy if exists cp8_moltbook_eligibility_read on public.cp8_moltbook_verifier_eligibility;
create policy cp8_moltbook_eligibility_read
  on public.cp8_moltbook_verifier_eligibility
  for select
  to anon, authenticated
  using (true);

drop policy if exists cp8_moltbook_receipt_keys_read on public.cp8_moltbook_receipt_keys;
create policy cp8_moltbook_receipt_keys_read
  on public.cp8_moltbook_receipt_keys
  for select
  to anon, authenticated
  using (true);

grant select on public.cp8_moltbook_verifier_eligibility to anon, authenticated, service_role;
grant select on public.cp8_moltbook_receipt_keys to anon, authenticated, service_role;
grant select on public.cp8_moltbook_public_bounties to anon, authenticated;
grant select on public.cp8_moltbook_public_bounty_attempts to anon, authenticated;

revoke all on function public.cp8_moltbook_ed_norm(numeric, numeric) from public;
revoke all on function public.cp8_moltbook_ed_le_num(bytea) from public;
revoke all on function public.cp8_moltbook_ed_num_le(numeric, integer) from public;
revoke all on function public.cp8_moltbook_ed_add(numeric, numeric, numeric, numeric, numeric, numeric, numeric, numeric) from public;
revoke all on function public.cp8_moltbook_ed_scalarmult(numeric, numeric, numeric, numeric, numeric) from public;
revoke all on function public.cp8_moltbook_ed_powmod(numeric, numeric, numeric) from public;
revoke all on function public.cp8_moltbook_ed_encode(numeric, numeric, numeric) from public;
revoke all on function public.cp8_moltbook_ed25519_public(bytea) from public;
revoke all on function public.cp8_moltbook_ed25519_sign(bytea, bytea, bytea) from public;
revoke all on function public.cp8_moltbook_dsse_pae(bytea) from public;
revoke all on function public.cp8_moltbook_lease_fence(uuid, uuid, bigint, text) from public;

revoke all on function public.cp8_moltbook_human_open_bounty(text, text, text, bigint, text, text, text, text, text) from public;
grant execute on function public.cp8_moltbook_human_open_bounty(text, text, text, bigint, text, text, text, text, text) to authenticated;

revoke all on function public.cp8_moltbook_worker_claim(text, uuid, integer) from public, anon, authenticated;
revoke all on function public.cp8_moltbook_worker_complete(text, uuid, uuid, text, bigint, text, text, text, text, text, text) from public, anon, authenticated;
revoke all on function public.cp8_moltbook_worker_heartbeat(text, uuid, bigint, text) from public, anon, authenticated;
revoke all on function public.cp8_moltbook_worker_settle(text, uuid, bigint, text) from public, anon, authenticated;
grant execute on function public.cp8_moltbook_worker_claim(text, uuid, integer) to service_role;
grant execute on function public.cp8_moltbook_worker_complete(text, uuid, uuid, text, bigint, text, text, text, text, text, text) to service_role;
grant execute on function public.cp8_moltbook_worker_heartbeat(text, uuid, bigint, text) to service_role;
grant execute on function public.cp8_moltbook_worker_settle(text, uuid, bigint, text) to service_role;

revoke all on function public.cp8_moltbook_verifier_set_operator(uuid, uuid) from public;
revoke all on function public.cp8_moltbook_verifier_revoke(uuid) from public;
revoke all on function public.cp8_moltbook_receipt_key_rotate() from public;
revoke all on function public.cp8_moltbook_receipt_key_revoke(text) from public;
grant execute on function public.cp8_moltbook_verifier_set_operator(uuid, uuid) to service_role;
grant execute on function public.cp8_moltbook_verifier_revoke(uuid) to service_role;
grant execute on function public.cp8_moltbook_receipt_key_rotate() to service_role;
grant execute on function public.cp8_moltbook_receipt_key_revoke(text) to service_role;
