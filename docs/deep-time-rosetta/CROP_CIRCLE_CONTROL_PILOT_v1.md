# Deep-Time Rosetta — Crop Circle Control Pilot v1

Status: **RECORDED / PILOT / NO ORIGIN PROMOTION**  
Date: 2026-08-19  
Protocol: `DTR-CC-BLIND-GEOMETRY-PILOT-V1`

## Purpose

Test whether basic published geometric complexity separates documented human-made formations from formations whose origin remains unresolved. This is a control experiment, not an origin classifier.

## Assimilated prior art

Known-human controls:

- **Winton, New Zealand (7 Mar 1998)** — maker/archive record says three people made the ~300 ft formation at night in under four hours for NBC; 103 flattened circles plus a standing Mandelbrot.
- **HTV Beckhampton (28 Jul 2001)** — Circlemakers' own record says John Lundberg, Rod Dickinson, and Wil Russell built a 240 ft, eight-fold, 178-element formation in about four hours for HTV West.
- **BBC Milk Hill (26 Jul 1998)** — archive field report identifies the BBC commission and makers; ~190 ft and more than 100 circles. It is retained as a calibration control but excluded from the complete-case distance pilot because exact count/symmetry are not available.

Unresolved comparison formations:

- **Windmill Hill (29 Jul 1996)** — 194 circles, three-arm spiral, wheat. The archive contains conflicting span estimates (>500 ft in the geometry description; at least 1000 ft in the field report), so the pilot freezes a conservative 500 ft lower-bound value.
- **Milk Hill (14 Aug 2001)** — 409 circles, six-armed Julia-set description, approximately 900 ft in the archived reporting.
- **Crabwood (15 Aug 2002)** — raster-like face plus circular coded disc. It is excluded from circle-family geometry distance because its representation is qualitatively different and is instead audited as an encoding case.

Geometry reconstruction prior art from Zef Damen is registered as a reference method, including its explicit warning that perspective distortion limits geometry recovered from aerial photographs.

## Frozen pilot

Complete-case sample: Winton 1998, HTV 2001, Windmill Hill 1996, Milk Hill 2001 (`n=4`).

Spec A features:

1. `log1p(element_count)`
2. `log1p(span_ft)`
3. symmetry order
4. recursive/multiscale indicator

Spec B removes symmetry as a sensitivity check because Winton's order is source-derived/inferred rather than a canonical field measurement.

Both specs z-score columns across the pilot and use Euclidean distance. Origin labels are not used in distance calculation; they are revealed only after the matrix is produced. This is **not called preregistered**, because the archival origins were known during sample assembly.

## Result

The same-origin nearest-neighbor rate is **50%** in both specifications.

The closest pair in both specifications is:

`Winton 1998 (HUMAN_MADE_CONFIRMED) ↔ Windmill Hill 1996 (ORIGIN_UNRESOLVED)`

The exact small-sample label-permutation checks do not show reliable origin separation (`p=2/3` for Spec A; `p=1/3` for Spec B).

**Interpretation:** this pilot provides no support for using geometric complexity, scale, symmetry, or fractal/multiscale appearance by themselves as evidence of non-human origin. A documented human-made formation can be geometrically closer to an unresolved formation than to another human-made control.

This result is deliberately `INCONCLUSIVE` rather than a claim that all formations are human-made. The sample is tiny and uses archived metadata/reconstructions rather than rectified raw-image measurements.

## Crabwood ASCII audit

A separate audit checks the binary transcription printed in the archived Crabwood report.

- 150 ordinary 8-bit chunks were checked.
- Those chunks decode to the text displayed in the source.
- One reported segment is `10101010110`, which is **11 bits**, equals decimal **1366**, and therefore breaks ordinary 8-bit ASCII framing.

Outcome: `PASS_INTERNAL_TRANSCRIPTION_WITH_ANOMALY`.

This validates only the arithmetic of the **published transcription**. It does **not** independently validate the mapping from crop marks to bits, the authenticity of a message, its authorship, or the formation's origin.

## CP8 consequence

The next image-based phase must use copyright-permitted or link-referenced overhead imagery with rectification metadata and must include the known-human controls. A proposed decoder is rejected if it finds comparable “special” structure in the human-made controls or randomized/synthetic controls.

Canonical backend: Supabase `AISquad` (`ecenvlwyenpakrxfuqup`).  
GitHub implementation: `dbottrader/Holbrook-CP8-HHC`, PR #25.
