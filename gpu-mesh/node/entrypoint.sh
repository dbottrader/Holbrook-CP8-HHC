#!/bin/sh
# Prefer to start already as uid 10001. Dropping from root needs CAP_SETUID,
# which a hardened container (cap_drop: ALL) does not have.
set -e
if [ "$(id -u)" = "0" ]; then
  mkdir -p /var/lib/gpumesh
  chown gpumesh:gpumesh /var/lib/gpumesh
  exec setpriv --reuid=gpumesh --regid=gpumesh --init-groups --inh-caps=-all python -m gpumesh_node
fi
exec python -m gpumesh_node
