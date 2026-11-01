# image pin: docker/IMAGE_PINS
FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends util-linux \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --create-home --uid 10001 --shell /usr/sbin/nologin gpumesh \
    && mkdir -p /data \
    && chown gpumesh:gpumesh /data

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY gpumesh ./gpumesh
COPY gpumesh_node ./gpumesh_node
COPY docker/coordinator-entrypoint.sh /entrypoint.sh
RUN pip install --no-cache-dir '.[postgres]' \
    && chmod 755 /entrypoint.sh

ENV GPU_MESH_DATABASE_URL=sqlite:////data/gpumesh.db \
    GPU_MESH_DATA_DIR=/data \
    GPU_MESH_HOST=0.0.0.0 \
    GPU_MESH_PORT=8741 \
    PYTHONUNBUFFERED=1

EXPOSE 8741
VOLUME /data
ENTRYPOINT ["/entrypoint.sh"]
