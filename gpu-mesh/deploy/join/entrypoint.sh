#!/bin/sh
# Runs the existing gpu-mesh worker. llama.cpp is inside this image.
# Ollama is reached at GPU_MESH_OLLAMA_HOST when GPU_MESH_BACKEND=ollama.
set -eu
if [ -z "${GPU_MESH_COORDINATOR:-}" ]; then
  echo "Set GPU_MESH_COORDINATOR to the coordinator URL." >&2
  exit 1
fi
exec python -m gpumesh_node
