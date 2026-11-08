#!/usr/bin/env bash
# Install the GPU Mesh node as a non-root systemd service.
# The process runs as user gpumesh. Root is only used to create that user and the unit.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: install.sh [--coordinator URL] [--name NAME] [--backend auto|ollama|vllm|llamacpp]
                  [--gpu] [--cpu] [--ollama-host URL] [--vllm-host URL]
                  [--invite TOKEN] [--payout-address 0x…] [--uninstall] [--purge]

--gpu requires a visible NVIDIA or AMD GPU and selects Ollama when --backend is auto.
--cpu selects llama.cpp and SmolLM2-360M-Instruct. --payout-address is unchanged.

The coordinator URL is filled in when this script is downloaded from a coordinator.
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root so the gpumesh user and systemd unit can be installed." >&2
  echo "  curl -fsSL <coordinator>/install.sh | sudo bash -s -- --name my-rig" >&2
  exit 1
fi

COORD="__DEFAULT_COORDINATOR__"
NAME=""
BACKEND="auto"
ALLOW_CPU="0"
OLLAMA_HOST="http://127.0.0.1:11434"
VLLM_HOST="http://127.0.0.1:8000"
UNINSTALL="0"
PURGE="0"
INVITE=""
PAYOUT=""
WANT_GPU="0"
WANT_CPU="0"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --uninstall)
      UNINSTALL="1"
      shift
      ;;
    --purge)
      PURGE="1"
      shift
      ;;
    --coordinator)
      COORD="${2:-}"
      shift 2
      ;;
    --name)
      NAME="${2:-}"
      shift 2
      ;;
    --backend)
      BACKEND="${2:-}"
      shift 2
      ;;
    --allow-cpu)
      echo "cpu-fallback and mock-tiny cannot serve or earn. Use --backend llamacpp." >&2
      exit 2
      ;;
    --gpu)
      WANT_GPU="1"
      shift
      ;;
    --cpu)
      WANT_CPU="1"
      shift
      ;;
    --ollama-host)
      OLLAMA_HOST="${2:-}"
      shift 2
      ;;
    --vllm-host)
      VLLM_HOST="${2:-}"
      shift 2
      ;;
    --invite)
      INVITE="${2:-}"
      shift 2
      ;;
    --payout-address)
      PAYOUT="${2:-}"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ "$UNINSTALL" == "1" ]]; then
  if command -v systemctl >/dev/null 2>&1; then
    systemctl disable --now gpumesh-node.service || true
  fi
  rm -f /etc/systemd/system/gpumesh-node.service
  rm -rf /opt/gpumesh
  if [[ "$PURGE" == "1" ]]; then
    rm -rf /var/lib/gpumesh /etc/gpumesh
  fi
  if command -v systemctl >/dev/null 2>&1; then
    systemctl daemon-reload || true
  fi
  echo "GPU Mesh node removed."
  exit 0
fi

if [[ -z "$COORD" || "$COORD" == "__DEFAULT_COORDINATOR__" ]]; then
  echo "Pass --coordinator https://your-coordinator" >&2
  exit 2
fi
COORD="${COORD%/}"

if [[ "$COORD" =~ [[:space:]\'\"] ]]; then
  echo "Coordinator URL must not contain spaces or quotes." >&2
  exit 2
fi

case "$BACKEND" in
  auto|ollama|vllm|llamacpp) ;;
  cpu|cpu-fallback|mock|mock-tiny)
    echo "cpu-fallback and mock-tiny cannot serve or earn. Use --backend llamacpp." >&2
    exit 2
    ;;
  *)
    echo "Backend must be auto, ollama, vllm, or llamacpp." >&2
    exit 2
    ;;
esac

if [[ -n "$PAYOUT" && ! "$PAYOUT" =~ ^0x[0-9a-fA-F]{40}$ ]]; then
  echo "payout address must be a 0x EVM address." >&2
  exit 2
fi
if [[ "$PAYOUT" =~ ^0x0{40}$ ]]; then
  echo "payout address must not be the zero address." >&2
  exit 2
fi

if [[ -n "$INVITE" && ! "$INVITE" =~ ^[A-Za-z0-9_.:@+-]{8,128}$ ]]; then
  echo "Invite must be 8-128 characters: letters, digits, and _ . : @ + -" >&2
  exit 2
fi

if [[ "$WANT_GPU" == "1" && "$WANT_CPU" == "1" ]]; then
  echo "Pass only one of --gpu or --cpu." >&2
  exit 2
