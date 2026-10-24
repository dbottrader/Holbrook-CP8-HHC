#!/bin/sh
# Root only long enough to make the data volume writable, then drop to gpumesh.
set -e
mkdir -p /data
chown gpumesh:gpumesh /data
if [ "$(id -u)" = "0" ]; then
  exec setpriv --reuid=gpumesh --regid=gpumesh --init-groups --inh-caps=-all \
    python -m uvicorn gpumesh.main:create_app --factory --host 0.0.0.0 --port 8741
fi
exec python -m uvicorn gpumesh.main:create_app --factory --host 0.0.0.0 --port 8741
