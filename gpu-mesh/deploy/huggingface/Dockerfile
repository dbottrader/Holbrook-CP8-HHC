# Hugging Face Spaces, Docker SDK, free CPU.
# Build context is an assembled Space root (see assemble.sh), not the
# Holbrook monorepo. Weights are not copied in. The process downloads the
# pinned SmolLM2 GGUF on first start.
# image pin: the tag below. Do not float this to :latest in a fork without noticing.
FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        cmake \
        g++ \
        libgomp1 \
        python3-dev \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /data/models /data/nodes

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY gpumesh ./gpumesh
COPY gpumesh_node ./gpumesh_node
COPY start.sh /start.sh

# CPU wheel or a source build. GGML_NATIVE=OFF keeps the image runnable on
# the Space CPU, which is not the machine that built it.
ENV CMAKE_ARGS="-DGGML_NATIVE=OFF" \
    FORCE_CMAKE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
RUN pip install --no-cache-dir '.[cpu]' \
    && chmod 755 /start.sh \
    && apt-get purge -y cmake g++ python3-dev \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

ENV GPU_MESH_HOST=0.0.0.0 \
    GPU_MESH_DATA_DIR=/data \
    GPU_MESH_DATABASE_URL=sqlite:////data/gpumesh.db \
    GPU_MESH_MODEL_CACHE=/data/models \
    GPU_MESH_STATE=/data/nodes/space-cpu.json \
    GPU_MESH_BACKEND=llamacpp \
    GPU_MESH_NAME=space-cpu \
    GPU_MESH_LLAMA_THREADS=2 \
    GPU_MESH_INVITE_ONLY=1 \
    GPU_MESH_TRUST_PROXY=1 \
    GPU_MESH_JOB_TIMEOUT_SEC=180 \
    GPU_MESH_REQUEST_TIMEOUT_SEC=180 \
    PORT=7860 \
    PYTHONUNBUFFERED=1

EXPOSE 7860
CMD ["/start.sh"]
