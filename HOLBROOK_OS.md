# Holbrook OS v0.2

A user-space governed AI runtime for bounded execution, policy gating, and replay-oriented provenance receipts.

## What changed

- SQLite receipt persistence
- read-only receipt API
- OpenAI-compatible chat-completions adapter
- deterministic null adapter for tests
- policy identity and policy hash in every receipt
- optional corpus hash
- receipt verification endpoint
- expanded test harness
- GitHub Actions test workflow

## Run

    docker compose up --build
    curl http://localhost:8000/health
    curl -X POST http://localhost:8000/run -H 'content-type: application/json' -d '{"prompt":"hello"}'

## CLI

    pip install -e .
    holbrook run "Explain the project architecture"
    holbrook verify receipt.json

## Model adapter

Set HOLBROOK_MODEL_URL to an OpenAI-compatible API base URL. HOLBROOK_MODEL selects the model and HOLBROOK_API_KEY supplies an optional bearer token.

## Evidence boundary

A valid receipt proves that the stored response hash matches the response in that receipt. It does not independently prove model truth, causal provenance, or scientific validity.

Promotion remains:

EXISTS -> EXECUTED -> REPRODUCED -> ESTABLISHED

No receipt means no promotion.
