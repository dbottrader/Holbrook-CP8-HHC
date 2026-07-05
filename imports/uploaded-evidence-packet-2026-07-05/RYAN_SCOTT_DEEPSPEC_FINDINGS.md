# Ryan Scott / DeepSpec Hardening Findings

## Purpose

This file records the DeepSpec hardening thread as an evidence-bound collaboration artifact.

## Collaborator Attribution

Ryan Scott is credited here as collaborator / critic / adversarial reviewer for the DeepSpec security and production-readiness thread.

## Finding Class

`E1_REVIEW_AND_PATCH_PROPOSAL`

This file does not claim that patches have been applied to upstream DeepSpec. It records the review logic and the next required receipt-producing actions.

## Core Findings

### 1. torch.load deserialization risk

Finding: `torch.load(..., weights_only=False)` creates unnecessary deserialization risk when loading checkpoint state.

Recommended direction:

```python
checkpoint = torch.load(state_path, map_location="cpu", weights_only=True)
```

If custom classes are genuinely required, use an explicit allowlist rather than reverting to unsafe global deserialization.

### 2. Checkpoint lifecycle / rotation

Finding: checkpoint directories can grow without bounded retention.

Recommended direction:

- implement `cleanup_old_checkpoints()`;
- delete oldest `step_N` directories beyond `max_checkpoints`;
- protect the target of `step_latest`;
- emit deletion receipt / log entry.

### 3. CP8 provenance wrapper

Finding: provenance instrumentation should remain outside the DeepSpec training/evaluation core unless a narrow patch is strictly required.

Recommended wrapper pattern:

```bash
python -m cp8.wrap -- <original deepspec command>
```

Wrapper duties:

- hash configs;
- hash checkpoint inputs/outputs;
- capture torch/CUDA environment;
- capture git commit if available;
- write JSON manifest;
- write lightweight HTML dashboard;
- exit with wrapped command's real exit code.

### 4. Evidence boundary

A response claiming that patches ran cleanly is not enough by itself. Promotion requires:

- actual patch files;
- command lines;
- stdout/stderr logs;
- SHA-256 inventory;
- manifest receipt;
- commit hash;
- CI or independent reproduction for E3+.

## Current Status

- `DeepSpec_Engineering_Review_with_Commentary.pdf` is registered as `E1_REVIEW_ARTIFACT`.
- `Kimi_Agent_DeepSpec GitHub Repository(1).zip` is registered as `E1_SOURCE_REVIEW_PACKET`.
- `Kimi_Agent_DeepSpec Critique Summary(7).zip` is registered as `E1_E2_CANDIDATE_CODE_PACKET`.
- Actual source patch files for `ckpt_manager.py`, checkpoint rotation, and `cp8.wrap` still require extraction or recreation before E2 promotion.

## Recommended Next Action

Create a dedicated patch path:

```text
patches/deepspec/cp8-wrapper/
patches/deepspec/checkpoint-security/
receipts/deepspec/2026-07-05/
```

Then run tests and generate receipt manifests before promoting any DeepSpec hardening claim.
