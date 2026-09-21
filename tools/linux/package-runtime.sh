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
runtime_dir="${BIN_DIR:-$repo_root/build-linux/bin}"   # BIN_DIR=build-linux-editor/bin para o editor
dist_dir="$repo_root/build-linux/dist"
package_name="AnastacioEngine-${version}-linux-x86_64"
staging_dir="$dist_dir/$package_name"
archive="$dist_dir/$package_name.tar.xz"

if [ ! -x "$runtime_dir/RangeRuntime" ] && [ ! -x "$runtime_dir/RangeEngine" ]; then
  printf 'RangeRuntime/RangeEngine nao encontrado em %s. Execute cmake --install primeiro.\n' "$runtime_dir" >&2
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

# Torna o pacote portatil: embute o Python 3.11 isolado em python311/ e troca o RUNPATH absoluto
# (/opt/anastacio-python311/lib) por $ORIGIN/python311/lib. Sem isso o binario so abre na maquina de build
# ("libpython3.11.so.1.0: cannot open shared object file").
python_root="${PYTHON_ROOT_DIR:-/opt/anastacio-python311}"
if [ ! -e "$python_root/lib/libpython3.11.so.1.0" ]; then
  printf 'Python isolado nao encontrado em %s (rode tools/linux/install-python311.sh).\n' "$python_root" >&2
  exit 1
fi
mkdir -p "$staging_dir/python311"
cp -a "$python_root/lib" "$staging_dir/python311/lib"
find "$staging_dir/python311" -type d \( -name test -o -name tests -o -name __pycache__ \) -prune -exec rm -rf {} +

# Patch direto na string do ELF (sem depender de patchelf/chrpath); a nova string e menor e o resto vira NUL.
python3 - "$staging_dir" "$python_root/lib" <<'PY'
import os, sys
root, old = sys.argv[1], sys.argv[2].encode()
new = b"$ORIGIN/python311/lib"
assert len(new) <= len(old), "RUNPATH novo maior que o antigo"
patched = 0
for dirpath, _, files in os.walk(root):
    for name in files:
        path = os.path.join(dirpath, name)
        if os.path.islink(path) or not os.path.isfile(path):
            continue
        with open(path, "rb") as f:
            if f.read(4) != b"\x7fELF":
                continue
            f.seek(0)
            data = f.read()
        if old + b"\0" not in data:
            continue
        data = data.replace(old + b"\0", new + b"\0" * (len(old) - len(new) + 1))
        with open(path, "wb") as f:
            f.write(data)
        patched += 1
        print("RUNPATH ajustado:", os.path.relpath(path, root))
# Desde a mudanca nos CMakeLists o link ja grava $ORIGIN/lib (libpython copiado para bin/lib); o patch acima
# so age em builds antigos com o RUNPATH absoluto, por isso patched == 0 e aceitavel.
PY

# Confere que o libpython vai junto: em lib/ (RUNPATH $ORIGIN/lib do CMake) ou em python311/lib.
if [ ! -e "$staging_dir/lib/libpython3.11.so.1.0" ] && [ ! -e "$staging_dir/python311/lib/libpython3.11.so.1.0" ]; then
  printf 'libpython3.11.so.1.0 ausente do pacote.
' >&2
  exit 1
fi

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
