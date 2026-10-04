#!/usr/bin/env bash
# Windows (Git Bash) version of run_net_test.sh: server and client RangeRuntime in small windows.
# Usage: tools/net_engine_test/run_net_test_win.sh [spawner|car|predict|server] [net-sim "lat,jit,loss"]
#   spawner, car  the script registers the objects (net.replicate) and calls host()/join()
#   predict       spawner plus a rig owned by the client, moved by net.predict() with the client's input
#                 (prediction, reconciliation) and shots at the Spawner through the input (lag compensation);
#                 runs through the network simulator, 40 ms / 5 ms / 1 % on each side unless a net-sim is given
#   server        spawner with the server started as a headless server (RangeRuntime --server): no render,
#                 no audio, dedicated. The server window is still a small GL window (no offscreen context
#                 in this GHOST): if it fails to open, that is the known pending issue, not a test bug.
# Each process gets its own TEMP: the player writes %TEMP%\range_runtime.log.txt, where the NETTEST lines go.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
SC="${1:-spawner}"
LABEL="$SC"
SIM="${2:-}"
SECONDS_RUN="${NET_SECONDS:-10}"
OUT="${TEMP:-/tmp}/net_engine_test_$SC.$$"
mkdir -p "$OUT/ts" "$OUT/tc"
SERVER_ARGS=()
case "$SC" in
  spawner) SRC="$ROOT/projects-teste/halfanim_crash/halfanim_crash.range" ;;
  car) SRC="$ROOT/projects-teste/car_framerate/car_com_fr0.range" ;;
  predict) export NET_PREDICT=1; SIM="${SIM:-40,5,1}"; SECONDS_RUN="${NET_SECONDS:-12}"
    SRC="$ROOT/projects-teste/halfanim_crash/halfanim_crash.range" ;;
  server) SERVER_ARGS=(--server); export NET_HEADLESS=1
    SRC="$ROOT/projects-teste/halfanim_crash/halfanim_crash.range" ;;
  *) echo "scenario?" >&2; exit 2 ;;
esac
# The player writes its log next to the .range: work on a copy, never dirty projects-teste/.
cp "$SRC" "$OUT/scene.range"
export NET_PORT="${NET_PORT:-$((20000 + RANDOM % 20000))}" NET_SECONDS="$SECONDS_RUN" NET_SIM="$SIM" NET_SCENARIO="spawner"
cd "$ROOT/build/bin" || exit 1
TEMP="$(cygpath -w "$OUT/ts")" TMP="$(cygpath -w "$OUT/ts")" NET_ROLE=server timeout 120 ./RangeRuntime.exe "${SERVER_ARGS[@]}" -w 320 240 \
  -p "$HERE/net_engine_test.py" "$OUT/scene.range" > "$OUT/ts/stdout.txt" 2>&1 &
sleep 1
TEMP="$(cygpath -w "$OUT/tc")" TMP="$(cygpath -w "$OUT/tc")" NET_ROLE=client timeout 120 ./RangeRuntime.exe -w 320 240 \
  -p "$HERE/net_engine_test.py" "$OUT/scene.range" > "$OUT/tc/stdout.txt" 2>&1 &
wait
LOGS="$OUT/ts/range_runtime.log.txt $OUT/tc/range_runtime.log.txt"
grep -ah "NETTEST" $LOGS | grep -v "t=.*tick="
if grep -aq "NETTEST server PASS" "$OUT/ts/range_runtime.log.txt" && grep -aq "NETTEST client PASS" "$OUT/tc/range_runtime.log.txt"; then
  echo "NET ENGINE TEST ($LABEL): PASS"; exit 0
fi
echo "NET ENGINE TEST ($LABEL): FAIL (logs in $OUT)"; exit 1
