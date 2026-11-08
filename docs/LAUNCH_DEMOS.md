# Launch demos

Five checks a stranger can run. Each one is independent of the others: a new shell, a new machine, or both. HHC is a utility credit for verified contribution. It is not sold and it pays no return.

Public coordinator:

```text
https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/gpu-mesh
```

Contracts on Base Sepolia (chain id 84532):

| What | Address |
| --- | --- |
| HHCW token | `0x24a7B22fC54DbFD117023535eBeCf660B76fdb5d` |
| Settlement | `0xdfFE664d23E30Baff7Ad4d16831aD625Cc90bcCA` |

The hub does not hold the deployer key. The box-side settler in `gpu-mesh/settler/settle.py` submits `Settlement.settle` after two distinct verifiers, neither of them the worker, have agreed. One mesh credit is 1000 HHCW units (900 to the worker, 50 to each verifier).

Set this once in each shell:

```bash
export COORD=https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/gpu-mesh
```

## (a) A stranger joins with one command

On a Linux or macOS machine with Docker. No account and no invite.

```bash
curl -fsSL https://raw.githubusercontent.com/dbottrader/Holbrook-CP8-HHC/main/gpu-mesh/deploy/join/install.sh | bash
```

Optional flags, still one command:

```bash
curl -fsSL https://raw.githubusercontent.com/dbottrader/Holbrook-CP8-HHC/main/gpu-mesh/deploy/join/install.sh | bash -s -- \
  --payout-address 0xYourEvmAddress \
  --gpu
```

`--cpu` forces the CPU fallback even when a GPU is visible. `--gpu` stops if no NVIDIA or AMD GPU is visible. Omit both and the installer detects the device.

What to check:

- The log line starts with `GPU_MESH_MODE:`.
- A machine with `nvidia-smi` prints `GPU mode cuda`, starts `ollama/ollama:0.12.6` with `--gpus all`, pulls a Qwen2.5 instruct tag sized to VRAM (`qwen2.5:7b-instruct` at 6144 MiB and above, `qwen2.5:3b-instruct` at 3072 MiB, smaller below that), and prints `ollama ps shows a GPU processor`.
- An AMD machine with `rocm-smi` or `/dev/kfd` uses `ollama/ollama:rocm` and passes `/dev/kfd` and `/dev/dri`.
- If `nvidia-smi` works and `nvidia-ctk` does not, the installer prints the NVIDIA Container Toolkit install commands and exits without starting the worker.
- No GPU, or `--cpu`, prints `CPU mode` and runs llama.cpp (`SmolLM2-360M-Instruct`) unless `--backend ollama` is set.
- `docker logs gpumesh-join` contains `GPU_MESH_MODE accelerator=` and `registered`.

## (b) The node registers, and /api/stats shows it

From any machine, after (a) has been running long enough to register:

```bash
curl -fsS "$COORD/api/stats"
```

What to check:

- `workers_registered` is at least 1 and `workers_online` counts the node while it heartbeats.
- `nodes` includes the machine name. On a GPU join, `accelerator` is `cuda` or `rocm`, `gpu_name` is the card, and `vram_mb` is greater than 0. A CPU join has `accelerator` `cpu` and `vram_mb` 0.
- `inference` runtime stays in `backend` (`ollama`, `llamacpp`, `vllm`, or `cpu`). `accelerator` is the hardware field and is not a replacement for `backend`.
- `ledger` is `base-sepolia`. `hhcw` and `settlement` are the addresses in the table above.

## (c) An open-weight model serves a request and returns a signed receipt

Ask for a model a live node advertises. List them first:

```bash
curl -fsS "$COORD/v1/models"
```

Then, with that id (the examples below match the installer defaults):

```bash
curl -fsS "$COORD/v1/chat/completions" \
  -H 'content-type: application/json' \
  -d '{"model":"qwen2.5:3b-instruct","messages":[{"role":"user","content":"Reply with exactly the token: MESH_OK"}],"temperature":0,"max_tokens":32}'
```

CPU llama.cpp nodes advertise `SmolLM2-360M-Instruct` instead. Use the id `/v1/models` returned. `mock-tiny` is the deterministic stub, not this demo.

What to check:

