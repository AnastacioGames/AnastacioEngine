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
extra_dir="${EXTRA_BIN_DIR:-}"                          # o outro dir (editor OU runtime) para empacotar os dois juntos
dist_dir="$repo_root/build-linux/dist"
package_name="AnastacioEngine-${version}-linux-x86_64"
staging_dir="$dist_dir/$package_name"
archive="$dist_dir/$package_name.tar.xz"

if [ ! -x "$runtime_dir/RangeRuntime" ] && [ ! -x "$runtime_dir/RangeEngine" ]; then
  printf 'RangeRuntime/RangeEngine nao encontrado em %s. Execute cmake --install primeiro.\n' "$runtime_dir" >&2
  exit 1
fi

if [ -n "$extra_dir" ] && [ ! -x "$extra_dir/RangeRuntime" ] && [ ! -x "$extra_dir/RangeEngine" ]; then
  printf 'EXTRA_BIN_DIR=%s nao tem RangeRuntime nem RangeEngine. Confira o cmake --install desse preset.\n' "$extra_dir" >&2
  exit 1
fi

if [ ! -f "$repo_root/source/COPYING" ]; then
  printf 'Arquivo de licenca ausente: %s\n' "$repo_root/source/COPYING" >&2
  exit 1
fi

rm -rf "$staging_dir"
mkdir -p "$staging_dir"
cp -a "$runtime_dir/." "$staging_dir/"
if [ -n "$extra_dir" ]; then
  # -n (no-clobber): so adiciona o que falta (o outro executavel e seus arquivos exclusivos),
  # sem sobrescrever nada que ja veio do runtime_dir principal.
  cp -an "$extra_dir/." "$staging_dir/"
fi
cp "$repo_root/source/COPYING" "$staging_dir/COPYING"
# Ferramentas de build (geradores de codigo) e estado local do ImGui nao vao para o usuario.
rm -f "$staging_dir/datatoc" "$staging_dir/datatoc_icon" "$staging_dir/makesdna" "$staging_dir/makesrna" \
  "$staging_dir/msgfmt" "$staging_dir/imgui.ini" "$staging_dir/\\imgui.ini"

missing=""
[ -x "$staging_dir/RangeRuntime" ] || missing="RangeRuntime"
[ -x "$staging_dir/RangeEngine" ] || missing="${missing:+$missing e }RangeEngine"
if [ -n "$missing" ]; then
  printf 'AVISO: pacote sem %s. Para publicar um release completo, compile os dois presets\n' "$missing" >&2
  printf '(linux-runtime e linux-editor) e passe BIN_DIR + EXTRA_BIN_DIR apontando pra cada bin/.\n' >&2
fi

# Torna o pacote portatil: embute o Python 3.11 isolado em <versao>/python e troca o RUNPATH absoluto
# (/opt/anastacio-python311/lib) por $ORIGIN/lib. Sem isso o binario so abre na maquina de build
# ("libpython3.11.so.1.0: cannot open shared object file").
python_root="${PYTHON_ROOT_DIR:-/opt/anastacio-python311}"
if [ ! -e "$python_root/lib/libpython3.11.so.1.0" ]; then
  printf 'Python isolado nao encontrado em %s (rode tools/linux/install-python311.sh).\n' "$python_root" >&2
  exit 1
fi
# O executavel procura a stdlib em <versao>/python (ex.: 2.79/python/lib/python3.11); fora dali o
# Python so acha "encodings" se /opt/anastacio-python311 existir, ou seja, so na maquina de build.
version_dir="$(find "$staging_dir" -mindepth 1 -maxdepth 1 -type d -name '[0-9].[0-9]*' | head -n1)"
if [ -z "$version_dir" ]; then
  printf 'Pasta de versao (ex.: 2.79) ausente em %s.\n' "$staging_dir" >&2
  exit 1
fi
bundle_python="$version_dir/python"
rm -rf "$bundle_python"
mkdir -p "$bundle_python"
cp -a "$python_root/lib" "$bundle_python/lib"
find "$bundle_python" -type d \( -name test -o -name tests -o -name __pycache__ \) -prune -exec rm -rf {} +

# Patch direto na string do ELF (sem depender de patchelf/chrpath); a nova string e menor e o resto vira NUL.
python3 - "$staging_dir" "$python_root/lib" <<'PY'
import os, sys
root, old = sys.argv[1], sys.argv[2].encode()
new = b"$ORIGIN/lib"
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

