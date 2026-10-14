#!/usr/bin/env bash
# Registra a Anastacio Engine no menu/dock do usuario (icone e atalho), apontando para esta pasta.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
apps="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
icons="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/256x256/apps"
mkdir -p "$apps" "$icons"
# No pacote portatil o PNG vem ao lado deste script. Ao executar diretamente
# da arvore fonte, use o mesmo asset que gera o icone do executavel Windows.
icon_source="$here/anastacio-engine-cube-splash-v2.png"
if [ ! -f "$icon_source" ]; then
  icon_source="$here/../windows/icons/anastacio-engine-cube-splash-v2.png"
fi
if [ ! -f "$icon_source" ]; then
  printf 'Icone Anastacio Engine ausente.\n' >&2
  exit 1
fi
cp "$icon_source" "$icons/AnastacioEngine.png"
desktop_source="$here/AnastacioEngine.desktop"
if [ ! -f "$desktop_source" ]; then
  desktop_source="$here/RangeEngine.desktop"
fi
if [ ! -f "$desktop_source" ]; then
  printf 'Atalho Anastacio Engine ausente.\n' >&2
  exit 1
fi
sed "s|^Exec=AnastacioEngine|Exec=\"$here/AnastacioEngine\"|" "$desktop_source" > "$apps/AnastacioEngine.desktop"
update-desktop-database "$apps" 2>/dev/null || true
gtk-update-icon-cache -q "${icons%/256x256/apps}" 2>/dev/null || true
printf 'Anastacio Engine registrada em %s\n' "$apps/AnastacioEngine.desktop"
