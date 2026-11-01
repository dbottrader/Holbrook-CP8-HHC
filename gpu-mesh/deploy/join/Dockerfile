# One volunteer image. Build context is gpu-mesh/ (the directory that
# contains gpumesh_node/). llama-cpp-python is the same CPU worker already
# used by gpu-mesh/gpumesh_node/llamacpp.py. Ollama stays outside this image:
# set GPU_MESH_BACKEND=ollama and GPU_MESH_OLLAMA_HOST.
# image pin: the tag below.
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
RUN pip install --no-cache-dir 'httpx>=0.27' \
    && if [ "$WITH_LLAMA" = "1" ]; then pip install --no-cache-dir 'llama-cpp-python>=0.3.4'; fi \
    && chmod 755 /opt/gpumesh/entrypoint.sh

ENV PYTHONPATH=/opt/gpumesh \
    GPU_MESH_STATE=/var/lib/gpumesh/node.json \
    GPU_MESH_MODEL_CACHE=/var/lib/gpumesh/models \
    GPU_MESH_BACKEND=llamacpp \
    GPU_MESH_ALLOW_CPU=1 \
    PYTHONUNBUFFERED=1

VOLUME /var/lib/gpumesh
USER gpumesh
ENTRYPOINT ["/opt/gpumesh/entrypoint.sh"]
