#!/usr/bin/env bash
# Windows (Git Bash) version of run_net_test.sh: server and client RangeRuntime in small windows.
# Usage: tools/net_engine_test/run_net_test_win.sh [spawner|car] [net-sim "lat,jit,loss"]
# Each process gets its own TEMP: the player writes %TEMP%\range_runtime.log.txt, where the NETTEST lines go.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
SC="${1:-spawner}"
OUT="${TEMP:-/tmp}/net_engine_test_$SC.$$"
mkdir -p "$OUT/ts" "$OUT/tc"
case "$SC" in
  spawner) SRC="$ROOT/projects-teste/halfanim_crash/halfanim_crash.range" ;;
  car) SRC="$ROOT/projects-teste/car_framerate/car_com_fr0.range" ;;
  *) echo "scenario?" >&2; exit 2 ;;
esac
# The player writes its log next to the .range: work on a copy, never dirty projects-teste/.
cp "$SRC" "$OUT/scene.range"
export NET_PORT="${NET_PORT:-$((20000 + RANDOM % 20000))}" NET_SECONDS="${NET_SECONDS:-10}" NET_SIM="${2:-}" NET_SCENARIO="$SC"
cd "$ROOT/build/bin" || exit 1
TEMP="$(cygpath -w "$OUT/ts")" TMP="$(cygpath -w "$OUT/ts")" NET_ROLE=server timeout 120 ./RangeRuntime.exe -w 320 240 \
  -p "$HERE/net_engine_test.py" "$OUT/scene.range" > /dev/null 2>&1 &
sleep 1
TEMP="$(cygpath -w "$OUT/tc")" TMP="$(cygpath -w "$OUT/tc")" NET_ROLE=client timeout 120 ./RangeRuntime.exe -w 320 240 \
  -p "$HERE/net_engine_test.py" "$OUT/scene.range" > /dev/null 2>&1 &
wait
LOGS="$OUT/ts/range_runtime.log.txt $OUT/tc/range_runtime.log.txt"
grep -ah "NETTEST" $LOGS | grep -v "t=.*tick="
if grep -aq "NETTEST server PASS" "$OUT/ts/range_runtime.log.txt" && grep -aq "NETTEST client PASS" "$OUT/tc/range_runtime.log.txt"; then
  echo "NET ENGINE TEST ($SC): PASS"; exit 0
fi
echo "NET ENGINE TEST ($SC): FAIL (logs in $OUT)"; exit 1
