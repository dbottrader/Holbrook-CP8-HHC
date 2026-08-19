# Deep-Time Rosetta — External Ingestion Registry v1

Status: **LIVE / FEDERATED / RECEIPT-BOUND**  
Date: 2026-08-19  
Canonical backend: Supabase AISquad (`ecenvlwyenpakrxfuqup`)  
Reproducibility branch: `agent/dtr-ingestion-sync-20260819`

## Purpose and authority boundary

This registry makes external ancient-language AI resources, crop-circle archives, public datasets, papers, and future archaeology sources reusable inside ASIN-HHC / CP8 without collapsing provenance or treating source claims as verified conclusions.

`SOURCE -> IMMUTABLE SOURCE RECORD -> CANONICAL ENTITY -> DERIVED MEASUREMENT -> ANALYSIS -> CHALLENGE / REPLICATION -> CP8 CLAIM`

Registry inclusion means **available for investigation**, not **proven true**. Raw source observation, canonical entity, derived measurement, analysis, replication, and conclusion remain separate.

## Supabase federation layer

The live backend contains:

- `cp8_external_sources`
- `cp8_external_records`
- `cp8_crop_formations`
- `cp8_crop_formation_sources`
- `cp8_analysis_runs`

All five tables have RLS enabled. `anon` and `authenticated` clients may read but cannot directly mutate the registry; validated ingestion remains server-controlled.

## Current verified state

After crop-circle control-batch assimilation:

- external sources: **12**
- immutable external records: **12**
- canonical crop formations: **7**
- formation/source matches: **8**
- analysis runs: **5**

## Ancient-language / cross-cultural controls

### Thalesian cuneiformBase-400m

Apache-2.0 reference model for Akkadian, Sumerian, Hittite, Linear B, limited Elamite, English, and German. It is a hypothesis generator, not primary-source authority; promoted results require primary-corpus verification.

### FolkMotif-270

CC BY 4.0 cross-cultural control benchmark. It is used to detect cultural-readout/decoder bias, not as a common-origin truth table.

## Crop-circle source federation

Sources remain separate so disagreements and copyright restrictions are visible:

1. Crop Circle Research Archive — research/archive index; link-first.
2. Crop Circle Center — current sightings/archive stream; link-first.
3. CropDecoder — searchable secondary database; anomaly labels remain source claims.
4. ICCRA USA — historical regional reporting.
5. Crop Circle Connector — public report metadata only; member-only picture archives are not bypassed.
6. Crop Circle Archives — historical formation/report source used in the control batch.
7. Circlemakers — primary maker/commission source used for known-human controls.
8. Lucy Pringle photograph library — date/location/photo corroboration; photographs remain link-only without permission.
9. Zef Damen reconstructions — geometry prior art with explicit perspective-distortion limitations.
10. Zenodo 20979174 — external technical-note/hypothesis artifact requiring replication.

## Crop-circle control batch v1

### Known-human controls

- `DTR-CC-19980307-WINTON-001` — NBC commissioned; `HUMAN_MADE_CONFIRMED`.
- `DTR-CC-20010728-BECKHAMPTON-HTV-001` — HTV commissioned; `HUMAN_MADE_CONFIRMED`.
- `DTR-CC-19980726-MILKHILL-BBC-001` — BBC Countryfile commissioned; `HUMAN_MADE_CONFIRMED`. Retained as a calibration control but excluded from the complete-case geometry distance matrix because exact features are incomplete.

### Unresolved comparisons

- `DTR-CC-19960729-WINDMILLHILL-001` — `ORIGIN_UNRESOLVED`.
- `DTR-CC-20010814-MILKHILL-409-001` — `ORIGIN_UNRESOLVED`.
- `DTR-CC-20020815-CRABWOOD-001` — `ORIGIN_UNRESOLVED`; handled as a separate encoding audit because its raster/disc representation is not directly comparable to the circle-family geometry sample.

## Geometry pilot

Protocol: `DTR-CC-BLIND-GEOMETRY-PILOT-V1`  
Group result hash: `a2ec1914c7b2a2a6eaf47f204f933c7c5d06e28632a036c0fe6d23680d9ac13a`

Complete-case sample: Winton 1998, HTV 2001, Windmill Hill 1996, Milk Hill 2001 (`n=4`). Published metadata were converted to frozen feature vectors. Origin labels were excluded from the distance computation and revealed afterward. The run is **not called preregistered**, because formation origins were known during sample assembly.

The closest pair in both feature specifications was:

**Winton 1998 (`HUMAN_MADE_CONFIRMED`) ↔ Windmill Hill 1996 (`ORIGIN_UNRESOLVED`)**.

Same-origin nearest-neighbor accuracy was 50%. Exact tiny-sample label-permutation checks did not show reliable separation (`p=2/3` for Spec A; `p=1/3` for Spec B).

Outcome: **INCONCLUSIVE — NO RELIABLE GEOMETRY-ONLY ORIGIN SEPARATION.**

Operational consequence: complexity, scale, symmetry, and fractal/multiscale appearance are not origin evidence by themselves. Future image decoders must run against known-human and randomized/synthetic controls under the same frozen pipeline.

## Crabwood ASCII audit

Analysis: `DTR-AN-CC-CRABWOOD-ASCII-V1`  
Result hash: `f599d9a958ff012758352c46864911aef4291f5314c0c5c3da3e05c84d451f8e`

The 150 ordinary 8-bit chunks in the archived published transcription decode consistently to the text displayed by the source. One quoted segment, `10101010110`, is 11 bits (decimal 1366), so it breaks ordinary 8-bit ASCII framing.

Outcome: **PASS_INTERNAL_TRANSCRIPTION_WITH_ANOMALY.**

This validates only the arithmetic of the published transcription. It does not independently validate crop-mark-to-bit extraction, message authenticity, authorship, or origin.

## Batch receipt

- receipt_id: `b3a52bd5-3aa2-498c-8bce-41f62c6065ec`
- payload_hash: `5ed5025500d6b5730d78afc21ae5cc8712d32190b406554cc7eb675074a72db9`
- receipt_hash: `fc231d2e3ee31c7ce039e27ee0e744d79dca9ad73f06de971a95be924ebacfa1`
- analysis runs bound: 5

## Analysis gate

No binary/textual decoding is eligible for promotion unless its encoding rule is explicit or preregistered, reproducible, statistically stronger than plausible arbitrary mappings, and survives negative controls. Controls include documented human-made formations, synthetic/randomized geometry, ordinary center-pivot agricultural imagery, and unrelated glyph/sacred-geometry imagery.

## Remaining synchronization edge

Harmony Core Continuity / Replit must consume Supabase as canonical state. The Replit connector was disabled during the attempted write, so that edge remains explicitly `BLOCKED_CONNECTOR_DISABLED` rather than being reported as synchronized.
