# Windows

HHC is a utility credit for verified contribution. It is not sold and it pays no return. The public hub settles it as HHCW on Base Sepolia after two distinct verifiers agree. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) and leave it running. The Linux installer detects a GPU. On Windows, pass `--gpus all` yourself when Docker Desktop GPU support is on, or use `--cpu` behavior by leaving the GPU flags off.

## llama.cpp (default)

PowerShell:

```powershell
docker run -d --name gpumesh-join --restart unless-stopped `
  -e GPU_MESH_COORDINATOR=https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/gpu-mesh `
  -e GPU_MESH_BACKEND=llamacpp `
  -e GPU_MESH_ALLOW_CPU=1 `
  -e GPU_MESH_NAME=$env:COMPUTERNAME `
  -v gpumesh-join:/var/lib/gpumesh `
  ghcr.io/dbottrader/holbrook-cp8-hhc/gpumesh-join:latest
```

The first job downloads SmolLM2-360M-Instruct into the volume. Watch it with `docker logs -f gpumesh-join`.

## Ollama

Install Ollama from https://ollama.com/download/windows and pull a weight, for example `ollama pull llama3.2:1b`. Then:

```powershell
docker run -d --name gpumesh-join --restart unless-stopped `
  --add-host=host.docker.internal:host-gateway `
  -e GPU_MESH_COORDINATOR=https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/gpu-mesh `
  -e GPU_MESH_BACKEND=ollama `
  -e GPU_MESH_OLLAMA_HOST=http://host.docker.internal:11434 `
  -e GPU_MESH_NAME=$env:COMPUTERNAME `
  -v gpumesh-join:/var/lib/gpumesh `
  ghcr.io/dbottrader/holbrook-cp8-hhc/gpumesh-join:latest
```

The model id the coordinator must be asked for is the Ollama tag, such as `llama3.2:1b`.

From a checkout of this repository, Docker Compose is the same file as on Linux:

```powershell
$env:GPU_MESH_COORDINATOR = "https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/gpu-mesh"
docker compose -f gpu-mesh/deploy/join/docker-compose.yml up --build
```

Add `--profile ollama` when `GPU_MESH_BACKEND` is `ollama`.
