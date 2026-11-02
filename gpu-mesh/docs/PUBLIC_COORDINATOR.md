# Public GPU mesh coordinator

A stranger can join and call free inference without an account Dennis creates.

Coordinator:

```text
https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/gpu-mesh
```

One command (llama.cpp, no invite):

```bash
curl -fsSL https://raw.githubusercontent.com/dbottrader/Holbrook-CP8-HHC/main/gpu-mesh/deploy/join/install.sh | bash
```

The published open invite is `open`. It is not required. Registration is limited to 10 new workers per hour per address, and the cohort cap is 64. Pass `--invite open` only if a future cohort turns invite mode on.

The edge function `gpu-mesh` speaks the worker calls in `gpumesh_node/agent.py`: register, heartbeat, claim, chunks, result, and fail. `POST /v1/chat/completions` is OpenAI-shaped. `max_tokens` is capped at 256 and prompts at 4000 characters. Anonymous callers are limited to 20 requests a minute.

A second online worker verifies the reply. Agreement writes one canon-v1 `inference_receipt` (Ed25519 over the GPU-MESH WorkClaim digest, SHA-256 standing in for keccak256, `chainId` 0). That is the record pull request 46 consumes when `verifier_decision` is `agree` and `amount` is a positive integer. The simulated credit stays in hold until the worker is 7 days old and has 3 verified jobs. Nothing is minted.

If no volunteer is online, the function calls Groq when the `GROQ_API_KEY` secret is set, and signs a canon-v1 `groq_inference_receipt` with amount 0. That kind is not a worker award. If the secret is unset, the response is HTTP 503 and the message is `no workers online`.

Deploy, from a Supabase login that can reach project `ecenvlwyenpakrxfuqup`:

```bash
supabase db query --linked < supabase/migrations/20261102143000_gpu_mesh_coordinator.sql
supabase functions deploy gpu-mesh --project-ref ecenvlwyenpakrxfuqup --no-verify-jwt
supabase secrets set GROQ_API_KEY=... --project-ref ecenvlwyenpakrxfuqup
```

`GPU_MESH_SIGNING_KEY` (64 hex characters, Ed25519 seed) pins the receipt key. If it is unset, the function generates one and stores it in `gpumesh_signer`, which anon cannot read. HHC recorded here is a simulated utility credit. Promotion stays HOLD.
