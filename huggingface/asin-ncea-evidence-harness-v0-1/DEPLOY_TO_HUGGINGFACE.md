# Deploy ASIN-NCEA Evidence Harness v0.1 to Hugging Face

The package in this directory is ready to become the root of a Hugging Face Gradio Space.

## Publication identity

```text
owner: Denniscp8222
space_name: asin-ncea-evidence-harness-v0-1
sdk: Gradio
hardware: CPU Basic
visibility: Public
canonical_source: https://github.com/dbottrader/Holbrook-CP8-HHC
```

Hugging Face is a distribution mirror. GitHub remains the canonical source and provenance surface.

## Automated publication workaround

The repository workflow `.github/workflows/publish-hugging-face-space.yml`:

1. validates the package on pull requests;
2. permits publication only through a manual dispatch from `refs/heads/main` with the `publish` checkbox enabled;
3. pins GitHub actions to immutable full commit SHAs;
4. serializes mutation by target Space rather than by source ref;
5. exposes `HF_TOKEN` only to the single publish-and-verify step;
6. creates the Space if it does not exist;
7. uploads only `README.md`, `app.py`, `requirements.txt`, `SPACE_MANIFEST.json`, and a generated `DEPLOYMENT_RECEIPT.json`;
8. records the exact GitHub source commit and workflow run in the in-mirror deployment receipt.

One repository secret is required:

```text
HF_TOKEN = Hugging Face user access token with write permission
```

Store the token in GitHub Actions secrets. Never commit it or paste it into an issue, pull request, log, or chat.

## Hardening receipt

The workflow currently pins:

```text
actions/checkout@11d5960a326750d5838078e36cf38b85af677262  # v4.4.0
actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065  # v5.6.0
```

The validation job asserts both pin counts, the main-ref guard, the target-wide concurrency group, the corrected upload commit message, and step-scoped secret placement.

## Remaining post-upload receipt gate

The in-mirror receipt is generated before upload, so it cannot contain the resulting Hugging Face commit OID without a second commit. Before claiming byte-for-byte external reproduction, add a post-upload workflow receipt that records the resulting Hugging Face commit and verifies the expected remote file hashes. Until then, publication remains `PASS_WITH_HOLD`; a successful build or `hf spaces info` response is not full content attestation.

## Manual fallback

Create the Space as Gradio/CPU Basic and place these files at its root:

```text
README.md
app.py
requirements.txt
SPACE_MANIFEST.json
```

## Required boundary after deployment

```text
status: PASS_WITH_HOLD
evidence_level: E3_LOCAL_INTEGRATION
promotion_verdict: HOLD
witness_class: MACHINE_EXECUTION_UNATTESTED
runtime_scope: PUBLIC_DEMO_SMOKE_TEST_ONLY
```

A successful build proves only that the public demo executes in the Hugging Face runtime. It does not establish independent reproduction, security certification, token authority, or kernel promotion.
