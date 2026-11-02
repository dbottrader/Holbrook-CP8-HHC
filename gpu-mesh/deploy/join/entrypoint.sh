#!/bin/sh
# Runs the existing gpu-mesh worker. llama.cpp is inside this image.
# Ollama is reached at GPU_MESH_OLLAMA_HOST when GPU_MESH_BACKEND=ollama.
set -eu
export GPU_MESH_COORDINATOR="${GPU_MESH_COORDINATOR:-https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/gpu-mesh}"
exec python -m gpumesh_node
