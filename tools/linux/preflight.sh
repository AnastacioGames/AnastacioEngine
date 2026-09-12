#!/usr/bin/env bash
# Verifica o ambiente minimo do preset linux-runtime sem alterar o sistema.

set -u

failed=0
python_version="${PYTHON_VERSION:-3.11}"
python_executable="${PYTHON_EXECUTABLE:-python${python_version}}"

ok() {
  printf 'OK   %s\n' "$1"
}

missing() {
  printf 'FALTA %s\n' "$1"
  failed=1
}

require_command() {
  if command -v "$1" >/dev/null 2>&1; then
    ok "comando $1"
  else
    missing "comando $1"
  fi
}

require_pkg_config() {
  if pkg-config --exists "$1"; then
    ok "biblioteca $1 ($(pkg-config --modversion "$1"))"
  else
    missing "biblioteca pkg-config $1"
  fi
}

require_python_module() {
  if "$python_executable" -c "import $1" >/dev/null 2>&1; then
    ok "modulo Python $1"
  else
    missing "modulo Python $1"
  fi
}

if [ "$(uname -s)" != "Linux" ]; then
  printf 'Este script deve ser executado em Linux.\n' >&2
  exit 2
fi

if [ "$(uname -m)" = "x86_64" ]; then
  ok "arquitetura x86_64"
else
  missing "arquitetura x86_64 (encontrada: $(uname -m))"
fi

require_command cmake
require_command ninja
require_command pkg-config
require_command gcc
require_command g++
require_command "$python_executable"

python_include="$("$python_executable" -c 'import sysconfig; print(sysconfig.get_path("include"))' 2>/dev/null || true)"
if [ -n "$python_include" ] && [ -f "$python_include/Python.h" ]; then
  ok "header Python ${python_version}"
else
  missing "header Python ${python_version} (Python.h)"
fi

if command -v "$python_executable" >/dev/null 2>&1; then
  require_python_module numpy
fi

if command -v pkg-config >/dev/null 2>&1; then
  require_pkg_config x11
  require_pkg_config xi
  require_pkg_config xinerama
  require_pkg_config xxf86vm
  require_pkg_config gl
  require_pkg_config glew
  require_pkg_config sdl2
  require_pkg_config openal
  require_pkg_config sndfile
  require_pkg_config freetype2
  require_pkg_config libpng
fi

if [ "$failed" -ne 0 ]; then
  printf '\nAmbiente incompleto. Instale os pacotes indicados em docs/linux-build.md.\n' >&2
  exit 1
fi

printf '\nAmbiente pronto para: cmake --preset linux-runtime -S source\n'
