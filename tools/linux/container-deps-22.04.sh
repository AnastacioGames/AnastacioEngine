#!/bin/bash
set -euxo pipefail
# Dependencias do build Linux num ubuntu:22.04: pacotes do apt, cmake, ccache, libsndfile 1.2.2 e o
# Python 3.11 isolado. Roda uma vez na imagem (Containerfile.22.04) ou, sem imagem, a cada build.
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
  libtheora-dev libvorbis-dev libogg-dev libvpx-dev libx264-dev \
  libflac-dev libopus-dev libmpg123-dev libmp3lame-dev ccache
pip3 install 'cmake>=3.28,<4'
hash -r
# A libsndfile do 22.04 (1.0.31) nao le MP3 (so a partir da 1.1.0) e o FFmpeg fica desligado no Linux:
# sem isto o aud/Sound actuator falha em todo .mp3. Compila a 1.2.2 em /usr/local, que o ld.so.cache
# resolve antes da do sistema; o package-runtime.sh empacota esta.
if ! [ -e /usr/local/lib/libsndfile.so.1 ]; then
  wget -qO /tmp/libsndfile.tar.xz \
    https://github.com/libsndfile/libsndfile/releases/download/1.2.2/libsndfile-1.2.2.tar.xz
  tar --no-same-owner -xJf /tmp/libsndfile.tar.xz -C /tmp
  cmake -S /tmp/libsndfile-1.2.2 -B /tmp/libsndfile-build -G Ninja -DCMAKE_BUILD_TYPE=Release \
    -DBUILD_SHARED_LIBS=ON -DBUILD_PROGRAMS=OFF -DBUILD_EXAMPLES=OFF -DBUILD_TESTING=OFF \
    -DENABLE_MPEG=ON -DENABLE_EXTERNAL_LIBS=ON -DCMAKE_INSTALL_PREFIX=/usr/local -DCMAKE_INSTALL_LIBDIR=lib
  cmake --build /tmp/libsndfile-build
  cmake --install /tmp/libsndfile-build
  ldconfig
fi
# Sem pipe com grep -q: com pipefail o SIGPIPE (141) derruba o script.
ldconfig -p > /tmp/ldcache.txt
grep -m1 'libsndfile.so.1 ' /tmp/ldcache.txt | grep /usr/local/lib
[ -x /opt/anastacio-python311/bin/python3.11 ] || bash "$(dirname "$0")/install-python311.sh"
rm -rf /var/lib/apt/lists/* /tmp/libsndfile*
touch /etc/anastacio-build-deps
