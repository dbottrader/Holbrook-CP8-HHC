# Deploy ASIN-NCEA Evidence Harness v0.1 to Hugging Face

The package in this directory is ready to become the root of a Hugging Face Gradio Space.

## Recommended Space identity

```text
owner: Dennis Christie / dbottrader
space_name: asin-ncea-evidence-harness-v0-1
sdk: Gradio
hardware: CPU Basic
visibility: Public or Private at operator discretion
```

## Files to place at the Space repository root

```text
README.md
app.py
requirements.txt
SPACE_MANIFEST.json
```

## Web deployment path

1. Create a new Hugging Face Space using the Gradio SDK.
2. Copy the four files above from this directory into the Space repository root.
3. Commit the files and allow the Space to build.
4. Run the interface once and preserve the emitted JSON receipt.
5. Record the Space URL and commit SHA in the artifact registry.

## Required boundary after deployment

```text
status: PASS_WITH_HOLD
evidence_level: E3_LOCAL_INTEGRATION
promotion_verdict: HOLD
witness_class: MACHINE_EXECUTION_UNATTESTED
runtime_scope: PUBLIC_DEMO_SMOKE_TEST_ONLY
```

A successful Space build proves only that the public demo package executes in the Hugging Face runtime. It does not establish independent reproduction, security certification, token authority, or kernel promotion.
