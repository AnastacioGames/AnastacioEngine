#!/bin/bash
set -euxo pipefail
# Roda DENTRO de um container ubuntu:22.04 (glibc 2.35), com o repo montado em /work. Jeito normal:
#   bash tools/linux/container-build.sh
# que usa a imagem com as dependencias ja instaladas. Sem imagem (mais lento, instala tudo a cada vez):
#   podman run --rm -v $PWD:/work:Z -v $PWD/tools/linux/container-build-22.04.sh:/build.sh:Z \
#     docker.io/library/ubuntu:22.04 /build.sh
# Use um clone separado: os build-linux*/ do container nao servem para a maquina host.
[ -e /etc/anastacio-build-deps ] || bash /work/tools/linux/container-deps-22.04.sh
cd /work
# Sem pipe com grep -q: com pipefail o SIGPIPE (141) derruba o script.
ldconfig -p > /tmp/ldcache.txt
grep -m1 'libsndfile.so.1 ' /tmp/ldcache.txt | grep /usr/local/lib
# ccache em /work/.ccache-linux: sobrevive ao --rm do container.
export CCACHE_DIR=/work/.ccache-linux CCACHE_MAXSIZE=${CCACHE_MAXSIZE:-20G}
launcher="-DCMAKE_C_COMPILER_LAUNCHER=ccache -DCMAKE_CXX_COMPILER_LAUNCHER=ccache"
cmake --preset linux-editor -S source $launcher
# O install do preset editor tambem instala o RangeRuntime, entao os dois alvos sao compilados aqui.
cmake --build build-linux-editor --target RangeEngine RangeRuntime -j$(nproc)
cmake --install build-linux-editor
cmake --preset linux-runtime -S source $launcher
cmake --build build-linux --target RangeRuntime -j$(nproc)
cmake --install build-linux
BIN_DIR=build-linux-editor/bin EXTRA_BIN_DIR=build-linux/bin bash tools/linux/package-runtime.sh "${VERSION:-0.5.4}"
# O pacote tem que levar a libsndfile com MP3 (ver acima).
pkg=AnastacioEngine-"${VERSION:-0.5.4}"-linux-x86_64
tar -xOJf build-linux/dist/$pkg.tar.xz $pkg/lib/libsndfile.so.1 > /tmp/libsndfile-pkg.so
grep -aq 'libsndfile-1\.2\.2' /tmp/libsndfile-pkg.so
# E a OCIO 1.1.1 do apt (libopencolorio-dev, a API 1.x que o intern/opencolorio usa): biblioteca e configs.
tar -tJf build-linux/dist/$pkg.tar.xz > /tmp/pkg-list.txt
grep -q "$pkg/AnastacioEngine" /tmp/pkg-list.txt
grep -q "$pkg/AnastacioRuntime" /tmp/pkg-list.txt
if grep -q "$pkg/RangeEngine$\|$pkg/RangeRuntime$" /tmp/pkg-list.txt; then exit 1; fi
grep -q "$pkg/lib/libOpenColorIO.so.1" /tmp/pkg-list.txt
grep -q "$pkg/2.79/datafiles/colormanagement/config.ocio" /tmp/pkg-list.txt
# Arquivos novos da 0.5.0: bibliotecas do bake (UV atlas e denoise), atlas de icones e modulo de rede.
grep -q "$pkg/libae_uvatlas.so" /tmp/pkg-list.txt
# O OIDN nao esta no apt do 22.04: sem ele o ae_denoise nao e compilado e o bake usa o box blur.
if [ -e build-linux-editor/bin/libae_denoise.so ]; then grep -q "$pkg/libae_denoise.so" /tmp/pkg-list.txt; fi
grep -q "$pkg/2.79/datafiles/icons_upbge/" /tmp/pkg-list.txt
grep -q "$pkg/2.79/datafiles/icons_blender5/" /tmp/pkg-list.txt
grep -q "$pkg/2.79/datafiles/sounds/effects/trovao1.wav" /tmp/pkg-list.txt
grep -q "$pkg/2.79/scripts/modules/anastacio_network/" /tmp/pkg-list.txt
grep -q "$pkg/2.79/python/bin/python3.11" /tmp/pkg-list.txt
if grep -q "Range_Components_Label.rar" /tmp/pkg-list.txt; then exit 1; fi
ccache -s
