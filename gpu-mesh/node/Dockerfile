# image pin: docker/IMAGE_PINS
FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends util-linux \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --create-home --uid 10001 --shell /usr/sbin/nologin gpumesh \
    && mkdir -p /var/lib/gpumesh /opt/gpumesh \
    && chown gpumesh:gpumesh /var/lib/gpumesh

WORKDIR /opt/gpumesh
COPY gpumesh_node /opt/gpumesh/gpumesh_node
COPY node/entrypoint.sh /opt/gpumesh/entrypoint.sh
RUN pip install --no-cache-dir 'httpx>=0.27' \
    && chmod 755 /opt/gpumesh/entrypoint.sh

ENV PYTHONPATH=/opt/gpumesh \
    GPU_MESH_STATE=/var/lib/gpumesh/node.json \
    GPU_MESH_ALLOW_CPU=1 \
    GPU_MESH_BACKEND=cpu \
    PYTHONUNBUFFERED=1

VOLUME /var/lib/gpumesh
USER gpumesh
ENTRYPOINT ["/opt/gpumesh/entrypoint.sh"]
