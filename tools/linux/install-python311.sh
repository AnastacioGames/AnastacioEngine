#!/usr/bin/env bash
# Compila e instala CPython 3.11 isolado em /opt/anastacio-python311, exatamente o
# PYTHON_ROOT_DIR esperado pelo preset `linux-runtime` (source/CMakePresets.json).
#
# Motivo de existir: distros recentes (Ubuntu 24.04+ inclusive) nao trazem mais o pacote
# `python3.11`/`python3.11-dev` no apt (so o Python "do sistema" da distro, ex: 3.12, 3.13...).
# O preset exige o ABI 3.11 especificamente, entao compilamos a partir do codigo-fonte oficial
# em vez de depender do que o apt tiver disponivel.
#
# Uso:
#   bash tools/linux/install-python311.sh
#   PYTHON_FULL_VERSION=3.11.10 bash tools/linux/install-python311.sh   # outra versao 3.11.x
#   FORCE=1 bash tools/linux/install-python311.sh                       # forca recompilar mesmo se ja existir
#
# Idempotente: se $PREFIX/bin/python3.11 ja existir, so reexecuta se FORCE=1.

set -euo pipefail

PYTHON_FULL_VERSION="${PYTHON_FULL_VERSION:-3.11.9}"
PREFIX="${PREFIX:-/opt/anastacio-python311}"
FORCE="${FORCE:-0}"

step() { printf '\n=== %s ===\n' "$1"; }

if [ "$(uname -s)" != "Linux" ]; then
  echo "Este script deve ser executado em Linux." >&2
  exit 2
fi

if [ -x "$PREFIX/bin/python3.11" ] && [ "$FORCE" != "1" ]; then
  step "Python 3.11 ja instalado em $PREFIX"
  "$PREFIX/bin/python3.11" --version
  echo "Use FORCE=1 para recompilar."
  exit 0
fi

step "1/5 - Instalando dependencias de build do CPython (apt, pode pedir senha sudo)"
sudo apt update
sudo apt install -y \
  build-essential gdb lcov pkg-config \
  libbz2-dev libffi-dev libgdbm-dev libgdbm-compat-dev liblzma-dev \
  libncurses-dev libreadline-dev libsqlite3-dev libssl-dev \
  lzma lzma-dev tk-dev uuid-dev zlib1g-dev wget

step "2/5 - Preparando diretorio de instalacao ($PREFIX)"
if [ ! -d "$PREFIX" ]; then
  sudo mkdir -p "$PREFIX"
fi
sudo chown -R "$(id -u):$(id -g)" "$PREFIX"

step "3/5 - Baixando e extraindo Python $PYTHON_FULL_VERSION"
BUILD_DIR="$(mktemp -d)"
trap 'rm -rf "$BUILD_DIR"' EXIT
cd "$BUILD_DIR"
wget -q "https://www.python.org/ftp/python/${PYTHON_FULL_VERSION}/Python-${PYTHON_FULL_VERSION}.tar.xz"
tar xf "Python-${PYTHON_FULL_VERSION}.tar.xz"
cd "Python-${PYTHON_FULL_VERSION}"

step "4/5 - Configurando e compilando (pode levar alguns minutos)"
./configure \
  --prefix="$PREFIX" \
  --enable-shared \
  --with-ensurepip=install \
  LDFLAGS="-Wl,-rpath,$PREFIX/lib"
make -j"$(nproc)"

step "5/5 - Instalando (make altinstall, nao mexe no python3 do sistema)"
make altinstall

"$PREFIX/bin/python3.11" --version
"$PREFIX/bin/python3.11" -m pip install --upgrade pip numpy

cat <<EOF

Python 3.11 instalado em: $PREFIX
Proximos passos (ver docs/linux-build.md):
  PYTHON_EXECUTABLE=$PREFIX/bin/python3.11 bash tools/linux/preflight.sh
  cmake --preset linux-runtime -S source
EOF
