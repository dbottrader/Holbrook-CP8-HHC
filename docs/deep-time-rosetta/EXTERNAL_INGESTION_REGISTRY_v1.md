# Deep-Time Rosetta — External Ingestion Registry v1

Status: ACTIVE / RECEIPT-BEARING RESEARCH SUBSTRATE  
Date: 2026-08-19  
Supabase project: `AISquad` (`ecenvlwyenpakrxfuqup`)

## Purpose

This registry makes external ancient-language AI resources, crop-circle archives, public datasets, papers, and future archaeology sources reusable inside ASIN-HHC / CP8 without collapsing provenance or treating source claims as verified conclusions.

Core rule:

`SOURCE -> IMMUTABLE SOURCE RECORD -> CANONICAL ENTITY -> DERIVED MEASUREMENT -> ANALYSIS -> CHALLENGE / REPLICATION -> CP8 CLAIM`

Raw source observations and AI-derived interpretations are stored separately.

## Supabase federation layer

The live AISquad Supabase backend now contains:

- `cp8_external_sources` — canonical source/model/dataset/archive registry.
- `cp8_external_records` — immutable source snapshots with source-specific IDs and hashes.
- `cp8_crop_formations` — canonical crop-formation entities.
- `cp8_crop_formation_sources` — explicit source-to-formation matches/conflicts.
- `cp8_analysis_runs` — reproducible derived analyses with algorithm/version/parameters/result hash and optional CP8 receipt binding.

All five tables have RLS enabled. Public and signed-in clients have read-only access; direct mutation is revoked from `anon` and `authenticated`. Server/service-role writers remain responsible for validated ingestion and promotion.

## Seeded external sources

1. `DTR-SRC-THALESIAN-CUNEIFORMBASE-400M` — Hugging Face `Thalesian/cuneiformBase-400m`; Apache-2.0; translation/transliteration reference for Akkadian, Sumerian, Hittite, Linear B, limited Elamite, English, and German. Model output is a hypothesis generator, never primary-source authority.
2. `DTR-SRC-FOLKMOTIF-270` — Hugging Face `Aragoner/folkmotif`; CC BY 4.0; 270-row cultural-bias/control benchmark.
3. `DTR-SRC-CCRA` — Crop Circle Research Archive; federated link reference; CCRA Reference retained as a deduplication key.
4. `DTR-SRC-CROP-CIRCLE-CENTER` — Crop Circle Center; current sightings/archive feed; images remain link-first where rights are unclear.
5. `DTR-SRC-CROPDECODER` — Decoding the Codes / CropDecoder; searchable map/database reference; source claims such as node-status labels require independent validation.
6. `DTR-SRC-ICCRA-USA` — ICCRA USA formation reports; historical regional source.
7. `DTR-SRC-CROP-CIRCLE-CONNECTOR` — public Crop Circle Connector report surface; member-only picture archives must never be bypassed or mirrored.
8. `DTR-SRC-ZENODO-20979174` — June 27, 2026 crop-circle geometry technical note; stored as a hypothesis/test artifact, not verified evidence of formation origin.

## Seeded source records

- `DTR-REC-MODEL-CUNEIFORMBASE-400M-20260220`
- `DTR-REC-FOLKMOTIF-270-20260808`
- `DTR-REC-CCC-UK20260804-A`
- `DTR-REC-ZENODO-20979174-V3`

The August 4, 2026 Wiltshire Crop Circle Center report is canonically represented as `DTR-CC-20260804-WILTSHIRE-001`, classified `SOURCE_REPORTED` with origin `ORIGIN_UNRESOLVED`. Exact location and image authorship remain unknown; no origin claim is promoted.

## Crop-circle evidence classes

Evidence and origin remain separate dimensions. A formation can have reproducible geometry while its origin remains unresolved; a confirmed human-made formation can still be mathematically complex.

Evidence classes include `OBSERVED_FORMATION`, `SOURCE_REPORTED`, `FIELD_SURVEYED`, `ANALYSIS_REPRODUCED`, `ENCODING_HYPOTHESIS`, `ENCODING_REJECTED`, and `SPECULATION`.

Origin classes include `HUMAN_MADE_CONFIRMED`, `HUMAN_MADE_LIKELY`, `ORIGIN_UNRESOLVED`, and `UNKNOWN`.

## Analysis gate

No binary/textual decoding is eligible for promotion unless the encoding rule is explicit or preregistered, reproducible, statistically stronger than plausible arbitrary mappings, and survives negative controls. Controls include documented human-made formations, synthetic/randomized geometry, center-pivot agricultural imagery, and unrelated glyph/sacred-geometry imagery.

## Verification

Live verification immediately after seeding returned:

- external sources: 8
- external records: 4
- canonical crop formations: 1
- crop source links: 1
- analysis runs: 0

Supabase security and performance advisors were run after the schema write. Two missing foreign-key indexes introduced by the new layer were added. Existing unrelated advisor warnings remain tracked separately, including prior CP8 `SECURITY DEFINER` RPC exposure and Moltbook tables with RLS but no policies.

## Authority boundary

Registry inclusion means **available for investigation**, not **true**. No external archive, model, paper, AI output, or source label bypasses CP8 evidence, identity, challenge, receipt, replication, and human-governance gates.
