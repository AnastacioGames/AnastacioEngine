#!/usr/bin/env bash
# Empacota uma instalacao ja validada do RangeRuntime para Linux x86_64.

set -euo pipefail

if [ "$(uname -s)" != "Linux" ]; then
  printf 'Este script deve ser executado em Linux.\n' >&2
  exit 2
fi

if [ "$#" -ne 1 ]; then
  printf 'Uso: %s <versao>\n' "$0" >&2
  exit 2
fi

version="$1"
case "$version" in
  *[!A-Za-z0-9._-]*|'')
    printf 'A versao deve conter apenas letras, numeros, ponto, sublinhado ou hifen.\n' >&2
    exit 2
    ;;
esac

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
runtime_dir="$repo_root/build-linux/bin"
dist_dir="$repo_root/build-linux/dist"
package_name="AnastacioEngine-${version}-linux-x86_64"
staging_dir="$dist_dir/$package_name"
archive="$dist_dir/$package_name.tar.xz"

if [ ! -x "$runtime_dir/RangeRuntime" ]; then
  printf 'RangeRuntime nao encontrado em %s. Execute cmake --install build-linux primeiro.\n' "$runtime_dir" >&2
  exit 1
fi

if [ ! -f "$repo_root/source/COPYING" ]; then
  printf 'Arquivo de licenca ausente: %s\n' "$repo_root/source/COPYING" >&2
  exit 1
fi

rm -rf "$staging_dir"
mkdir -p "$staging_dir"
cp -a "$runtime_dir/." "$staging_dir/"
cp "$repo_root/source/COPYING" "$staging_dir/COPYING"

mkdir -p "$dist_dir"
rm -f "$archive" "$archive.sha256"
tar -C "$dist_dir" -cJf "$archive" "$package_name"
(
  cd "$dist_dir"
  sha256sum "$(basename "$archive")" > "$(basename "$archive").sha256"
)
rm -rf "$staging_dir"

printf 'Pacote criado: %s\n' "$archive"
printf 'Checksum: %s.sha256\n' "$archive"
