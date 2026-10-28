#!/bin/bash
# Runs the whole frame pacing drive test on a native Linux machine and saves a report.
# Usage, from the repo root:
#   bash tools/timing_linux.sh <windows build/bin> [linux bin]
# <windows build/bin>: folder with AnastacioRuntime.exe/AnastacioEngine.exe (e.g. the D: drive mounted
#   under /media). Runs through Wine, like Kitsuy. [linux bin]: optional native Linux build for reference.
# Report: timing_linux_result.txt in the repo root.
set -u
WIN_BIN=${1:?usage: tools/timing_linux.sh <windows build/bin> [linux bin]}
LIN_BIN=${2:-}
cd "$(dirname "$0")/.."
OUT=$PWD/timing_linux_result.txt
SCENE=$(mktemp -d)/drive.range
export FT_SECONDS=${FT_SECONDS:-10}

{
echo "== $(date) | $(uname -sr)"
echo "== GPU: $(glxinfo -B 2>/dev/null | grep -i 'renderer string' || echo 'glxinfo missing (sudo apt install mesa-utils)')"
echo "== wine: $(wine --version 2>/dev/null || echo 'missing (sudo apt install wine)')"
} | tee "$OUT"
if glxinfo -B 2>/dev/null | grep -qi llvmpipe; then
  echo "WARNING: llvmpipe = no GPU in use, results will be slow-motion like WSL" | tee -a "$OUT"
fi

for fps in 60 120; do
  export FT_FPS=$fps
  if [ -n "$LIN_BIN" ]; then
    "$LIN_BIN/AnastacioEngine" -b --python tools/create_pacing_drive_test.py -- "$SCENE" >/dev/null 2>&1
  else
    WINEDEBUG=-all wine "$WIN_BIN/AnastacioEngine.exe" -b --python tools/create_pacing_drive_test.py -- \
      "$(winepath -w "$SCENE")" >/dev/null 2>&1
  fi
  [ -f "$SCENE" ] || { echo "could not create the test scene" | tee -a "$OUT"; exit 1; }
  echo "== Wine, $fps fps" | tee -a "$OUT"
  bash tools/timing_drive_wine.sh "$WIN_BIN" "$SCENE" 2>&1 | tee -a "$OUT"
  if [ -n "$LIN_BIN" ]; then
    echo "== Linux native, $fps fps" | tee -a "$OUT"
    python3 tools/timing_drive_ab.py "$LIN_BIN" 2>&1 | tee -a "$OUT"
  fi
done
echo "== done: $OUT"
