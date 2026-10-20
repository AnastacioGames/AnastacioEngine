#!/bin/bash
set -euo pipefail
# Build Linux do pacote no container, com imagem pronta e ccache:
#   bash tools/linux/container-build.sh            (VERSION=... e outras variaveis passam para dentro)
# A tag da imagem leva o hash das receitas: mudou container-deps-22.04.sh, install-python311.sh ou o
# Containerfile, a imagem e gerada de novo; senao reaproveita a que existe.
repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
tools="$repo_root/tools/linux"
hash="$(cat "$tools/Containerfile.22.04" "$tools/container-deps-22.04.sh" "$tools/install-python311.sh" \
  | sha256sum | cut -c1-12)"
image="localhost/anastacio-build:22.04-$hash"
if ! podman image exists "$image"; then
  podman build -t "$image" -f "$tools/Containerfile.22.04" "$tools"
fi
env_args=()
for var in VERSION WEB_RUNTIME_DIR SKIP_WEB CCACHE_MAXSIZE; do
  [ -n "${!var:-}" ] && env_args+=(-e "$var=${!var}")
done
exec podman run --rm "${env_args[@]}" -v "$repo_root:/work:Z" "$image" bash /work/tools/linux/container-build-22.04.sh