# Confere que libpython (lib/, RUNPATH $ORIGIN/lib do CMake) e a stdlib vao juntos.
mkdir -p "$staging_dir/lib"
[ -e "$staging_dir/lib/libpython3.11.so.1.0" ] || cp -L "$python_root/lib/libpython3.11.so.1.0" "$staging_dir/lib/"
if [ ! -e "$bundle_python/lib/python3.11/encodings/__init__.py" ]; then
  printf 'stdlib do Python ausente em %s.\n' "$bundle_python" >&2
  exit 1
fi
if [ ! -e "$staging_dir/lib/libpython3.11.so.1.0" ]; then
  printf 'libpython3.11.so.1.0 ausente do pacote.
' >&2
  exit 1
fi

# Empacota em lib/ as .so da distro (diretas e indiretas) de que os executaveis e os modulos do Python
# dependem; sem isso o pacote so abre com os mesmos nomes de pacote do Ubuntu 24.04 (Fumangy, 2026-09-29).
# Ficam no sistema: glibc, libstdc++/libgcc_s, GL/driver, X11/xcb/Wayland, audio e servicos do desktop.
# A glibc nao pode ir junto: o pacote continua exigindo a glibc da maquina de build (ver docs/linux-build.md).
system_libs='^(ld-linux.*|lib(c|m|dl|pthread|rt|resolv|util|anl|nsl|mvec)|libstdc\+\+|libgcc_s|libGL|libGLX.*|libGLdispatch|libEGL|libOpenGL|libglapi|libgbm|libdrm.*|libX11|libX11-xcb|libxcb.*|libxshmfence|libwayland-.*|libxkbcommon.*|libvdpau|libva.*|libOpenCL|libcuda|libnvidia.*|libasound|libjack|libpulse.*|libfontconfig|libexpat|libdbus-1|libsystemd|libudev|libcom_err|libgpg-error)\.so'
ldd_targets=()
while IFS= read -r -d '' f; do
  head -c4 "$f" | grep -q 'ELF' && ldd_targets+=("$f")
done < <(find "$staging_dir" -type f \( -name 'Range*' -o -name '*.so' -o -name '*.so.*' \) -print0)
bundled=0
while read -r soname path; do
  printf '%s\n' "$soname" | grep -Eq "$system_libs" && continue
  case "$path" in "$staging_dir"/*) continue ;; esac
  [ -e "$staging_dir/lib/$soname" ] && continue
  cp -L "$path" "$staging_dir/lib/$soname"
  bundled=$((bundled + 1))
done < <(ldd "${ldd_targets[@]}" 2>/dev/null | awk '$2 == "=>" && $3 ~ /^\// {print $1, $3}' | sort -u -k1,1)
printf 'Bibliotecas da distro empacotadas em lib/: %s\n' "$bundled"
if ldd "${ldd_targets[@]}" 2>/dev/null | grep -q 'not found'; then
  printf 'Dependencia nao encontrada na maquina de build:\n' >&2
  ldd "${ldd_targets[@]}" 2>/dev/null | grep 'not found' | sort -u >&2
  exit 1
fi

# DT_RUNPATH so vale para as dependencias diretas; as .so empacotadas nao acham umas as outras em lib/.
# DT_RPATH do executavel vale para a arvore toda, entao troca a tag (0x1d -> 0x0f) nos dois executaveis.
python3 - "$staging_dir" <<'PY'
import os, struct, sys
root = sys.argv[1]
for name in ("RangeEngine", "RangeRuntime"):
    path = os.path.join(root, name)
    if not os.path.isfile(path):
        continue
    with open(path, "r+b") as f:
        data = bytearray(f.read())
        assert data[:4] == b"\x7fELF" and data[4] == 2, name + ": esperado ELF 64 bits"
        phoff, = struct.unpack_from("<Q", data, 0x20)
        phentsize, phnum = struct.unpack_from("<HH", data, 0x36)
        changed = False
        for i in range(phnum):
            p = phoff + i * phentsize
            p_type, = struct.unpack_from("<I", data, p)
            if p_type != 2:  # PT_DYNAMIC
                continue
            off, = struct.unpack_from("<Q", data, p + 8)
            size, = struct.unpack_from("<Q", data, p + 32)
            for e in range(off, off + size, 16):
                tag, = struct.unpack_from("<q", data, e)
                if tag == 0:
                    break
                if tag == 0x1d:
                    struct.pack_into("<q", data, e, 0x0f)
                    changed = True
        if changed:
            f.seek(0)
            f.write(data)
            print("RUNPATH -> RPATH:", name)
PY

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
