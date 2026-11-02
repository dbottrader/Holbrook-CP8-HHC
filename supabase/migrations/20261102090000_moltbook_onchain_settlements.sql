-- On-chain settlement idempotency for HHCW minting on Base.
-- Exactly-once: unique idempotency_key; retries return the stored result_json.

CREATE TABLE IF NOT EXISTS public.cp8_moltbook_onchain_settlements (
  idempotency_key text PRIMARY KEY,
  settlement_id text NOT NULL,
  tx_hash text,
  block_number bigint,
  result_json jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS cp8_moltbook_onchain_settlements_settlement_id_uidx
  ON public.cp8_moltbook_onchain_settlements (settlement_id);

COMMENT ON TABLE public.cp8_moltbook_onchain_settlements IS
  'Idempotent record of Base Settlement.settle + mint txs. LEDGER_BACKEND=onchain.';

-- Server-side idempotency only. No client policies: the Data API roles cannot
-- read or write settlement receipts. The settler DSN must be the table owner
-- or a role that bypasses RLS (Supabase service_role does). anon/authenticated
-- exist on Supabase and are absent on a bare Postgres, so the revoke is guarded.
ALTER TABLE public.cp8_moltbook_onchain_settlements ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.cp8_moltbook_onchain_settlements FROM PUBLIC;

DO $onchain_rls$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
    EXECUTE 'REVOKE ALL ON TABLE public.cp8_moltbook_onchain_settlements FROM anon';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
    EXECUTE 'REVOKE ALL ON TABLE public.cp8_moltbook_onchain_settlements FROM authenticated';
  END IF;
END
$onchain_rls$;
