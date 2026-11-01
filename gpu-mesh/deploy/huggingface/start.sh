#!/bin/sh
# One container: the coordinator, then one llama.cpp CPU worker.
# A second worker has to join from outside before a spot-check can record HHC.
set -eu

PORT="${PORT:-7860}"
export GPU_MESH_HOST=0.0.0.0
export GPU_MESH_PORT="$PORT"
export GPU_MESH_DATA_DIR="${GPU_MESH_DATA_DIR:-/data}"
export GPU_MESH_DATABASE_URL="${GPU_MESH_DATABASE_URL:-sqlite:////data/gpumesh.db}"
export GPU_MESH_MODEL_CACHE="${GPU_MESH_MODEL_CACHE:-$GPU_MESH_DATA_DIR/models}"
export GPU_MESH_STATE="${GPU_MESH_STATE:-$GPU_MESH_DATA_DIR/nodes/space-cpu.json}"
export GPU_MESH_BACKEND="${GPU_MESH_BACKEND:-llamacpp}"
export GPU_MESH_NAME="${GPU_MESH_NAME:-space-cpu}"
export GPU_MESH_COORDINATOR="http://127.0.0.1:${PORT}"
export GPU_MESH_LLAMA_THREADS="${GPU_MESH_LLAMA_THREADS:-2}"

mkdir -p "$GPU_MESH_DATA_DIR/models" "$GPU_MESH_DATA_DIR/nodes"

if [ -z "${GPU_MESH_ADMIN_TOKEN:-}" ]; then
  echo "Set GPU_MESH_ADMIN_TOKEN in the Space secrets. It is not generated into the public log." >&2
  exit 1
fi
if [ "${GPU_MESH_INVITE_ONLY:-1}" = "1" ]; then
  if [ -z "${GPU_MESH_INVITE_TOKEN:-}" ]; then
    echo "Set GPU_MESH_INVITE_TOKEN in the Space secrets. The CPU worker and volunteers use that invite." >&2
    exit 1
  fi
  if [ -z "${GPU_MESH_INVITE:-}" ]; then
    export GPU_MESH_INVITE="$GPU_MESH_INVITE_TOKEN"
  fi
fi

python -m uvicorn gpumesh.main:create_app --factory --host 0.0.0.0 --port "$PORT" &
coord_pid=$!

i=0
until python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:${PORT}/health')" >/dev/null 2>&1; do
  i=$((i + 1))
  if ! kill -0 "$coord_pid" 2>/dev/null; then
    echo "coordinator exited before it was healthy" >&2
    exit 1
  fi
  if [ "$i" -gt 60 ]; then
    echo "coordinator did not become healthy" >&2
    kill "$coord_pid" 2>/dev/null || true
    exit 1
  fi
  sleep 1
done

python -m gpumesh_node &
worker_pid=$!

cleanup() {
  kill "$coord_pid" "$worker_pid" 2>/dev/null || true
}
trap cleanup INT TERM

while kill -0 "$coord_pid" 2>/dev/null && kill -0 "$worker_pid" 2>/dev/null; do
  sleep 2
done
cleanup
exit 1
