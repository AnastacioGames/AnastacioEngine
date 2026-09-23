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
PYTHON_ROOT_DIR="${PYTHON_ROOT_DIR:-/opt/anastacio-python311}"
PYTHON_EXECUTABLE="${PYTHON_EXECUTABLE:-$PYTHON_ROOT_DIR/bin/python${PYTHON_VERSION}}"
GAME_RANGE="${1:-}"

step() { printf '\n=== %s ===\n' "$1"; }

step "1/6 - Verificando sistema"
if [ "$(uname -s)" != "Linux" ]; then
  echo "Este script deve ser executado em Linux." >&2
  exit 2
fi

if command -v apt >/dev/null 2>&1; then
  step "2/6 - Instalando dependencias de sistema (apt, pode pedir senha sudo)"
  sudo apt update
  sudo apt install -y build-essential cmake ninja-build git pkg-config \
    libx11-dev libxi-dev libxinerama-dev libxxf86vm-dev libxfixes-dev \
    libgl1-mesa-dev libglu1-mesa-dev libglew-dev \
    libsdl2-dev libopenal-dev libsndfile1-dev \
    libfreetype6-dev libpng-dev libjpeg-dev zlib1g-dev libtbb-dev \
    libboost-all-dev libfftw3-dev
else
  echo "Gerenciador de pacotes 'apt' nao encontrado. Instale manualmente as" >&2
  echo "dependencias listadas em docs/linux-build.md para sua distro e rode de novo." >&2
  exit 2
fi

step "3/6 - Garantindo CPython ${PYTHON_VERSION} isolado em $PYTHON_ROOT_DIR"
# Distros recentes (Ubuntu 24.04+ inclusive) nao tem mais o pacote python3.11 no apt;
# o preset linux-runtime exige esse ABI especificamente, entao compilamos a parte se
# ainda nao existir (script e idempotente).
bash tools/linux/install-python311.sh

step "4/6 - Checagem de ambiente (preflight)"
PYTHON_VERSION="$PYTHON_VERSION" PYTHON_EXECUTABLE="$PYTHON_EXECUTABLE" bash tools/linux/preflight.sh

step "5/6 - Configurando e compilando (RangeRuntime, preset linux-runtime)"
cmake --preset linux-runtime -S source
cmake --build build-linux --target RangeRuntime -j"$(nproc)"
cmake --install build-linux

if [ -x "build-linux/bin/RangeRuntime" ]; then
  step "6/6 - Build concluido"
  echo "Executavel pronto em: build-linux/bin/RangeRuntime"
else
  echo "Build terminou mas build-linux/bin/RangeRuntime nao foi encontrado." >&2
  exit 1
fi

# Notebooks com grafica hibrida Intel+NVIDIA (Optimus/PRIME) renderizam na Intel
# por padrao mesmo com driver NVIDIA instalado, deixando o jogo lento e sem
# aproveitar a GPU dedicada. Se um provider NVIDIA de offload estiver disponivel
# (xrandr --listproviders lista "NVIDIA-G0" nesse caso), forcamos o uso dela.
NVIDIA_OFFLOAD_ENV=()
if command -v xrandr >/dev/null 2>&1 && xrandr --listproviders 2>/dev/null | grep -q "NVIDIA-G0"; then
  NVIDIA_OFFLOAD_ENV=(env __NV_PRIME_RENDER_OFFLOAD=1 __GLX_VENDOR_LIBRARY_NAME=nvidia)
  echo "GPU NVIDIA (Optimus/PRIME) detectada: rodando com offload para a dedicada."
fi

if [ -n "$GAME_RANGE" ]; then
  if [ -f "$GAME_RANGE" ]; then
    step "Rodando jogo: $GAME_RANGE"
    (cd build-linux/bin && "${NVIDIA_OFFLOAD_ENV[@]}" ./RangeRuntime "$GAME_RANGE")
  else
    echo "Arquivo .range nao encontrado: $GAME_RANGE" >&2
    exit 1
  fi
else
  if [ "${#NVIDIA_OFFLOAD_ENV[@]}" -gt 0 ]; then
    cat <<EOF

Para rodar um jogo depois (notebook com GPU NVIDIA hibrida detectada, use o offload):
  cd build-linux/bin
  __NV_PRIME_RENDER_OFFLOAD=1 __GLX_VENDOR_LIBRARY_NAME=nvidia ./RangeRuntime /caminho/para/seu_jogo.range

Ou rode este script de novo passando o caminho do .range como argumento.
EOF
  else
    cat <<EOF

Para rodar um jogo depois:
  cd build-linux/bin
  ./RangeRuntime /caminho/para/seu_jogo.range

Ou rode este script de novo passando o caminho do .range como argumento.
EOF
  fi
fi
