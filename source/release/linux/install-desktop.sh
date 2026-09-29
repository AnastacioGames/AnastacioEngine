#!/usr/bin/env bash
# Registra o Range Engine no menu/dock do usuario (icone e atalho), apontando para esta pasta.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
apps="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
icons="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/256x256/apps"
mkdir -p "$apps" "$icons"
cp "$here/range-engine.png" "$icons/range-engine.png"
sed "s|^Exec=RangeEngine|Exec=\"$here/RangeEngine\"|" "$here/RangeEngine.desktop" > "$apps/RangeEngine.desktop"
update-desktop-database "$apps" 2>/dev/null || true
gtk-update-icon-cache -q "${icons%/256x256/apps}" 2>/dev/null || true
printf 'Range Engine registrado em %s\n' "$apps/RangeEngine.desktop"
