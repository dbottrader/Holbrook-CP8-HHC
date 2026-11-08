# GPU volunteer join kit

One image runs the GPU Mesh worker from `gpumesh_node`. A visible NVIDIA GPU selects Ollama (`ollama/ollama:0.12.6`) with `--gpus all` and a Qwen2.5 instruct tag sized to VRAM. An AMD GPU selects `ollama/ollama:rocm` with `/dev/kfd` and `/dev/dri`. No GPU, or `--cpu`, uses llama.cpp with SmolLM2-360M-Instruct, the same worker as `gpu-mesh/gpumesh_node/llamacpp.py`. `--backend ollama` or `--backend llamacpp` overrides that choice. `--gpu` fails if no GPU is visible. `--payout-address 0x…` is unchanged.

HHC is a utility credit for verified contribution. It is not sold and it pays no return. The public hub settles it as HHCW on Base Sepolia after two distinct verifiers agree. Settlement `0xdfFE664d23E30Baff7Ad4d16831aD625Cc90bcCA`, token `0x24a7B22fC54DbFD117023535eBeCf660B76fdb5d`. The key stays on the operator box.

The image installs the pinned CPU wheel `llama-cpp-python` 0.3.36 from the upstream `v0.3.36` release (the asset with no CUDA, HIP, or Vulkan suffix). PyPI only publishes a source tarball for that version.

The image is published to GHCR by `.github/workflows/gpumesh-join.yml` on pushes to `main`:

```text
ghcr.io/dbottrader/holbrook-cp8-hhc/gpumesh-join:latest
```

GitHub packages are private until the repository owner marks this package public. The workflow uses `GITHUB_TOKEN` only. No other secret is stored in the repo.

## Linux and macOS

The public coordinator is the default. No invite is required. The published open invite is `open`.

```bash
curl -fsSL https://raw.githubusercontent.com/dbottrader/Holbrook-CP8-HHC/main/gpu-mesh/deploy/join/install.sh | bash
```

Run the llama.cpp CPU worker, or require a GPU:

```bash
curl -fsSL https://raw.githubusercontent.com/dbottrader/Holbrook-CP8-HHC/main/gpu-mesh/deploy/join/install.sh | bash -s -- --cpu
curl -fsSL https://raw.githubusercontent.com/dbottrader/Holbrook-CP8-HHC/main/gpu-mesh/deploy/join/install.sh | bash -s -- --gpu --payout-address 0xYourEvmAddress
```

From a checkout, Compose in this directory uses the CPU worker unless you select a profile:

```bash
docker compose -f gpu-mesh/deploy/join/docker-compose.yml up --build
docker compose -f gpu-mesh/deploy/join/docker-compose.yml --profile nvidia up --build --scale worker=0
docker compose -f gpu-mesh/deploy/join/docker-compose.yml --profile rocm up --build --scale worker=0
```

The `nvidia` profile sets `deploy.resources.reservations.devices` with driver `nvidia` and capabilities `[gpu]`. The `rocm` profile uses `ollama/ollama:rocm`. If `nvidia-smi` works and `nvidia-ctk` does not, the installer prints the NVIDIA Container Toolkit commands and does not start the worker.

## Windows

See [WINDOWS.md](WINDOWS.md).
