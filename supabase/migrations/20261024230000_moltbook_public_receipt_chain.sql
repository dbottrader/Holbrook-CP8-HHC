-- Public receipt-chain projection for the Pages console.
--
-- NOT APPLIED to project ecenvlwyenpakrxfuqup. Do not run this against the
-- live database from CI. Apply it only after
-- 20261024180000_moltbook_advisor_hardening.sql, which moves the bounty
-- projections into cp8_moltbook_internal.
--
-- The console can already read the five public bounty views and can call
-- cp8_moltbook_settlement_receipt_ok. It cannot read receipt hashes: anon
-- has no select on cp8_moltbook_receipt_chain, and the public transfer view
-- omits prev_hash and entry_hash. This file adds those read columns and
-- nothing else.
--
-- statement_json and envelope_json stay off the public view. The simulated
-- HMAC key stays in private.cp8_moltbook_sim_receipt_key. No service role
-- key is involved. Base tables gain no new grants and no new policies.

create or replace view cp8_moltbook_internal.cp8_moltbook_public_receipts
with (security_invoker = false) as
select
  receipt_hash,
  prev_receipt_hash,
  kind,
  bounty_id,
  settlement_id,
  signature_scheme,
  backend,
  created_at
from public.cp8_moltbook_receipt_chain;

revoke all on cp8_moltbook_internal.cp8_moltbook_public_receipts from public, anon, authenticated;
grant select on cp8_moltbook_internal.cp8_moltbook_public_receipts to anon, authenticated, service_role;

create or replace view public.cp8_moltbook_public_receipts
with (security_invoker = true) as
select
  receipt_hash,
  prev_receipt_hash,
  kind,
  bounty_id,
  settlement_id,
  signature_scheme,
  backend,
  created_at
from cp8_moltbook_internal.cp8_moltbook_public_receipts;

revoke all on public.cp8_moltbook_public_receipts from public, anon, authenticated;
grant select on public.cp8_moltbook_public_receipts to anon, authenticated, service_role;

comment on view public.cp8_moltbook_public_receipts is
  'Public receipt hashes and previous-hash links. No statement body, no envelope, no key. Signature recomputation stays in cp8_moltbook_settlement_receipt_ok.';

-- Add hash links at the end of the existing transfer projection.
-- CREATE OR REPLACE may append columns. The public view is then replaced
-- so its column list includes the new hashes. PostgreSQL stores a view's
-- select list at creation time, so replacing only the internal view would
-- leave the public view on the old columns.

create or replace view cp8_moltbook_internal.cp8_moltbook_public_transfers
with (security_invoker = false) as
select
  transfer_id,
  bounty_id,
  kind,
  pending_transfer_id,
  debit_account,
  credit_account,
  amount_minor,
  code,
  prev_hash,
  entry_hash,
  created_at
from public.cp8_moltbook_transfers
where bounty_id is not null;

create or replace view public.cp8_moltbook_public_transfers
with (security_invoker = true) as
select
  transfer_id,
  bounty_id,
  kind,
  pending_transfer_id,
  debit_account,
  credit_account,
  amount_minor,
  code,
  prev_hash,
  entry_hash,
  created_at
from cp8_moltbook_internal.cp8_moltbook_public_transfers;

revoke all on public.cp8_moltbook_public_transfers from public, anon, authenticated;
grant select on public.cp8_moltbook_public_transfers to anon, authenticated, service_role;
grant select on cp8_moltbook_internal.cp8_moltbook_public_transfers to anon, authenticated, service_role;

comment on view public.cp8_moltbook_public_transfers is
  'Public bounty transfer legs, including the hash link between legs. Stipend rows stay hidden because bounty_id is null.';
