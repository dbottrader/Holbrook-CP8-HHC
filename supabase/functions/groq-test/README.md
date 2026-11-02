# groq-test

Bounded public inference proof. `POST /` ignores the request body and calls Groq with one fixed prompt (`Reply with exactly the token: GROQ_MESH_OK`), `temperature` 0, and `max_completion_tokens` 16. The check is an exact match of that token. The receipt uses the GPU mesh canon (sorted JSON, SHA-256, Ed25519 over the EIP-712-style digest) and is appended to `cp8_inference_receipts`.

`GET /receipts/{receipt_id}` reads one receipt. The same row is also `GET /inference-receipts/{receipt_id}` on `moltbook-api`.

Secrets, set in the Supabase project and never committed:

```bash
supabase secrets set GROQ_API_KEY="$GROQ_API_KEY" INFERENCE_RECEIPT_SIGNING_KEY="$INFERENCE_RECEIPT_SIGNING_KEY" --project-ref ecenvlwyenpakrxfuqup
supabase functions deploy groq-test --project-ref ecenvlwyenpakrxfuqup --no-verify-jwt
```

If `GROQ_API_KEY` is missing, `POST /` returns 503 `groq_api_key_not_configured`. If the signing secret is missing or does not match the published public key in `site/groq-test/pubkey.json`, the route returns 503 and does not call Groq... it checks the signing key before the rate limit, and Groq only after the key is present.

The private proxy `cp8-groq-inference` is unchanged. This function does not accept caller messages.

The default ledger row is simulated. It settles to the Base work token once the on-chain backend is enabled. This function does not deploy a contract.
