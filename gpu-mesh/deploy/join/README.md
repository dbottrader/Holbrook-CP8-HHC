# GPU volunteer join kit

One image runs the GPU Mesh worker from `gpumesh_node`. The default backend is llama.cpp with SmolLM2-360M-Instruct, the same worker as `gpu-mesh/gpumesh_node/llamacpp.py`. `--backend ollama` uses the official `ollama/ollama:0.12.6` image and the worker's existing Ollama client.

HHC is a simulated utility credit for verified contribution.

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

Ollama instead of llama.cpp:

```bash
curl -fsSL https://raw.githubusercontent.com/dbottrader/Holbrook-CP8-HHC/main/gpu-mesh/deploy/join/install.sh | bash -s -- --backend ollama
```

From a checkout, Compose in this directory uses the same default:

```bash
docker compose -f gpu-mesh/deploy/join/docker-compose.yml up --build
```

## Windows

See [WINDOWS.md](WINDOWS.md).
