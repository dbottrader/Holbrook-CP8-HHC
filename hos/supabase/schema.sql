create extension if not exists pgcrypto;

create table if not exists public.hos_receipts (
  receipt_id text primary key,
  created_at timestamptz not null,
  packet jsonb not null,
  packet_sha256 text not null check (length(packet_sha256) = 64),
  actions jsonb not null default '[]'::jsonb,
  checks jsonb not null,
  authority text not null default 'USER_REVIEW_REQUIRED',
  runtime_claim text not null default 'REFERENCE_IMPLEMENTATION',
  inserted_at timestamptz not null default now()
);

create index if not exists hos_receipts_packet_sha256_idx
  on public.hos_receipts(packet_sha256);

alter table public.hos_receipts enable row level security;

-- No public insert policy is created by default.
-- Add a narrowly scoped policy only after choosing an authentication model.