fi

gpu_mesh_source_mode() {
  local here="" mode_file=""
  if [[ -n "${BASH_SOURCE[0]:-}" && -f "${BASH_SOURCE[0]}" ]]; then
    here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  fi
  if [[ -n "$here" && -f "$here/../../deploy/join/gpu-mode.sh" ]]; then
    mode_file="$here/../../deploy/join/gpu-mode.sh"
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

gpu_mesh_source_mode
gpu_mode_detect
DETECTED_ACCEL="$GPU_ACCEL"
DETECTED_NAME="$GPU_NAME"
DETECTED_VRAM="$GPU_VRAM_MB"
if [[ "$WANT_GPU" == "1" && "$DETECTED_ACCEL" == "cpu" ]]; then
  echo "GPU_MESH_MODE: --gpu was passed but no NVIDIA or AMD GPU was detected." >&2
  exit 2
fi
RUN_ACCEL="$DETECTED_ACCEL"
if [[ "$WANT_CPU" == "1" || "$BACKEND" == "cpu" ]]; then
  RUN_ACCEL="cpu"
fi
if [[ "$BACKEND" == "auto" ]]; then
  if [[ "$RUN_ACCEL" == "cpu" ]]; then
    BACKEND="llamacpp"
    ALLOW_CPU="0"
  else
    BACKEND="ollama"
  fi
fi
if [[ "$RUN_ACCEL" == "cpu" ]]; then
  REPORT_ACCEL="cpu"
  REPORT_NAME="cpu"
  REPORT_VRAM="0"
  REPORT_COUNT="0"
  REPORT_DRIVER=""
  if [[ "$WANT_CPU" == "1" && "$DETECTED_ACCEL" != "cpu" ]]; then
    echo "GPU_MESH_MODE: CPU mode forced by --cpu. Detected ${DETECTED_ACCEL} ${DETECTED_NAME} (${DETECTED_VRAM} MiB) will not be registered."
  else
    echo "GPU_MESH_MODE: CPU mode. No NVIDIA or AMD GPU was detected. Inference backend is ${BACKEND}."
  fi
else
  REPORT_ACCEL="$DETECTED_ACCEL"
  REPORT_NAME="$DETECTED_NAME"
  REPORT_VRAM="$DETECTED_VRAM"
  REPORT_COUNT="$GPU_COUNT"
  REPORT_DRIVER="$GPU_DRIVER"
  echo "GPU_MESH_MODE: GPU mode ${REPORT_ACCEL}. ${REPORT_NAME}, ${REPORT_VRAM} MiB. Inference backend is ${BACKEND}."
fi

if [[ "$BACKEND" == "ollama" ]] && command -v ollama >/dev/null 2>&1; then
  OLLAMA_MODEL="$(gpu_mode_model "$REPORT_ACCEL" "$REPORT_VRAM")"
  echo "GPU_MESH_MODE: pulling ${OLLAMA_MODEL} with the native Ollama (CUDA when an NVIDIA GPU is visible)."
  ollama pull "$OLLAMA_MODEL"
  if command -v timeout >/dev/null 2>&1; then
    timeout 180 ollama run "$OLLAMA_MODEL" "Reply with exactly: ok"
  else
    ollama run "$OLLAMA_MODEL" "Reply with exactly: ok"
  fi
  ollama_ps="$(ollama ps || true)"
  echo "$ollama_ps"
  if [[ "$REPORT_ACCEL" != "cpu" ]]; then
    if ! gpu_mode_ps_uses_gpu "$ollama_ps"; then
      echo "GPU_MESH_MODE: ollama ps did not show a GPU processor. The service was not started." >&2
      exit 1
    fi
    echo "GPU_MESH_MODE: ollama ps shows a GPU processor for ${OLLAMA_MODEL}."
  else
    echo "GPU_MESH_MODE: CPU Ollama is serving ${OLLAMA_MODEL}."
  fi
fi

if [[ -z "$NAME" ]]; then
  NAME="$(hostname -s 2>/dev/null || hostname)-gpu"
fi
if [[ ! "$NAME" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]{0,62}$ ]]; then
  echo "Name must be 1-63 characters: letters, digits, dot, underscore, hyphen." >&2
  exit 2
fi

install_python() {
  if command -v apt-get >/dev/null 2>&1; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -y
    apt-get install -y python3 python3-venv python3-pip ca-certificates curl
  fi
}

if ! command -v python3 >/dev/null 2>&1 || ! command -v curl >/dev/null 2>&1; then
  install_python
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required." >&2
  exit 1