- HTTP 200 and `choices[0].message.content` is non-empty.
- `gpumesh.receipt.canon` is `v1`.
- `gpumesh.receipt.signature` and `gpumesh.receipt.signer` are present.
- `gpumesh.receipt.kind` is `inference_receipt` once a second worker has agreed. Until then the body may be the queued or completed job without a worker award. A single machine can still show a signed `node_register` receipt from `GET /api/receipts?limit=20`.
- Promotion in the payload stays `HOLD`. The credit is not a sale.

Save the completion if you want (d) to verify that exact receipt:

```bash
curl -fsS "$COORD/v1/chat/completions" \
  -H 'content-type: application/json' \
  -d '{"model":"qwen2.5:3b-instruct","messages":[{"role":"user","content":"Reply with exactly the token: MESH_OK"}],"temperature":0,"max_tokens":32}' \
  -o /tmp/mesh-completion.json
```

## (d) An independent machine verifies the receipt

On a second machine, clone the repo (or copy `supabase/functions/gpu-mesh/canon.mjs` and its imports; the file is self-contained). Do not use the worker's key, the settler key, or the hub's database.

```bash
curl -fsS "$COORD/.well-known/inference-receipt-key.json" -o /tmp/mesh-key.json
curl -fsS "$COORD/api/receipts?limit=20" -o /tmp/mesh-receipts.json
node --input-type=module <<'EOF'
import { readFileSync } from "node:fs";
import { verifyMeshReceipt } from "./supabase/functions/gpu-mesh/canon.mjs";

const key = JSON.parse(readFileSync("/tmp/mesh-key.json", "utf8"));
const body = JSON.parse(readFileSync("/tmp/mesh-receipts.json", "utf8"));
const rows = (body.receipts || []).filter((row) => row && row.signature && row.canon === "v1");
if (!rows.length) {
  console.error("no signed canon-v1 receipt in /api/receipts");
  process.exit(1);
}
let verified = 0;
for (const row of rows) {
  const check = await verifyMeshReceipt(row);
  if (!check.ok) {
    console.error(check.error);
    process.exit(1);
  }
  if (row.signer !== key.public_key_hex) {
    console.error("signer does not match the coordinator public key");
    process.exit(1);
  }
  verified += 1;
}
console.log(`verified ${verified} receipt(s) against ${key.public_key_hex}`);
EOF
```

Run that from the repository root so the import path resolves. What to check:

- The process prints `verified N receipt(s)` and exits 0.
- `public_key_hex` matches `signer` on each receipt and `signer_configured` in the key document is true.
- A changed byte in the receipt makes `verifyMeshReceipt` return `ok: false`. That is the check that the signature is over those bytes.

To verify the completion from (c) instead of the ledger page, pass `gpumesh.receipt` from `/tmp/mesh-completion.json` into `verifyMeshReceipt` the same way.

## (e) A Base Sepolia settlement transaction is confirmed

The settler has to have run on the operator box for a job that already had two distinct verifiers and payout addresses. This command only reads the hub.

```bash
curl -fsS "$COORD/api/receipts?limit=50" -o /tmp/mesh-receipts.json
python3 - <<'PY'
import json
rows = json.load(open("/tmp/mesh-receipts.json"))["receipts"]
found = [row for row in rows if row.get("settlement_tx_url")]
if not found:
    raise SystemExit("no settlement_tx_url yet; the job is still waiting on two verifiers or the settler")
for row in found:
    print(row.get("settlement_status"), row["settlement_tx_hash"])
    print(row["settlement_tx_url"])
PY
```

The same hashes are on the stats document:

```bash
curl -fsS "$COORD/api/stats" | python3 -c 'import json,sys; body=json.load(sys.stdin); [print(item["status"], item["tx_url"]) for item in body.get("settlement_txs") or []]'
```

What to check:

- `tx_url` starts with `https://sepolia.basescan.org/tx/0x`.
- Open that URL. The transaction is to Settlement `0xdfFE664d23E30Baff7Ad4d16831aD625Cc90bcCA` and the status is success.
- The token movement is HHCW `0x24a7B22fC54DbFD117023535eBeCf660B76fdb5d`.
- `settlement_status` is `settled` or `already_settled`. A row with no payout address stays `skipped_missing_payout` and has no Base transaction. That is expected until the node joins with `--payout-address`.
