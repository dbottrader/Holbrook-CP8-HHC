# GPU Mesh

Volunteer GPU network for free open-weight inference. People contribute GPU time the way miners contribute hashpower. The coordinator queues chat jobs and hands them to machines that already run those models through [Ollama](https://ollama.com) or [vLLM](https://docs.vllm.ai). Anyone can call the public API.

Compute credits are a **simulated ledger**. They are not money, not a token, and they cannot be transferred, sold, or redeemed. There is no wallet and no chain in the cryptocurrency sense. Receipts are a hash chain so a contribution can be replayed offline, in the same canonical-JSON style as [ASIN-HHC](https://github.com/dbottrader/ASIN-HHC-Agent-Mesh).

```
client  --OpenAI /v1/chat/completions-->  coordinator  <--pull jobs--  node (your GPU)
                                              |                              |
                                              |-- hash-chained receipt <-----|
                                              |-- spot-check on a second node
                                              +-- dashboard
```

## What a job does

1. A client calls `POST /v1/chat/completions` (streaming or not). Anonymous callers are rate limited by IP. An optional `sk-mesh-…` key has its own limit.
2. The coordinator queues the job if some online node advertises that model.
3. A node heartbeats GPU name, VRAM, and loaded models, then long-polls for a job. It runs the chat on Ollama or vLLM and posts the text back. The node opens no inbound port.
4. The coordinator stores the output and writes an `execution_submitted` receipt with amount 0. That is not a credit. A second node spot-checks the text and, when TOPLOC is installed, the worker's proof. Agreement writes one `inference_receipt`. The receipt hash covers the canonical JSON of `actor`, `kind`, `payload`, `prev_hash`, `seq`, and `ts` (Unix milliseconds). A separate EIP-712-style signature covers the integer amount, worker, verifiers, and settlement id. `hash` and `canon` sit beside the preimage.
5. A sample of jobs is queued again for a **different** node. Temperature-0 disagreements and a failed TOPLOC proof go to `disputed` and do not credit the worker. The checker is paid either way. Sampled (temperature > 0) disagreements are disputed without a slash, because open models are not bitwise stable there.
6. Canaries ("reply with exactly this token") run even when only one node is online. Three failures, or reputation under 40, quarantines the node. An admin can reinstate it.

The CPU fallback (`mock-tiny`) is a deterministic stub for tests and for `docker compose` on a machine with no GPU. It is not a neural model, and the API says so.

`GPU_MESH_BACKEND=llamacpp` serves a real open-weight model on CPU: SmolLM2-360M-Instruct Q8_0 (Apache-2.0), pulled at runtime from HuggingFaceTB and checked against a pinned SHA-256. The GGUF is not in git. That path does not attach a TOPLOC hidden-state proof. Install it with `pip install -e ".[cpu]"`.

A free-tier coordinator and worker runbook, including the Hugging Face Space steps and the NVIDIA Ollama invite, is in [docs/FREE_TIER.md](docs/FREE_TIER.md). The Space bundle is [deploy/huggingface/](deploy/huggingface/).

## Local quickstart

Docker Compose runs the coordinator and one CPU-fallback node:

```bash
docker compose up --build
```

Board: http://localhost:8741

```bash
curl -s http://localhost:8741/v1/chat/completions \
  -H 'content-type: application/json' \
  -d '{"model":"mock-tiny","messages":[{"role":"user","content":"Say hello in one sentence."}],"temperature":0}'
```

Spot-checks need a second node. Compose starts one by default; the extra node is a profile:

```bash
docker compose --profile verify up --build
```

The dev admin token in Compose is `dev-admin-change-me`. Do not use it on a public host.

Without Docker, from this repo:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
GPU_MESH_ADMIN_TOKEN=dev GPU_MESH_PORT=8741 python -m gpumesh
```

In another shell, a CPU node:

```bash
GPU_MESH_COORDINATOR=http://127.0.0.1:8741 \
GPU_MESH_ALLOW_CPU=1 \
GPU_MESH_BACKEND=cpu \
GPU_MESH_NAME=laptop-cpu \
python -m gpumesh_node
```

Replay a ledger file:

```bash
curl -s http://127.0.0.1:8741/api/ledger -o ledger.json
gpumesh-verify-ledger ledger.json
```

## Public API

`GET /v1/models` and `POST /v1/chat/completions` follow the OpenAI chat shape, including `stream: true` (server-sent events). `n` must be 1. Image inputs are rejected. `max_tokens` is clamped (default cap 1024) and prompts are capped (default 16k characters).

Optional header `X-GPUMesh-Wait-Seconds: 0` returns `202` with a poll URL `GET /v1/jobs/{id}` instead of waiting.

Anonymous default is 30 requests per minute per IP, plus a duplicate-prompt cap. Create a key with the admin token:

```bash
curl -s http://127.0.0.1:8741/api/admin/keys \
  -H "authorization: Bearer $GPU_MESH_ADMIN_TOKEN" \
  -H 'content-type: application/json' \
  -d '{"name":"friends","rpm":120}'
```

The plaintext key is returned once. Send it as `Authorization: Bearer sk-mesh-…`.

Other admin routes, same bearer token:

- `POST /api/admin/keys/{id}/revoke`
- `POST /api/admin/bans` with `{"ip","reason"}` and `POST /api/admin/bans/lift`
- `POST /api/admin/nodes/{id}/ban` and `POST /api/admin/nodes/{id}/reinstate`
- `POST /api/admin/canary` to inject a known-answer job now

`GET /api/stats`, `GET /api/receipts`, `GET /api/ledger`, and `GET /api/ledger/verify` are public. Receipts store an output hash, not the prompt and not the completion text.

## Node protocol

| Call | Purpose |
| --- | --- |
| `POST /api/nodes/register` | Returns `node_id` and a `gmt_…` token once |
| `POST /api/nodes/heartbeat` | GPU, VRAM, models, backend |
| `POST /api/nodes/jobs/claim?wait=20` | Long-poll. The payload has no canary answer and no "this is a check" flag |
| `POST /api/nodes/jobs/{id}/chunks` | Optional streaming deltas |
| `POST /api/nodes/jobs/{id}/result` | Final text, token counts, duration |
| `POST /api/nodes/jobs/{id}/fail` | Requeue onto someone else |

A job that sits assigned past `GPU_MESH_JOB_TIMEOUT_SEC` (default 120) is requeued, up to 3 attempts. A node that misses heartbeats (default 30s) is marked offline and its jobs return to the queue.

Backends:

- `ollama` — `OLLAMA_HOST` or `GPU_MESH_OLLAMA_HOST` (default `http://127.0.0.1:11434`). Models come from `ollama list`. Pull weights yourself: `ollama pull llama3.2:1b`.
- `vllm` — OpenAI server on `GPU_MESH_VLLM_HOST` (default `http://127.0.0.1:8000`).
- `auto` — Ollama, then vLLM, then CPU if `GPU_MESH_ALLOW_CPU=1`.
- `llamacpp` — llama.cpp on CPU. Default model id `SmolLM2-360M-Instruct`. Weights download into `GPU_MESH_MODEL_CACHE` (default `data/models`) and are not committed. Canary-shaped exact-token prompts are answered literally; every other prompt is the GGUF. No TOPLOC hidden-state proof.
- `cpu` — deterministic `mock-tiny` only. Not an open-weight model.

The ledger unit is HHC, a simulated utility credit for verified contribution. The software stores it as an integer kudos balance. It is not sold, and it pays no return. Amounts scale with capped completion length and VRAM class (1× CPU, 2× under 12 GB, 4× under 20 GB, 8× at 20 GB and above) and are recorded only after verification. Until a worker is trusted (by default, account age of 7 days and 3 verified jobs), the balance stays in an accounting hold. A failed canary reduces the balance by 5 and adds a strike. Jobs that finish absurdly fast on a GPU backend, or that keep failing, raise a suspicion score and the scheduler pauses the node. Anonymous callers can queue small jobs. A request above the free completion-length cap needs a positive HHC balance on an API key, and a higher balance is served first. The simulated ledger is the default. `GPU_MESH_LEDGER_BACKEND=onchain` is refused and does not mint anything.

## Install a node (systemd, non-root)

On the GPU machine, after the NVIDIA driver and Ollama or vLLM are up:

```bash
curl -fsSL https://YOUR-COORDINATOR/install.sh | sudo bash -s -- --name my-rig
```

The script creates user `gpumesh`, a venv under `/opt/gpumesh`, `/etc/gpumesh/node.env`, and `gpumesh-node.service`. The unit sets `User=gpumesh`, `NoNewPrivileges=true`, `ProtectSystem=strict`, and can write only `/var/lib/gpumesh`. Root is used to install, not to serve.

```bash
systemctl status gpumesh-node
journalctl -u gpumesh-node -f
```

Dry run on a box with no GPU: add `--allow-cpu`. That serves `mock-tiny` only. For a real small model on CPU, use `--backend llamacpp` after `pip install 'llama-cpp-python>=0.3.4'`. See [docs/FREE_TIER.md](docs/FREE_TIER.md).

The same agent is a Docker image (`node/Dockerfile`). It starts as root only to chown the state volume, then `setpriv` drops to uid 10001 (`gpumesh`). For a real GPU, install the NVIDIA container toolkit and run that image with `--gpus all`, `GPU_MESH_BACKEND=ollama` or `vllm`, and the runtime reachable from the container (host network, or an Ollama container on the same Docker network). Do not set `GPU_MESH_ALLOW_CPU` on a machine you intend to contribute for real.

## Deploy a public coordinator

One process. The ledger lock is in-process; do not run multiple uvicorn workers against one database.

1. A small VM is enough. GPUs stay on volunteer machines. Ubuntu 24.04 is the path this was written for.
2. Install Docker and the Compose plugin.
3. Clone this repo. Set a long `GPU_MESH_ADMIN_TOKEN` and `GPU_MESH_PUBLIC_BASE_URL=https://gpu.example.com` in `.env` (see `.env.example`). Leave the CPU node off if you do not want a public `mock-tiny`:
   ```bash
   docker compose up -d --build coordinator
   ```
4. Put Caddy or nginx in front with TLS, proxying to port 8741. Set `GPU_MESH_TRUST_PROXY=1` so rate limits use `X-Forwarded-For`.
5. Postgres is optional. The image includes `psycopg`. Point `GPU_MESH_DATABASE_URL` at `postgresql+psycopg://USER:PASSWORD@HOST:5432/gpumesh` and keep `GPU_MESH_DATA_DIR` on a volume so a generated admin token (if you forgot to set one) survives restarts. SQLite on the `/data` volume is the default and is enough to start.
6. Raise `GPU_MESH_JOB_TIMEOUT_SEC` if the models you expect are slow to load on first use. Raise `GPU_MESH_MAX_COMPLETION_TOKENS` only if you are willing to spend volunteer time on long answers.
7. On the first GPU box: install the driver, install Ollama, `ollama pull` an open model, then run the installer against `https://gpu.example.com`. Confirm the node on the board and call `/v1/chat/completions` with that model's name.

If you skip Docker on the coordinator, `pip install '.[postgres]'` and `python -m gpumesh` with the same environment variables. Bind a non-default port if 8741 is taken. Keep the data directory backed up: it holds the SQLite ledger (or, with Postgres, the admin token file).

## Tests

```bash
pip install -e ".[dev]"
ruff check .
pytest -q
```

CI is [`.github/workflows/gpu-mesh.yml`](../.github/workflows/gpu-mesh.yml) in the Holbrook repo. It runs Ruff and pytest on Python 3.12, scoped to `gpu-mesh/`. The integration test drives the real node agent against the FastAPI app in-process, including a dishonest node that gets slashed and quarantined. No GPU and no GGUF download are required. The llama.cpp extra is not installed in CI.

## Limits worth knowing

- One coordinator process. Rate-limit buckets live in memory and reset on restart. Bans and the ledger are in the database.
- A spot-check compares text. It cannot prove the weights that produced it. A node that behaves only on canary-shaped prompts can still cheat ordinary traffic until a temperature-0 re-run disagrees. That disagreement is recorded and, when temperature was 0, penalized.
- Prompts are stored until `GPU_MESH_PROMPT_RETENTION_SEC` (default one day) so a spot-check can replay them, then the message body is cleared. Receipts never contained the prompt.
- The node does not execute the prompt in a shell. It forwards chat messages to Ollama, vLLM, or a local llama.cpp GGUF. The `cpu` backend does not run a model at all.
- HHC is a simulated utility credit for verified contribution. The amounts are integers. The on-chain backend refuses to mint. Do not describe the credit as a payout, a sale, or a return.
- One worker process. Do not mount the Docker socket, the coordinator database, or host paths into the node. The Compose node runs as uid 10001, read-only, with every capability dropped.
- Install `torch==2.5.1` (CPU index is enough) and `toploc==0.1.6` before a public launch if you want proof-of-inference enforced. Without that library the coordinator still spot-checks text and records the proof as unavailable.

`POST /api/admin/ledger/anchor` (admin token) writes a Merkle root of the receipt chain into the database. It does not publish the root. `GET /api/ledger/anchor` reads the latest one.

`POST /api/nodes/credentials/rotate` replaces a live node token. `POST /api/admin/nodes/{id}/revoke-credentials` revokes every token for that node. Set `GPU_MESH_INVITE_ONLY=1` and `GPU_MESH_INVITE_TOKEN` to keep the first cohort invite-only. `GPU_MESH_MAX_NODES` caps how many can register.

## Where the design came from

No AGPL source is copied into this repo. AI Horde's server and worker are AGPL-3.0-or-later; copying them would require this project to be AGPL as well, and it is MIT. The ideas below are reimplemented.

| Source | License | What we took | What we did not take |
| --- | --- | --- | --- |
| [AI Horde](https://github.com/Haidra-Org/AI-Horde) and [horde-worker-reGen](https://github.com/Haidra-Org/horde-worker-reGen) | AGPL-3.0-or-later | Poll-only workers (they never listen), kudos as non-cash priority, escrow until trusted, suspicion on too-fast or failed jobs, size threshold before a request spends kudos. Docs: [kudos](https://haidra-org.github.io/AI-Horde/haidra-assets/docs/kudos/), [workers](https://github.com/Haidra-Org/haidra-assets/blob/main/docs/workers.md). | Their server code, uptime formula, and kudos trading. Trading is a later decision. |
| [TOPLOC](https://github.com/PrimeIntellect-ai/toploc) (Prime Intellect), paper [arXiv:2501.16007](https://arxiv.org/abs/2501.16007) | MIT | `build_proofs_base64` / `verify_proofs_base64` as the proof-of-inference check beside the text spot-check. Copyright Jack Min Ong and the TOPLOC authors; see that repo's LICENSE. | We do not reimplement the polynomial. CPU fallback proves a deterministic activation trace of the prompt, and the README says so. A hidden-state proof is the check that a transformer ran. |
| [Petals](https://github.com/bigscience-workshop/petals) | MIT | Heartbeat expiry, request timeouts, and the warning that untrusted peers can lie. The second-node spot-check is their "send it twice" idea. | We do not run a DHT or shard layers. The node opens no port. |
| [exo](https://github.com/exo-explore/exo) | Apache-2.0 | OpenAI-compatible `/v1/chat/completions`, and placing a job only on a node that advertises the model. | No Apache source is copied. We do not elect a master or pool a home cluster over libp2p. |
| [GPUStack](https://github.com/gpustack/gpustack) | Apache-2.0 | Dashboard metering: tokens, jobs, and per-model usage, plus per-key quotas. No Apache source is copied. | Their cluster manager and model catalog service. |
| EIP-712 and Merkle commitments | Public specifications | Typed-data claims and a pairwise SHA-256 root over receipt hashes. SHA-256 stands in for keccak256. `chainId` is 0. | No transaction, contract, or mint. |
| [ASIN-HHC Agent Mesh](https://github.com/dbottrader/ASIN-HHC-Agent-Mesh) | see that repo | Canonical JSON hashing for the receipt chain (`sort_keys`, compact separators, millisecond timestamps). | — |

On top of those: fenced leases (a generation token, an expiry, rejection of a late completion), exactly-once settlement enforced by a unique key (the same unique constraint Postgres and SQLite both apply), revocable per-node credentials, admission control, and the signed simulated ledger.
