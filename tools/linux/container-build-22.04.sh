#!/bin/bash
set -euxo pipefail
# Roda DENTRO de um container ubuntu:22.04 (glibc 2.35), com o repo montado em /work:
#   podman run --rm -v $PWD:/work:Z -v $PWD/tools/linux/container-build-22.04.sh:/build.sh:Z \
#     docker.io/library/ubuntu:22.04 /build.sh
# Use um clone separado: os build-linux*/ do container nao servem para a maquina host.
export DEBIAN_FRONTEND=noninteractive TZ=Etc/UTC
ln -fs /usr/share/zoneinfo/Etc/UTC /etc/localtime; echo Etc/UTC > /etc/timezone
apt-get update
apt-get install -y tzdata sudo python3-pip build-essential ninja-build git pkg-config wget \
  libx11-dev libxi-dev libxinerama-dev libxxf86vm-dev libxfixes-dev \
  libgl1-mesa-dev libglu1-mesa-dev libglew-dev \
  libsdl2-dev libopenal-dev libsndfile1-dev \
  libfreetype6-dev libpng-dev libjpeg-dev zlib1g-dev libtbb-dev \
  libboost-all-dev libfftw3-dev \
  libopenimageio-dev libopencolorio-dev libembree-dev libopenexr-dev libpugixml-dev libtiff-dev \
  libavformat-dev libavcodec-dev libavdevice-dev libavutil-dev \
  libswscale-dev libswresample-dev \
  libtheora-dev libvorbis-dev libogg-dev libvpx-dev libx264-dev
pip3 install 'cmake>=3.28,<4'
hash -r
cd /work
[ -x /opt/anastacio-python311/bin/python3.11 ] || bash tools/linux/install-python311.sh
cmake --preset linux-editor -S source
# O install do preset editor tambem instala o RangeRuntime, entao os dois alvos sao compilados aqui.
cmake --build build-linux-editor --target RangeEngine RangeRuntime -j16
cmake --install build-linux-editor
cmake --preset linux-runtime -S source
cmake --build build-linux --target RangeRuntime -j16
cmake --install build-linux
BIN_DIR=build-linux-editor/bin EXTRA_BIN_DIR=build-linux/bin bash tools/linux/package-runtime.sh 0.4.4
