#!/usr/bin/env bash
# Install the GPU Mesh node as a non-root systemd service.
# The process runs as user gpumesh. Root is only used to create that user and the unit.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: install.sh [--coordinator URL] [--name NAME] [--backend auto|ollama|vllm|llamacpp|cpu]
                  [--allow-cpu] [--ollama-host URL] [--vllm-host URL]
                  [--invite TOKEN] [--uninstall] [--purge]

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
      ALLOW_CPU="1"
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
  auto|ollama|vllm|llamacpp|cpu) ;;
  *)
    echo "Backend must be auto, ollama, vllm, llamacpp, or cpu." >&2
    exit 2
    ;;
esac

if [[ -n "$INVITE" && ! "$INVITE" =~ ^[A-Za-z0-9_.:@+-]{8,128}$ ]]; then
  echo "Invite must be 8-128 characters: letters, digits, and _ . : @ + -" >&2
  exit 2
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
