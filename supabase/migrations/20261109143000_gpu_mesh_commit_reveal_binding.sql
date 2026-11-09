-- Commit-reveal, distinct receipt digests, and disagreement hold.
-- A verifier stores a sha256 commitment before the hub will reveal the
-- worker output hash. Checker pay does not depend on agree vs disagree.
-- A disagreement keeps the worker payout off the Base Sepolia queue.
-- New columns are empty-default so existing rows stay valid.
-- anon and authenticated stay revoked. This does not upgrade Postgres.

alter table public.gpumesh_jobs
  add column if not exists output_commitment text not null default '',
  add column if not exists commitment_at double precision not null default 0,
  add column if not exists weights_digest text not null default '',
  add column if not exists input_digest text not null default '',
  add column if not exists batch_id text not null default '';

alter table public.gpumesh_nodes
  add column if not exists batch_id text not null default '';

alter table public.gpumesh_chain_settlements
  add column if not exists verifier1_decision text not null default '',
  add column if not exists verifier2_decision text not null default '',
  add column if not exists tiebreak_node_id text not null default '',
  add column if not exists tiebreak_decision text not null default '';

comment on column public.gpumesh_jobs.output_commitment is
  'sha256 hex of the verifier output, stored before the worker output hash is revealed.';
comment on column public.gpumesh_jobs.input_digest is
  'sha256 of the canonical chat messages. Distinct from the manifest, weights, and output digests.';
comment on column public.gpumesh_jobs.weights_digest is
  'GGUF sha256 reported by the node. Distinct from model_digest, which is the runtime manifest digest.';
comment on column public.gpumesh_jobs.batch_id is
  'Optional checker batch. batch-002 is verification-only.';
comment on column public.gpumesh_chain_settlements.tiebreak_decision is
  'agree or disagree_deterministic from the tiebreaker. A disagreement does not enter the mint queue.';
