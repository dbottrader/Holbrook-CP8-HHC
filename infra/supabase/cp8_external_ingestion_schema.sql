-- CP8 external ingestion schema snapshot
-- Applied to Supabase project AISquad (ecenvlwyenpakrxfuqup) on 2026-08-19.
-- This is a reproducibility snapshot, not a Supabase migration-history file.

create table if not exists public.cp8_external_sources (
  source_id text primary key,
  source_name text not null,
  source_type text not null,
  canonical_url text not null unique,
  owner_maintainer text,
  license_terms text,
  last_observed_version text,
  last_observed_update date,
  ingestion_method text not null default 'LINK_REFERENCE',
  fields_available jsonb not null default '[]'::jsonb,
  provenance_strength text not null default 'UNSPECIFIED' check (provenance_strength in ('PRIMARY','SCHOLARLY_SECONDARY','GENERAL_SECONDARY','COMMUNITY_ARCHIVE','UNSPECIFIED')),
  status text not null default 'REFERENCE_ONLY' check (status in ('ACTIVE','REFERENCE_ONLY','QUARANTINED','BLOCKED_BY_TERMS')),
  raw_mirror_policy text not null default 'UNKNOWN' check (raw_mirror_policy in ('MIRROR_ALLOWED','LINK_ONLY','UNKNOWN')),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.cp8_external_records (
  record_id text primary key,
  source_id text not null references public.cp8_external_sources(source_id) on delete restrict,
  external_id text not null,
  record_type text not null,
  title text,
  source_url text not null,
  observed_at timestamptz not null default now(),
  event_date date,
  event_date_precision text,
  classification text not null default 'SOURCE_REPORTED',
  provenance_strength text not null default 'UNSPECIFIED',
  canonical_entity_key text,
  raw_payload jsonb not null default '{}'::jsonb,
  raw_content_hash text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (source_id, external_id)
);

create table if not exists public.cp8_crop_formations (
  formation_id text primary key,
  canonical_entity_key text unique,
  discovery_date date,
  date_precision text,
  place text,
  nearest_town text,
  region text,
  country text,
  latitude numeric,
  longitude numeric,
  map_reference text,
  crop_type text,
  dimensions jsonb not null default '{}'::jsonb,
  circle_count integer,
  ring_count integer,
  symmetry_order integer,
  orientation_azimuth_deg numeric,
  staged_additions jsonb not null default '[]'::jsonb,
  evidence_classification text not null default 'SOURCE_REPORTED' check (evidence_classification in ('OBSERVED_FORMATION','SOURCE_REPORTED','FIELD_SURVEYED','ANALYSIS_REPRODUCED','ENCODING_HYPOTHESIS','ENCODING_REJECTED','SPECULATION')),
  origin_classification text not null default 'ORIGIN_UNRESOLVED' check (origin_classification in ('HUMAN_MADE_CONFIRMED','HUMAN_MADE_LIKELY','ORIGIN_UNRESOLVED','UNKNOWN')),
  source_confidence numeric check (source_confidence is null or (source_confidence >= 0 and source_confidence <= 1)),
  geometry_summary jsonb not null default '{}'::jsonb,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.cp8_crop_formation_sources (
  formation_id text not null references public.cp8_crop_formations(formation_id) on delete cascade,
  record_id text not null references public.cp8_external_records(record_id) on delete restrict,
  match_status text not null default 'PROPOSED' check (match_status in ('PROPOSED','MATCHED','CONFLICT','REJECTED')),
  match_confidence numeric check (match_confidence is null or (match_confidence >= 0 and match_confidence <= 1)),
  conflict_notes jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  primary key (formation_id, record_id)
);

create table if not exists public.cp8_analysis_runs (
  analysis_id text primary key,
  record_id text references public.cp8_external_records(record_id) on delete restrict,
  formation_id text references public.cp8_crop_formations(formation_id) on delete restrict,
  analysis_type text not null,
  preregistered boolean not null default false,
  algorithm_ref text not null,
  algorithm_version text,
  parameters jsonb not null default '{}'::jsonb,
  result jsonb not null default '{}'::jsonb,
  result_hash text,
  outcome text not null default 'OPEN' check (outcome in ('OPEN','PASS','FAIL','INCONCLUSIVE','REJECTED')),
  created_by text not null,
  cp8_receipt_id uuid references public.cp8_receipts(receipt_id) on delete set null,
  created_at timestamptz not null default now(),
  check (record_id is not null or formation_id is not null)
);

create index if not exists cp8_external_records_source_idx on public.cp8_external_records(source_id, event_date desc);
create index if not exists cp8_external_records_entity_idx on public.cp8_external_records(canonical_entity_key);
create index if not exists cp8_crop_formations_date_idx on public.cp8_crop_formations(discovery_date desc);
create index if not exists cp8_crop_formations_country_region_idx on public.cp8_crop_formations(country, region);
create index if not exists cp8_crop_formation_sources_record_idx on public.cp8_crop_formation_sources(record_id);
create index if not exists cp8_analysis_runs_record_idx on public.cp8_analysis_runs(record_id, created_at desc);
create index if not exists cp8_analysis_runs_formation_idx on public.cp8_analysis_runs(formation_id, created_at desc);
create index if not exists cp8_analysis_runs_receipt_idx on public.cp8_analysis_runs(cp8_receipt_id);

alter table public.cp8_external_sources enable row level security;
alter table public.cp8_external_records enable row level security;
alter table public.cp8_crop_formations enable row level security;
alter table public.cp8_crop_formation_sources enable row level security;
alter table public.cp8_analysis_runs enable row level security;

revoke insert, update, delete on public.cp8_external_sources, public.cp8_external_records, public.cp8_crop_formations, public.cp8_crop_formation_sources, public.cp8_analysis_runs from anon, authenticated;
grant select on public.cp8_external_sources, public.cp8_external_records, public.cp8_crop_formations, public.cp8_crop_formation_sources, public.cp8_analysis_runs to anon, authenticated;
grant select, insert, update, delete on public.cp8_external_sources, public.cp8_external_records, public.cp8_crop_formations, public.cp8_crop_formation_sources, public.cp8_analysis_runs to service_role;

-- Public-read policies are intentional for these public research registry surfaces.
drop policy if exists "public read cp8 external sources" on public.cp8_external_sources;
create policy "public read cp8 external sources" on public.cp8_external_sources for select to anon, authenticated using (true);
drop policy if exists "public read cp8 external records" on public.cp8_external_records;
create policy "public read cp8 external records" on public.cp8_external_records for select to anon, authenticated using (true);
drop policy if exists "public read cp8 crop formations" on public.cp8_crop_formations;
create policy "public read cp8 crop formations" on public.cp8_crop_formations for select to anon, authenticated using (true);
drop policy if exists "public read cp8 crop formation sources" on public.cp8_crop_formation_sources;
create policy "public read cp8 crop formation sources" on public.cp8_crop_formation_sources for select to anon, authenticated using (true);
drop policy if exists "public read cp8 analysis runs" on public.cp8_analysis_runs;
create policy "public read cp8 analysis runs" on public.cp8_analysis_runs for select to anon, authenticated using (true);
