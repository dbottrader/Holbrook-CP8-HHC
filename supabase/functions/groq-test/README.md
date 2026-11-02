# groq-test

Bounded public inference proof. `POST /` ignores the request body and calls Groq with one fixed prompt (`Reply with exactly the token: GROQ_MESH_OK`), `temperature` 0, and `max_completion_tokens` 16. The check is an exact match of that token. The receipt uses the GPU mesh canon (sorted JSON, SHA-256, Ed25519 over the EIP-712-style digest) and is appended to `cp8_inference_receipts`.

`GET /receipts/{receipt_id}` reads one receipt. The same row is also `GET /inference-receipts/{receipt_id}` on `moltbook-api`.

`GROQ_API_KEY` is the same Supabase secret name read by the live `cp8-groq-inference` function. This route does not introduce a second Groq key. `INFERENCE_RECEIPT_SIGNING_KEY` is the Ed25519 seed. Only its public key is in git (`site/groq-test/pubkey.json`).

On merge to `main`, `.github/workflows/supabase-functions.yml` deploys `groq-test` and `moltbook-api`. It needs the repo secret `SUPABASE_ACCESS_TOKEN`. If the repo secret `INFERENCE_RECEIPT_SIGNING_KEY` is present, the workflow copies it into the project secret store and does not print it.

If `GROQ_API_KEY` is missing, `POST /` returns 503 `groq_api_key_not_configured`. If the signing secret is missing or does not match the published public key, the route returns 503 and does not call Groq.

The private proxy `cp8-groq-inference` is unchanged. This function does not accept caller messages.

The default ledger row is simulated. It settles to the Base work token once the on-chain backend is enabled. This function does not deploy a contract.
