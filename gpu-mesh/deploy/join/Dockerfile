# One volunteer image. Build context is gpu-mesh/ (the directory that
# contains gpumesh_node/). llama.cpp is the CPU worker already used by
# gpu-mesh/gpumesh_node/llamacpp.py. This image does not bake a CUDA wheel.
# NVIDIA passthrough is a runtime flag (--gpus all, or Compose
# deploy.resources.reservations.devices with driver nvidia and
# capabilities: [gpu]). The NVIDIA Container Toolkit then mounts nvidia-smi.
# AMD is the ollama/ollama:rocm container with /dev/kfd and /dev/dri.
# Ollama stays outside this image: GPU_MESH_BACKEND=ollama and
# GPU_MESH_OLLAMA_HOST. The official ollama/ollama tag is the CUDA build
# and uses the GPU when the device is passed through.
#
# PyPI llama-cpp-python 0.3.36 is a source tarball. The main publish
# (Actions run 41285393780) failed in that build: CMake had no C or C++
# compiler. The CPU binary is the v0.3.36 GitHub release wheel, the tag
# with no CUDA, HIP, or Vulkan suffix. --only-binary refuses a source build.
FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --create-home --uid 10001 --shell /usr/sbin/nologin gpumesh \
    && mkdir -p /var/lib/gpumesh/models \
    && chown -R gpumesh:gpumesh /var/lib/gpumesh

WORKDIR /opt/gpumesh
COPY gpumesh_node /opt/gpumesh/gpumesh_node
COPY deploy/join/entrypoint.sh /opt/gpumesh/entrypoint.sh

ARG WITH_LLAMA=1
ARG LLAMA_CPP_VERSION=0.3.36
ARG LLAMA_CPP_WHEEL=llama_cpp_python-0.3.36-py3-none-manylinux2014_x86_64.manylinux_2_17_x86_64.whl
RUN pip install --no-cache-dir 'httpx==0.28.1' \
    && if [ "$WITH_LLAMA" = "1" ]; then \
         pip install --no-cache-dir --only-binary=:all: \
           "https://github.com/abetlen/llama-cpp-python/releases/download/v${LLAMA_CPP_VERSION}/${LLAMA_CPP_WHEEL}"; \
       fi \
    && chmod 755 /opt/gpumesh/entrypoint.sh

ENV PYTHONPATH=/opt/gpumesh \
    GPU_MESH_STATE=/var/lib/gpumesh/node.json \
    GPU_MESH_MODEL_CACHE=/var/lib/gpumesh/models \
    GPU_MESH_BACKEND=llamacpp \
    GPU_MESH_ALLOW_CPU=1 \
    GPU_MESH_COORDINATOR=https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/gpu-mesh \
    PYTHONUNBUFFERED=1

VOLUME /var/lib/gpumesh
USER gpumesh
ENTRYPOINT ["/opt/gpumesh/entrypoint.sh"]
