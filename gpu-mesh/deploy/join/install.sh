#!/usr/bin/env bash
# Linux and macOS. One command from the join page:
#   curl -fsSL https://raw.githubusercontent.com/dbottrader/Holbrook-CP8-HHC/main/gpu-mesh/deploy/join/install.sh | bash
#
# Detects an NVIDIA or AMD GPU and starts Ollama with that device.
# CPU llama.cpp is the fallback when no GPU is visible, or when --cpu is passed.
# --payout-address is the EVM address that receives this node's HHCW.
# The public coordinator is the default. --coordinator overrides it.
# Registration is rate-limited. The published open invite is "open" and is not required.
set -euo pipefail

DEFAULT_COORD="https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/gpu-mesh"
COORD=""
BACKEND=""
NAME=""
INVITE="${GPU_MESH_INVITE:-}"
PAYOUT="${GPU_MESH_PAYOUT_ADDRESS:-}"
IMAGE="${GPU_MESH_IMAGE:-ghcr.io/dbottrader/holbrook-cp8-hhc/gpumesh-join:latest}"
OLLAMA_HOST="http://127.0.0.1:11434"
DRY=0
WANT_GPU=0
WANT_CPU=0

usage() {
  echo "Usage: install.sh [--coordinator URL] [--backend llamacpp|ollama] [--name NAME] [--invite TOKEN] [--payout-address 0x…] [--image REF] [--gpu] [--cpu]" >&2
  echo "Default coordinator: $DEFAULT_COORD" >&2
  echo "Published open invite (not required): open" >&2
  echo "A visible NVIDIA or AMD GPU selects Ollama on that GPU. --cpu forces the CPU fallback. --gpu fails if no GPU is visible." >&2
}

gpu_mesh_source_mode() {
  local here="" mode_file=""
  if [[ -n "${BASH_SOURCE[0]:-}" && -f "${BASH_SOURCE[0]}" ]]; then
    here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  fi
  if [[ -n "$here" && -f "$here/gpu-mode.sh" ]]; then
    mode_file="$here/gpu-mode.sh"
    # shellcheck disable=SC1090,SC1091
    source "$mode_file"
    return 0
  fi
  if [[ -n "${GPU_MESH_GPU_MODE_FILE:-}" && -f "${GPU_MESH_GPU_MODE_FILE}" ]]; then
    # shellcheck disable=SC1090
    source "${GPU_MESH_GPU_MODE_FILE}"
    return 0
  fi
  local url="${GPU_MESH_GPU_MODE_URL:-https://raw.githubusercontent.com/dbottrader/Holbrook-CP8-HHC/main/gpu-mesh/deploy/join/gpu-mode.sh}"
  local tmp
  tmp="$(mktemp)"
  curl -fsSL "$url" -o "$tmp"
  # shellcheck disable=SC1090
  source "$tmp"
  rm -f "$tmp"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --coordinator) COORD="${2:-}"; shift 2 ;;
    --backend) BACKEND="${2:-}"; shift 2 ;;
    --name) NAME="${2:-}"; shift 2 ;;
    --invite) INVITE="${2:-}"; shift 2 ;;
    --payout-address) PAYOUT="${2:-}"; shift 2 ;;
    --image) IMAGE="${2:-}"; shift 2 ;;
    --gpu) WANT_GPU=1; shift ;;
    --cpu) WANT_CPU=1; shift ;;
    --dry-run) DRY=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage; exit 2 ;;
  esac
done

if [[ "$WANT_GPU" == "1" && "$WANT_CPU" == "1" ]]; then
  echo "Pass only one of --gpu or --cpu." >&2
  exit 2
fi
if [[ -n "$BACKEND" && "$BACKEND" != "llamacpp" && "$BACKEND" != "ollama" ]]; then
  echo "Backend must be llamacpp or ollama." >&2
  exit 2
fi
if [[ -n "$PAYOUT" && ! "$PAYOUT" =~ ^0x[0-9a-fA-F]{40}$ ]]; then
  echo "payout address must be a 0x EVM address." >&2
  exit 2
fi
if [[ "$PAYOUT" =~ ^0x0{40}$ ]]; then
  echo "payout address must not be the zero address." >&2
  exit 2
fi

gpu_mesh_source_mode
if [[ "$WANT_GPU" == "1" && -n "$BACKEND" ]]; then
  gpu_mode_plan --gpu --backend "$BACKEND"
elif [[ "$WANT_GPU" == "1" ]]; then
  gpu_mode_plan --gpu
elif [[ "$WANT_CPU" == "1" && -n "$BACKEND" ]]; then
  gpu_mode_plan --cpu --backend "$BACKEND"
elif [[ "$WANT_CPU" == "1" ]]; then
  gpu_mode_plan --cpu
elif [[ -n "$BACKEND" ]]; then
  gpu_mode_plan --backend "$BACKEND"
else
  gpu_mode_plan
fi

if [[ -z "$COORD" ]]; then
  COORD="${GPU_MESH_COORDINATOR:-$DEFAULT_COORD}"
fi

echo "GPU_MESH_MODE: ${RUN_NOTE}"
gpu_mode_emit
echo "coordinator=$COORD"
echo "backend=$RUN_BACKEND"
echo "image=$IMAGE"
echo "invite=${INVITE}"
echo "payout=${PAYOUT}"

