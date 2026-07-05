# Uploaded Evidence Packet — 2026-07-05

This folder registers and stages the uploaded CP8 / ASIN-HHC / DeepSpec evidence packet.

## Purpose

The packet combines:

1. DeepSpec engineering review material.
2. Ryan Scott / Kimi critique and hardening material.
3. CP8/CP9 geometric transformer research artifacts.
4. Cathedral / Delta717 / CP8 conformance-style source packets.
5. Symbolic/status logs that are useful as chronology but not engineering proof.

## Handling Rule

Large binary originals are **registered by SHA-256** in this folder and remain:

`HASH_REGISTERED / BINARY_UPLOAD_PENDING`

until they are uploaded through a binary-safe GitHub path such as release assets, Git LFS, or a local git commit.

Text/source material extracted from ZIP files is staged when it is useful for review, provenance, or reproducibility.

## Files Added in This Pass

- `SHA256SUMS.txt` — hashes of uploaded originals.
- `EVIDENCE_REGISTRY.json` — evidence-tier registry and destination map.
- `ZIP_CONTENTS_SUMMARY.md` — file inventory summary for uploaded ZIP packets.
- `RYAN_SCOTT_DEEPSPEC_FINDINGS.md` — distilled DeepSpec/Ryan hardening record.

## Current Evidence Status

This is a staging and registration pass, not a production promotion.

- DeepSpec review claims remain review-level until tied to source diffs, test logs, and receipts.
- CP8/CP9 geometric claims remain research-artifact level until training logs, checkpoints, ablations, and independent reproduction are attached.
- Symbolic/status logs remain chronology and should not be treated as deployment proof.

## Next Steps

1. Upload binary originals through a binary-safe path.
2. Extract selected source files from ZIPs into first-class repo paths after dedupe.
3. Run test suites from extracted packages.
4. Generate receipts over test outputs.
5. Promote only artifacts whose evidence tier is supported by receipts.
