#!/usr/bin/env bash
# Roteiro automatico para compilar e testar o RangeRuntime (player) no Linux.
# Uso:
#   bash tools/linux/quickstart.sh                 -> instala deps, compila e instala
#   bash tools/linux/quickstart.sh /caminho/jogo.range  -> alem disso, roda o jogo no final
#
# Este script assume Debian/Ubuntu (apt). Ver docs/linux-build.md para detalhes e
# para outras distros (troque o bloco de instalacao de pacotes pelo gerenciador certo).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

PYTHON_VERSION="${PYTHON_VERSION:-3.11}"
GAME_RANGE="${1:-}"

step() { printf '\n=== %s ===\n' "$1"; }

step "1/5 - Verificando sistema"
if [ "$(uname -s)" != "Linux" ]; then
  echo "Este script deve ser executado em Linux." >&2
  exit 2
fi

if command -v apt >/dev/null 2>&1; then
  step "2/5 - Instalando dependencias (apt, pode pedir senha sudo)"
  sudo apt update
  sudo apt install -y build-essential cmake ninja-build git pkg-config \
    libx11-dev libxi-dev libxinerama-dev libxxf86vm-dev libxfixes-dev \
    libgl1-mesa-dev libglu1-mesa-dev libglew-dev \
    libsdl2-dev libopenal-dev libsndfile1-dev \
    libfreetype6-dev libpng-dev libjpeg-dev zlib1g-dev libtbb-dev \
    libboost-all-dev libfftw3-dev \
    "python${PYTHON_VERSION}" "python${PYTHON_VERSION}-dev" python3-numpy
else
  echo "Gerenciador de pacotes 'apt' nao encontrado. Instale manualmente as" >&2
  echo "dependencias listadas em docs/linux-build.md para sua distro e rode de novo." >&2
  exit 2
fi

step "3/5 - Checagem de ambiente (preflight)"
PYTHON_VERSION="$PYTHON_VERSION" bash tools/linux/preflight.sh

step "4/5 - Configurando e compilando (RangeRuntime, preset linux-runtime)"
cmake --preset linux-runtime -S source
cmake --build build-linux --target RangeRuntime -j"$(nproc)"
cmake --install build-linux

if [ -x "build-linux/bin/RangeRuntime" ]; then
  step "5/5 - Build concluido"
  echo "Executavel pronto em: build-linux/bin/RangeRuntime"
else
  echo "Build terminou mas build-linux/bin/RangeRuntime nao foi encontrado." >&2
  exit 1
fi

if [ -n "$GAME_RANGE" ]; then
  if [ -f "$GAME_RANGE" ]; then
    step "Rodando jogo: $GAME_RANGE"
    (cd build-linux/bin && ./RangeRuntime "$GAME_RANGE")
  else
    echo "Arquivo .range nao encontrado: $GAME_RANGE" >&2
    exit 1
  fi
else
  cat <<EOF

Para rodar um jogo depois:
  cd build-linux/bin
  ./RangeRuntime /caminho/para/seu_jogo.range

Ou rode este script de novo passando o caminho do .range como argumento.
EOF
fi
