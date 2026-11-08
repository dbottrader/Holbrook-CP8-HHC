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

A second online worker verifies the reply only when both workers advertise the same known model digest. A missing digest is stored as `unpinned` and is not eligible. Two unknown digests do not match. Agreement writes one canon-v1 `inference_receipt` (Ed25519 over the GPU-MESH WorkClaim digest, SHA-256 standing in for keccak256, `chainId` 0). The receipt records the agent commit, the runtime name and version, and the pinned options (`temperature` 0, `top_k` 1, `top_p` 1, `repeat_penalty` 1, `num_ctx` 2048, and the hub seed). A further distinct worker must agree before the job is pending for Base Sepolia. The worker cannot verify its own job. Mesh credits stay in hold until the worker is 7 days old and has 3 verified jobs. The edge function does not hold the deployer key. The box settler in `gpu-mesh/settler/settle.py` submits `Settlement.settle`.

If no volunteer is online, the function calls Groq when the `GROQ_API_KEY` secret is set, and signs a canon-v1 `groq_inference_receipt` with amount 0. That kind is not a worker award. If the secret is unset, the response is HTTP 503 and the message is `no workers online`.

Deploy, from a Supabase login that can reach project `ecenvlwyenpakrxfuqup`. Apply the digest-pin migration before the function that writes the new columns:

```bash
supabase db query --linked < supabase/migrations/20261108170000_gpu_mesh_digest_pin.sql
supabase functions deploy gpu-mesh --project-ref ecenvlwyenpakrxfuqup --no-verify-jwt
supabase secrets set GROQ_API_KEY=... --project-ref ecenvlwyenpakrxfuqup
```

The function deploy uploads this directory. The files it loads are:

```text
supabase/functions/gpu-mesh/index.ts
supabase/functions/gpu-mesh/protocol.mjs
supabase/functions/gpu-mesh/supabase_store.mjs
supabase/functions/gpu-mesh/canon.mjs
supabase/functions/gpu-mesh/secrets.mjs
```

`GPU_MESH_SIGNING_KEY` (64 hex characters, Ed25519 seed) pins the receipt key. `GPU_MESH_SETTLER_TOKEN` authenticates the box settler from the function environment. The Vault name is `gpu_mesh_settler_token`. The deployer key stays on the operator machine and is not a Supabase secret. HHC recorded here is a utility credit for verified contribution. Settlement is HHCW `0x24a7B22fC54DbFD117023535eBeCf660B76fdb5d` and Settlement `0xdfFE664d23E30Baff7Ad4d16831aD625Cc90bcCA` on Base Sepolia. Promotion stays HOLD.
