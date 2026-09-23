#!/usr/bin/env bash
# Roteiro automatico para compilar o RangeEngine (editor completo) no Linux.
# Uso:
#   bash tools/linux/quickstart-editor.sh
#
# Preset ainda nao validado em Linux real (ver docs/linux-build.md). Espelha os
# WITH_* que o editor Windows (v142-ninja) usa por padrao: Compositor, OpenImageIO,
# OpenColorIO e FFmpeg ligados; Cycles/Alembic/OpenVDB desligados (o RangeEngine nao
# usa render offline nem compositor de VFX pesado, apenas nodes de material/textura).
#
# Este script assume Debian/Ubuntu (apt). Ver docs/linux-build.md para detalhes e
# para outras distros (troque o bloco de instalacao de pacotes pelo gerenciador certo).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

PYTHON_VERSION="${PYTHON_VERSION:-3.11}"
PYTHON_ROOT_DIR="${PYTHON_ROOT_DIR:-/opt/anastacio-python311}"
PYTHON_EXECUTABLE="${PYTHON_EXECUTABLE:-$PYTHON_ROOT_DIR/bin/python${PYTHON_VERSION}}"

step() { printf '\n=== %s ===\n' "$1"; }

step "1/5 - Verificando sistema"
if [ "$(uname -s)" != "Linux" ]; then
  echo "Este script deve ser executado em Linux." >&2
  exit 2
fi

if command -v apt >/dev/null 2>&1; then
  step "2/5 - Instalando dependencias de sistema (apt, pode pedir senha sudo)"
  # Mesma base do RangeRuntime (tools/linux/quickstart.sh), mais as libs que o
  # editor liga por padrao: OpenImageIO, OpenColorIO e o conjunto do FFmpeg.
  sudo apt update
  sudo apt install -y build-essential cmake ninja-build git pkg-config \
    libx11-dev libxi-dev libxinerama-dev libxxf86vm-dev libxfixes-dev \
    libgl1-mesa-dev libglu1-mesa-dev libglew-dev \
    libsdl2-dev libopenal-dev libsndfile1-dev \
    libfreetype6-dev libpng-dev libjpeg-dev zlib1g-dev libtbb-dev \
    libboost-all-dev libfftw3-dev \
    libopenimageio-dev libopencolorio-dev \
    libavformat-dev libavcodec-dev libavdevice-dev libavutil-dev \
    libswscale-dev libswresample-dev \
    libtheora-dev libvorbis-dev libogg-dev libvpx-dev libx264-dev
else
  echo "Gerenciador de pacotes 'apt' nao encontrado. Instale manualmente as" >&2
  echo "dependencias listadas em docs/linux-build.md para sua distro e rode de novo." >&2
  exit 2
fi

step "3/5 - Garantindo CPython ${PYTHON_VERSION} isolado em $PYTHON_ROOT_DIR"
bash tools/linux/install-python311.sh

step "4/5 - Checagem de ambiente (preflight)"
PYTHON_VERSION="$PYTHON_VERSION" PYTHON_EXECUTABLE="$PYTHON_EXECUTABLE" bash tools/linux/preflight.sh

step "5/5 - Configurando e compilando (RangeEngine, preset linux-editor)"
cmake --preset linux-editor -S source
cmake --build build-linux-editor --target RangeEngine -j"$(nproc)"
cmake --install build-linux-editor

if [ -x "build-linux-editor/bin/RangeEngine" ]; then
  echo
  echo "Build concluido. Executavel pronto em: build-linux-editor/bin/RangeEngine"
  echo "Se alguma dependencia (FFmpeg/OpenImageIO/OpenColorIO) nao foi encontrada,"
  echo "o CMake desliga a flag correspondente sozinho e mostra um aviso no log de"
  echo "configuracao acima -- releia-o se algum recurso do editor faltar em runtime."
else
  echo "Build terminou mas build-linux-editor/bin/RangeEngine nao foi encontrado." >&2
  exit 1
fi
