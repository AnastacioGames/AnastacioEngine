#!/bin/bash
# Wine A/B of tools/create_pacing_drive_test.py. Wine fails to map PE files from /mnt/<drive> under WSL
# (entry point reads as zeros), so the runtime is copied into the Linux filesystem first.
# Usage (WSL or Linux with wine): tools/timing_drive_wine.sh <bin dir> <drive.range>
set -e
BIN=${1:-/mnt/d/AnastacioEngine/build/bin}
SCENE=${2:-/mnt/d/AnastacioEngine/build/_wine_drive.range}
RT=~/range_wine_rt
rm -rf "$RT"; mkdir -p "$RT"
cp -r "$BIN"/AnastacioRuntime.exe "$BIN"/*.dll "$BIN"/blender.crt "$BIN"/2.79 "$RT"/
cp "$SCENE" "$RT/drive.range"
cd "$RT"
export WINEDEBUG=-all FT_SECONDS=${FT_SECONDS:-10}
for fx in 1 0; do
  for tr in 1 0; do
    for p in sleep mix; do
      if [ "$tr" = 0 ]; then export RANGE_NO_TIMER_RES=1; else unset RANGE_NO_TIMER_RES; fi
      RANGE_PACING=$p timeout 120 wine AnastacioRuntime.exe -g fixed_timestep = $fx drive.range >/dev/null 2>&1 || true
      loop=fixed; [ "$fx" = 0 ] && loop=legacy
      timer=1ms; [ "$tr" = 0 ] && timer=15ms
      printf "%-6s %-5s %-4s | %s\n" $loop $p $timer "$(tail -1 drive_result.txt 2>/dev/null | cut -c12-)"
      rm -f drive_result.txt
    done
  done
done
