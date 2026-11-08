---
title: GPU Mesh
emoji: 🤖
colorFrom: gray
colorTo: green
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: Free CPU SmolLM2 chat. HHC is a utility credit.
---

# GPU Mesh — free CPU demo

This Space runs the GPU Mesh coordinator and **one** CPU worker. The worker loads **SmolLM2-360M-Instruct** (Apache-2.0) through llama.cpp. The GGUF is downloaded on first start from `HuggingFaceTB/SmolLM2-360M-Instruct-GGUF` and is not in git.

HHC is a utility credit for verified contribution. It is stored as an integer. It is not sold, it is not a claim on anything of value, and it pays no return. With only this one worker online, a chat completion is returned and the HHC amount for that job stays 0. A second worker on the same model id has to spot-check it before an amount is recorded. New amounts stay in an accounting hold until that worker is 7 days old and has 3 verified jobs.

The public GPU mesh settles HHCW on Base Sepolia after two distinct verifiers agree (Settlement `0xdfFE664d23E30Baff7Ad4d16831aD625Cc90bcCA`, token `0x24a7B22fC54DbFD117023535eBeCf660B76fdb5d`). The key stays on the operator box. Nothing in this Space deploys a contract or holds that key. This Space is the CPU demo. GPU passthrough is `gpu-mesh/deploy/join`.

## Call it

Wait until the logs say the node is online. The first boot downloads about 369 MB.

```bash
curl -s https://USERNAME-gpu-mesh.hf.space/v1/models
curl -s https://USERNAME-gpu-mesh.hf.space/v1/chat/completions \
  -H 'content-type: application/json' \
  -d '{"model":"SmolLM2-360M-Instruct","messages":[{"role":"user","content":"What color is a clear daytime sky? Answer in one short sentence."}],"temperature":0,"max_tokens":64}'
```

## What this demo is not

The free CPU Space disk does not survive a rebuild. The receipt signing key in `/data` is lost with it, so this Space is a public demo, not the durable ledger. A home machine or an always-on VM with a backed-up `data/` directory is the coordinator you keep.

NVIDIA volunteers join with Ollama and the invite. The steps are in `docs/FREE_TIER.md` in [Holbrook-CP8-HHC](https://github.com/dbottrader/Holbrook-CP8-HHC/blob/main/gpu-mesh/docs/FREE_TIER.md). An Ollama tag spot-checks a job only when the model id matches. This worker's id is `SmolLM2-360M-Instruct`.
