# Contribute a machine to the ASIN-HHC GPU Mesh

This guide gets you from zero to a node that does verified work, in one command.
HHC is a utility credit for verified contribution. It is not sold and it pays no return.

## Quickstart (Linux x86_64 or Windows WSL2)

```bash
curl -fsSL https://raw.githubusercontent.com/dbottrader/Holbrook-CP8-HHC/main/gpu-mesh/deploy/join/join.sh | bash
# optional: name the EVM address that receives this node's HHCW on Base Sepolia
curl -fsSL https://raw.githubusercontent.com/dbottrader/Holbrook-CP8-HHC/main/gpu-mesh/deploy/join/join.sh | bash -s -- --payout-address 0xYourEvmAddress
```

Prefer to read first? `curl -fsSLO .../join.sh && less join.sh && bash join.sh --dry-run`.

Needs: AVX2 CPU, curl, about 2 GB free disk during install (0.7 GB after), 2 GB free RAM.
Python 3.11+ is used if present. If not, the script fetches `uv` into `~/.asin-hhc/bin`.
No Docker, no sudo, no account, no invite.

## What the script does

| Step | Check | Stops when |
|---|---|---|
| 1 | Platform, coordinator `/health`, Python | not Linux x86_64 with AVX2, hub unreachable |
| 2 | Installs `gpumesh_node` into `~/.asin-hhc/venv` | pip fails |
| 3 | Downloads Ollama v0.40.15 (sha256 `628c0184…`), keeps only `libggml-cpu-haswell.so`, serves it on `127.0.0.1:11435` | sha256 mismatch, port taken |
| 4 | Downloads `qwen2.5-0.5b-instruct-q4_k_m.gguf` (sha256 `74a4da8c…`) | sha256 mismatch |
| 5 | Builds `asin-qwen0.5b` from `gpu-mesh/models/asin-qwen0.5b.Modelfile`, checks digest `29ef26c5…` | digest mismatch |
| 6 | Replays public job `job_17da8f18d97f` and requires output sha256 `d30ca7a7…` | output differs |
| 7 | Registers, saves the token to `~/.asin-hhc/node.json` (mode 600), starts the worker | worker exits |

Commands after joining:

```bash
tail -f ~/.asin-hhc/node.log      # what the node is doing
bash ~/.asin-hhc/stop.sh          # stop the node and its private Ollama
curl -fsSL .../join.sh | bash     # rerun: reuses the identity, skips finished downloads
```

## Why the runtime is pinned so tightly

A verifier reruns the worker's job with temperature 0, top_k 1 and a seed derived from the job id,
then compares output hashes. That only works if both machines compute the same numbers.
On 2026-11-20 our test box (Xeon with AVX-512 and AMX) answered `Mesh` to job `job_17da8f18d97f`,
while the worker and first verifier answered `mesh`. Same model digest, same seed. Restricting
Ollama to its AVX2 (`haswell`) CPU backend on the same box produced `mesh`, matching them.
So the join script runs exactly one CPU backend, and step 6 refuses machines that still differ.

Not verifiers yet: macOS, ARM, and GPU backends. Their replays have not been shown to match
the canonical runtime. A GPU profile needs a GPU-to-GPU replay matrix first.

## How credit works

- A verifier commits the sha256 of its output before the hub reveals the worker's hash.
- A verifier is paid the same for agree and disagree, so faking agreement gains nothing.
- A job enters Base Sepolia settlement after two distinct verifiers, neither the worker, agree.
  A disagreement goes to one tiebreaker.
- A new node's credit is held until it is 7 days old and has 3 verified jobs.
- HHCW `0x24a7B22fC54DbFD117023535eBeCf660B76fdb5d`, Settlement `0xdfFE664d23E30Baff7Ad4d16831aD625Cc90bcCA`.

## Reporting a failed check

Open an issue at https://github.com/dbottrader/Holbrook-CP8-HHC/issues with the last 30 lines of
the script output, your CPU model (`grep -m1 "model name" /proc/cpuinfo`), and `uname -a`.
Never paste `~/.asin-hhc/node.json`: it holds your node token.
