#!/bin/sh
# Copy a Hugging Face Space tree into DEST. Does not log in, push, or create a Space.
# Usage: deploy/huggingface/assemble.sh /path/to/empty-space-checkout
set -eu
if [ "$#" -ne 1 ]; then
  echo "Usage: $0 DEST" >&2
  exit 2
fi
dest=$1
root=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)
mkdir -p "$dest"
cp "$root/pyproject.toml" "$root/LICENSE" "$dest/"
cp "$root/deploy/huggingface/Dockerfile" "$dest/Dockerfile"
cp "$root/deploy/huggingface/README.md" "$dest/README.md"
cp "$root/deploy/huggingface/start.sh" "$dest/start.sh"
chmod 755 "$dest/start.sh"
rm -rf "$dest/gpumesh" "$dest/gpumesh_node"
cp -a "$root/gpumesh" "$root/gpumesh_node" "$dest/"
find "$dest" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
echo "Assembled $dest"
echo "Next, from that directory: git add -A && git status"
echo "Do not commit a .gguf. Set Space secrets before the container starts."
