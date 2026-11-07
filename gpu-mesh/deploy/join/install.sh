#!/usr/bin/env bash
# Linux and macOS. One command from the join page:
#   curl -fsSL https://raw.githubusercontent.com/dbottrader/Holbrook-CP8-HHC/main/gpu-mesh/deploy/join/install.sh | bash
#
# Reuses the gpu-mesh worker (gpumesh_node) published as one GHCR image.
# llama.cpp is the default backend inside that image. --backend ollama
# also starts the official Ollama container from docker-compose.yml.
# The public coordinator is the default. --coordinator overrides it.
# Registration is rate-limited. The published open invite is "open" and is not required.
set -euo pipefail

DEFAULT_COORD="https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/gpu-mesh"
COORD=""
BACKEND="llamacpp"
NAME=""
INVITE="${GPU_MESH_INVITE:-}"
IMAGE="${GPU_MESH_IMAGE:-ghcr.io/dbottrader/holbrook-cp8-hhc/gpumesh-join:latest}"
OLLAMA_HOST="http://127.0.0.1:11434"
DRY=0

usage() {
  echo "Usage: install.sh [--coordinator URL] [--backend llamacpp|ollama] [--name NAME] [--invite TOKEN] [--image REF]" >&2
  echo "Default coordinator: $DEFAULT_COORD" >&2
  echo "Published open invite (not required): open" >&2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --coordinator) COORD="${2:-}"; shift 2 ;;
    --backend) BACKEND="${2:-}"; shift 2 ;;
    --name) NAME="${2:-}"; shift 2 ;;
    --invite) INVITE="${2:-}"; shift 2 ;;
    --image) IMAGE="${2:-}"; shift 2 ;;
    --dry-run) DRY=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage; exit 2 ;;
  esac
done

if [[ -z "$COORD" ]]; then
  COORD="${GPU_MESH_COORDINATOR:-$DEFAULT_COORD}"
fi
if [[ "$BACKEND" != "llamacpp" && "$BACKEND" != "ollama" ]]; then
  echo "Backend must be llamacpp or ollama." >&2
  exit 2
fi
if [[ "$DRY" == "1" ]]; then
  echo "coordinator=$COORD"
  echo "backend=$BACKEND"
  echo "image=$IMAGE"
  echo "invite=${INVITE}"
  exit 0
fi
if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required. Install Docker Engine or Docker Desktop, then run this again." >&2
  exit 1
fi

if [[ -z "$NAME" ]]; then
  NAME="$(hostname -s 2>/dev/null || hostname)"
fi

if [[ "$BACKEND" == "ollama" ]]; then
  if ! docker ps --format '{{.Names}}' | grep -qx 'gpumesh-ollama'; then
    docker run -d --name gpumesh-ollama --restart unless-stopped -v gpumesh-ollama:/root/.ollama -p 11434:11434 ollama/ollama:0.12.6
  fi
  OLLAMA_HOST="http://host.docker.internal:11434"
fi

docker pull "$IMAGE"
docker rm -f gpumesh-join >/dev/null 2>&1 || true
docker run -d --name gpumesh-join --restart unless-stopped \
  --add-host=host.docker.internal:host-gateway \
  -e GPU_MESH_COORDINATOR="$COORD" \
  -e GPU_MESH_BACKEND="$BACKEND" \
  -e GPU_MESH_OLLAMA_HOST="$OLLAMA_HOST" \
  -e GPU_MESH_INVITE="$INVITE" \
  -e GPU_MESH_NAME="$NAME" \
  -e GPU_MESH_ALLOW_CPU=1 \
  -v gpumesh-join:/var/lib/gpumesh \
  "$IMAGE"

echo "Worker gpumesh-join is running against $COORD (backend $BACKEND)."
echo "HHC from that coordinator is a simulated utility credit for verified contribution."
echo "Logs: docker logs -f gpumesh-join"
