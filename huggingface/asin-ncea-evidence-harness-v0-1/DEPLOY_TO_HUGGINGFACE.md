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
2. runs publication only through a manual dispatch with the `publish` checkbox enabled;
3. creates the Space if it does not exist;
4. uploads only `README.md`, `app.py`, `requirements.txt`, `SPACE_MANIFEST.json`, and a generated `DEPLOYMENT_RECEIPT.json`;
5. records the exact GitHub source commit and workflow run in the deployment receipt.

One repository secret is required:

```text
HF_TOKEN = Hugging Face user access token with write permission
```

Store the token in GitHub Actions secrets. Never commit it or paste it into an issue, pull request, log, or chat.

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