fi

if ! python3 - <<'PY'
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY
then
  echo "Python 3.11 or newer is required." >&2
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required." >&2
  exit 1
fi

if ! id gpumesh >/dev/null 2>&1; then
  useradd --system --create-home --home-dir /var/lib/gpumesh --shell /usr/sbin/nologin gpumesh
fi

install -d -o gpumesh -g gpumesh -m 0750 /var/lib/gpumesh
install -d -m 0755 /opt/gpumesh
install -d -m 0755 /etc/gpumesh

tmp="$(mktemp)"
curl -fsSL "$COORD/dl/gpumesh-node.tar.gz" -o "$tmp"
sum="$(mktemp)"
curl -fsSL "$COORD/dl/gpumesh-node.tar.gz.sha256" -o "$sum"
echo "$(awk '{print $1}' "$sum")  $tmp" | sha256sum -c -
rm -f "$sum"
tar -xzf "$tmp" -C /opt/gpumesh
rm -f "$tmp"

if [[ ! -x /opt/gpumesh/venv/bin/python ]]; then
  if ! python3 -m venv /opt/gpumesh/venv; then
    install_python
    python3 -m venv /opt/gpumesh/venv
  fi
fi
/opt/gpumesh/venv/bin/pip install --upgrade pip
/opt/gpumesh/venv/bin/pip install -r /opt/gpumesh/requirements.txt
if [[ "$BACKEND" == "llamacpp" ]]; then
  if command -v apt-get >/dev/null 2>&1; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -y
    apt-get install -y g++ cmake python3-dev libgomp1
  fi
  /opt/gpumesh/venv/bin/pip install 'llama-cpp-python>=0.3.4'
  install -d -o gpumesh -g gpumesh -m 0750 /var/lib/gpumesh/models
fi

umask 027
cat > /etc/gpumesh/node.env <<EOF
GPU_MESH_COORDINATOR=$COORD
GPU_MESH_NAME=$NAME
GPU_MESH_BACKEND=$BACKEND
GPU_MESH_ALLOW_CPU=$ALLOW_CPU
GPU_MESH_OLLAMA_HOST=$OLLAMA_HOST
GPU_MESH_VLLM_HOST=$VLLM_HOST
GPU_MESH_STATE=/var/lib/gpumesh/node.json
PYTHONPATH=/opt/gpumesh
PYTHONUNBUFFERED=1
EOF
if [[ -n "$INVITE" ]]; then
  printf 'GPU_MESH_INVITE=%s\n' "$INVITE" >> /etc/gpumesh/node.env
fi
if [[ -n "$PAYOUT" ]]; then
  printf 'GPU_MESH_PAYOUT_ADDRESS=%s\n' "$PAYOUT" >> /etc/gpumesh/node.env
fi
cat >> /etc/gpumesh/node.env <<EOF
GPU_MESH_ACCELERATOR=$REPORT_ACCEL
GPU_MESH_GPU_NAME=$REPORT_NAME
GPU_MESH_VRAM_MB=$REPORT_VRAM
GPU_MESH_GPU_COUNT=$REPORT_COUNT
GPU_MESH_GPU_DRIVER=$REPORT_DRIVER
EOF
echo "GPU_MESH_MODE: registered hardware accelerator=${REPORT_ACCEL} gpu=${REPORT_NAME} vram_mb=${REPORT_VRAM} backend=${BACKEND}."
if [[ "$BACKEND" == "llamacpp" ]]; then
  cat >> /etc/gpumesh/node.env <<'EOF'
GPU_MESH_MODEL_CACHE=/var/lib/gpumesh/models
GPU_MESH_LLAMA_THREADS=2
EOF
fi
chown root:gpumesh /etc/gpumesh/node.env
chmod 0640 /etc/gpumesh/node.env
chown -R gpumesh:gpumesh /opt/gpumesh

curl -fsSL "$COORD/gpumesh-node.service" -o /etc/systemd/system/gpumesh-node.service

if command -v systemctl >/dev/null 2>&1; then
  systemctl daemon-reload
  systemctl enable --now gpumesh-node.service
  echo "GPU Mesh node '$NAME' is running as user gpumesh."
  echo "Logs: journalctl -u gpumesh-node -f"
else
  echo "systemd is not available. The unit and env file are installed."
  echo "Start it with: su -s /bin/sh gpumesh -c '/opt/gpumesh/venv/bin/python -m gpumesh_node'"
fi
