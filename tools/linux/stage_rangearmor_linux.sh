#!/bin/bash
# Monta RangeArmor-<versao>-linux-x86_64.tar.xz: painel Rust compilado no Linux + release/ do git
# (data, icons, scripts) + release/launcher/ do zip Windows da mesma versao (Launcher Linux, Launcher.exe e
# launcher.py minificado; os launchers nao ficam no git). Ver docs/release-0.5.3.md.
# Painel (glibc max. 2.30), na raiz do repo:
#   podman run --rm -v $PWD/tools/rangearmor:/ra:Z -v <target>:/target:Z -e CARGO_TARGET_DIR=/target \
#     docker.io/library/rust:1.95-bullseye bash -c "cd /ra/source/gui-rs && cargo build --release --locked"
#   TARGET_DIR=<target> WIN_LAUNCHER_DIR=<zip extraido>/release/launcher \
#     bash tools/linux/stage_rangearmor_linux.sh 0.5.3
set -euo pipefail
version="${1:?uso: stage_rangearmor_linux.sh <versao>}"
repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
panel="${TARGET_DIR:?TARGET_DIR com release/rangearmor_panel}/release/rangearmor_panel"
launchers="${WIN_LAUNCHER_DIR:?WIN_LAUNCHER_DIR com o release/launcher do zip Windows}"
pkg="RangeArmor-$version-linux-x86_64"
out="${OUT_DIR:-$repo_root/build-linux/dist}"
stage="$repo_root/build-linux/release-staging/$pkg"
ra="$repo_root/tools/rangearmor"

rm -rf "$stage"; mkdir -p "$stage/release" "$out"
cp -r "$ra/release/data" "$ra/release/icons" "$ra/release/scripts" "$stage/release/"
cp -r "$launchers" "$stage/release/launcher"
find "$stage" -name __pycache__ -prune -exec rm -rf {} +
install -m755 "$panel" "$stage/RangeArmor Panel"
strip "$stage/RangeArmor Panel"
chmod +x "$stage/release/launcher/Launcher"
cp "$ra/LICENSE" "$stage/LICENSE"
# O Launcher Linux registrado em legacy-template-sha256.json/release-0.5.2.md e o 3cb1ade9...
sha256sum "$stage/release/launcher/Launcher" | grep -q '^3cb1ade91d3440c3'

tar -C "$(dirname "$stage")" -cJf "$out/$pkg.tar.xz" "$pkg"
(cd "$out" && sha256sum "$pkg.tar.xz" | tee "$pkg.tar.xz.sha256")