if [[ "$DRY" == "1" ]]; then
  if [[ "$RUN_TOOLKIT" == "missing" ]]; then
    gpu_mode_toolkit_instructions
  fi
  exit 0
fi

if [[ "$RUN_DOCKER_GPUS" == "all" && "$RUN_TOOLKIT" == "missing" ]]; then
  gpu_mode_toolkit_instructions >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required. Install Docker Engine or Docker Desktop, then run this again." >&2
  exit 1
fi

if [[ -z "$NAME" ]]; then
  NAME="$(hostname -s 2>/dev/null || hostname)"
fi

worker_host="http://host.docker.internal:11434"
if [[ "$RUN_BACKEND" == "ollama" ]]; then
  echo "GPU_MESH_MODE: starting Ollama image ${RUN_OLLAMA_IMAGE}"
  docker rm -f gpumesh-ollama >/dev/null 2>&1 || true
  ollama_args=(docker run -d --name gpumesh-ollama --restart unless-stopped)
  if [[ "$RUN_DOCKER_GPUS" == "all" ]]; then
    ollama_args+=(--gpus all)
    ollama_args+=(-e NVIDIA_VISIBLE_DEVICES=all)
    ollama_args+=(-e "NVIDIA_DRIVER_CAPABILITIES=compute,utility")
  fi
  if [[ -n "$RUN_DOCKER_DEVICES" ]]; then
    for dev in $RUN_DOCKER_DEVICES; do
      ollama_args+=(--device "$dev")
    done
    if command -v getent >/dev/null 2>&1; then
      if getent group video >/dev/null 2>&1; then
        ollama_args+=(--group-add video)
      fi
      if getent group render >/dev/null 2>&1; then
        ollama_args+=(--group-add render)
      fi
    fi
  fi
  ollama_args+=(-v gpumesh-ollama:/root/.ollama -p 11434:11434 "$RUN_OLLAMA_IMAGE")
  "${ollama_args[@]}"
  echo "GPU_MESH_MODE: pulling ${RUN_MODEL}"
  docker exec gpumesh-ollama ollama pull "$RUN_MODEL"
  if command -v timeout >/dev/null 2>&1; then
    timeout 180 docker exec gpumesh-ollama ollama run "$RUN_MODEL" "Reply with exactly: ok"
  else
    docker exec gpumesh-ollama ollama run "$RUN_MODEL" "Reply with exactly: ok"
  fi
  ps_out="$(docker exec gpumesh-ollama ollama ps || true)"
  echo "$ps_out"
  if [[ "$RUN_MODE" != "cpu" ]]; then
    if ! gpu_mode_ps_uses_gpu "$ps_out"; then
      echo "GPU_MESH_MODE: ollama ps did not show a GPU processor. The worker was not started." >&2
      echo "Check nvidia-container-toolkit (NVIDIA) or /dev/kfd and /dev/dri (AMD), then rerun." >&2
      exit 1
    fi
    echo "GPU_MESH_MODE: ollama ps shows a GPU processor for ${RUN_MODEL}."
  else
    echo "GPU_MESH_MODE: CPU Ollama is serving ${RUN_MODEL}."
  fi
  OLLAMA_HOST="$worker_host"
fi

docker pull "$IMAGE"
docker rm -f gpumesh-join >/dev/null 2>&1 || true
run_args=(docker run -d --name gpumesh-join --restart unless-stopped)
run_args+=(--add-host=host.docker.internal:host-gateway)
if [[ "$RUN_DOCKER_GPUS" == "all" ]]; then
  run_args+=(--gpus all)
  run_args+=(-e NVIDIA_VISIBLE_DEVICES=all)
  run_args+=(-e "NVIDIA_DRIVER_CAPABILITIES=compute,utility")
fi
if [[ -n "$RUN_DOCKER_DEVICES" ]]; then
  for dev in $RUN_DOCKER_DEVICES; do
    run_args+=(--device "$dev")
  done
fi
run_args+=(
  -e GPU_MESH_COORDINATOR="$COORD"
  -e GPU_MESH_BACKEND="$RUN_BACKEND"
  -e GPU_MESH_OLLAMA_HOST="$OLLAMA_HOST"
  -e GPU_MESH_INVITE="$INVITE"
  -e GPU_MESH_NAME="$NAME"
  -e GPU_MESH_PAYOUT_ADDRESS="$PAYOUT"
  -e GPU_MESH_ALLOW_CPU="$RUN_ALLOW_CPU"
  -e GPU_MESH_ACCELERATOR="$RUN_ACCEL"
  -e GPU_MESH_GPU_NAME="$RUN_GPU_NAME"
  -e GPU_MESH_VRAM_MB="$RUN_VRAM_MB"
  -e GPU_MESH_GPU_COUNT="$RUN_GPU_COUNT"
  -e GPU_MESH_GPU_DRIVER="$RUN_DRIVER"
  -v gpumesh-join:/var/lib/gpumesh
  "$IMAGE"
)
"${run_args[@]}"

echo "GPU_MESH_MODE: worker gpumesh-join is running against $COORD."
echo "GPU_MESH_MODE: accelerator=${RUN_ACCEL} gpu=${RUN_GPU_NAME} vram_mb=${RUN_VRAM_MB} backend=${RUN_BACKEND} model=${RUN_MODEL}."
echo "HHC from that coordinator is a utility credit for verified contribution."
echo "Logs: docker logs -f gpumesh-join"
