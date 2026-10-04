#!/usr/bin/env bash
# Starts a server and a client RangeRuntime (headless, xvfb) and checks that a replicated object moves
# on the client. Usage: tools/net_engine_test/run_net_test.sh [spawner|car] [build dir] [net-sim "lat,jit,loss"]
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
SCENARIO="${1:-spawner}"
BUILD="${2:-$ROOT/build-linux}"
SIM="${3:-}"
PORT="${NET_PORT:-$((20000 + RANDOM % 20000))}"
SECONDS_RUN="${NET_SECONDS:-10}"
case "$SCENARIO" in
  spawner) SCENE="$ROOT/projects-teste/halfanim_crash/halfanim_crash.range" ;;
  car) SCENE="$ROOT/projects-teste/car_framerate/car_com_fr0.range" ;;
  *) echo "scenario?" >&2; exit 2 ;;
esac
OUT="${TMPDIR:-/tmp}/net_engine_test.$$"
mkdir -p "$OUT"
export NET_PORT="$PORT" NET_SCENARIO="$SCENARIO" NET_SECONDS="$SECONDS_RUN" NET_SIM="$SIM"
export PYTHONPATH="${PYTHONPATH:-}"

run() { # role
  ( cd "$BUILD/bin" && NET_ROLE="$1" timeout 120 xvfb-run -a ./RangeRuntime -w 160 120 \
      -p "$HERE/net_engine_test.py" "$SCENE" > "$OUT/$1.log" 2>&1 ) &
}
run server
sleep 1
run client
wait
grep -h "NETTEST" "$OUT/server.log" "$OUT/client.log"
if grep -q "NETTEST server PASS" "$OUT/server.log" && grep -q "NETTEST client PASS" "$OUT/client.log"; then
  echo "NET ENGINE TEST ($SCENARIO): PASS"
  exit 0
fi
echo "NET ENGINE TEST ($SCENARIO): FAIL (logs in $OUT)"
exit 1
