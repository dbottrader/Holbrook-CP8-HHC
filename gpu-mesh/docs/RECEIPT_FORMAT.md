# Inference receipt format

A Groq fallback receipt and a volunteer receipt use the same bytes. The public hub settles a verified worker receipt as HHCW on Base Sepolia after two distinct verifiers. Settlement `0xdfFE664d23E30Baff7Ad4d16831aD625Cc90bcCA`, token `0x24a7B22fC54DbFD117023535eBeCf660B76fdb5d`. The box settler holds the key. HHC is a utility credit for verified contribution. It is not sold and it pays no return.

A self-hosted Python process defaults to `GPU_MESH_LEDGER_BACKEND=simulated` and writes the local chain. `GPU_MESH_LEDGER_BACKEND=onchain` in that process does not submit a transaction and does not open a socket. That switch is not the live settler.

## Fields

| Field | Role |
| --- | --- |
| `actor`, `kind`, `payload`, `prev_hash`, `seq`, `ts` | The preimage. `payload` is itself a canonical JSON string. `ts` is Unix milliseconds. `seq` starts at 1. The first `prev_hash` is 64 zero hex characters. |
| `body_json` | Canonical JSON of those six fields. |
| `hash` | SHA-256 hex of the UTF-8 `body_json`. |
| `canon` | `v1`. |
| `amount` | Integer. Groq fallback receipts use `0` until a settlement attestation assigns a value. `credits` inside the payload matches `amount`. |
| `signature` | Ed25519 hex over the 32-byte typed digest, not over `hash`. |
| `signer` | Raw Ed25519 public key, hex. The live Groq test key is derived at runtime and served at `GET /functions/v1/groq-test/.well-known/inference-receipt-key.json`. |
| `typed_data` | EIP-712-style document. Domain name `GPU-MESH`, version `1`, `chainId` 0, zero `verifyingContract`. The hash function is SHA-256 standing in for keccak256. `chainId` 0 is not a network and this digest is not a transaction. |

Canonical JSON is `json.dumps` with `sort_keys=True`, `separators=(",", ":")`, and `ensure_ascii=True`. The same function is `canonDumps` in `supabase/functions/groq-test/receipt.mjs` and `site/groq-test/receipt.js` (those two files are copies).

## Claim

The signature covers `digest_for` in `gpu-mesh/gpumesh/typed.py`:

```text
WorkClaim(string actor,int256 amount,string kind,uint256 ledgerSeq,bytes32 payloadHash,bytes32 prevHash,string settlementId,uint256 ts,string verifierIds,string workerId)
```

`payloadHash` is SHA-256 of the payload string. `prevHash` is the 32-byte previous receipt hash.

Groq fallback payload schema is `gpumesh.groq_fallback.v1`. It records `worker_id` `groq:<model>`, `verifier_ids` (`exact-match` or the second model id), `verification_method`, `output_hash`, `prompt_sha256`, `request_id`, integer token counts, `state` `OBSERVED`, and `promotion` `HOLD`. The prompt text is not in the public row.

A volunteer `gpumesh.execution.v1` receipt and a `gpumesh.verification.v1` receipt also record the run that produced the text: `agent_commit` (git commit, or the package version), `runtime_name`, `runtime_version`, `model_digest`, `temperature`, `top_k`, `top_p`, `seed`, `num_ctx`, and `repeat_penalty`. Deterministic jobs pin `top_p` to 1, `repeat_penalty` to 1, and `num_ctx` to 2048. A verification receipt repeats the parent run as `parent_agent_commit`, `parent_runtime_name`, `parent_runtime_version`, `parent_model_digest`, and `parent_` plus each generation field, so a wording mismatch can be traced to a different commit, runtime, or digest. `reported_generation` is the option object the worker said it sent. A digest of `unpinned`, or a missing digest, is not a match.

A checker is paid the same mesh credit for `agree` and `disagree_deterministic` (`agreement_bonus` is 0). A disagreement does not mint the worker. The hub holds that payout and queues one tiebreaker. The worker output hash stays sealed until the verifier has committed `sha256` of its own output. Receipts keep four digests in separate fields: `input_digest` (canonical messages), `manifest_digest` (Ollama manifest), `output_digest` (output text), and `weights_digest` (GGUF sha256). `GET /api/evidence/{job_id}` returns the job, receipts, verdicts, tx hash, and the decoded `Settled` log when the transaction is on Base Sepolia.

## Where a row lives

- The self-hosted coordinator appends through `LedgerBackend`. `simulated` writes the local chain. `onchain` in that process refuses without opening a socket. The public hub's box settler is the process that submits `Settlement.settle`.
- The public test appends the same shape to `public.cp8_inference_receipts` on project `ecenvlwyenpakrxfuqup`. Read it with `GET /inference-receipts/{receipt_id}` on `moltbook-api` or `GET /receipts/{receipt_id}` on `groq-test`.

`cp8_moltbook_receipt_chain` stays the bounty HMAC chain. Inference proofs do not invent a bounty id to fit that table.

## Checks

1. Recompute `body_json` and compare SHA-256 to `hash`.
2. Recompute the typed digest from `typed_data.message`.
3. Verify the Ed25519 signature with the published public key.

The Groq test page does that in the browser. `gpumesh-verify-ledger` still replays a coordinator export.
