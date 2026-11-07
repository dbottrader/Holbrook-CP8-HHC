# groq-test

Bounded public inference proof. `POST /` ignores the request body and calls Groq with one fixed prompt (`Reply with exactly the token: GROQ_MESH_OK`), `temperature` 0, and `max_completion_tokens` 16. The check is an exact match of that token. The receipt uses the GPU mesh canon (sorted JSON, SHA-256, Ed25519 over the EIP-712-style digest) and is appended to `cp8_inference_receipts`.

`GET /health` reports `groq_configured` and `signer_configured`. `GET /.well-known/inference-receipt-key.json` returns the Ed25519 public key derived from the signing seed. Neither route embeds a key from git.

Secrets, in order:

1. Function environment `GROQ_API_KEY` and `INFERENCE_RECEIPT_SIGNING_KEY`.
2. Vault names `groq_api_key` and `inference_receipt_signing_key`, read by `cp8_private.read_named_secret`. That function is `SECURITY DEFINER` and executable only by `service_role`.

`cp8-groq-inference` is a separate deployed function. It is not in this repository and does not share this code. It still reads `GROQ_API_KEY` and `CP8_GROQ_PROXY_TOKEN` from its own environment.

`GET /receipts/{receipt_id}` reads one receipt. The same row is also `GET /inference-receipts/{receipt_id}` on `moltbook-api`.

On a push to `main`, `.github/workflows/supabase-functions.yml` deploys the functions when the repo secret `SUPABASE_ACCESS_TOKEN` is set. If that secret is absent, the workflow skips. If `INFERENCE_RECEIPT_SIGNING_KEY` is also set, the workflow copies it into the project secret store and prints only the derived public key.

If the Groq key is missing, `POST /` returns 503 `groq_api_key_not_configured`. If the signing seed is missing or not a 32-byte Ed25519 seed, the route returns 503 and does not call Groq.

The default ledger row is simulated. It settles to the Base work token once the on-chain backend is enabled. This function does not deploy a contract.
