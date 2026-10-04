#!/usr/bin/env bash
# Starts a server and a client RangeRuntime (xvfb; a --server one without any display) and checks that a replicated object moves
# on the client. Usage: tools/net_engine_test/run_net_test.sh [spawner|car|scene|server|scene-server|predict|predict-cube|rpc|relevance] [build dir] [net-sim "lat,jit,loss"]
#   spawner, car  the script registers the objects (net.replicate) and calls host()/join()
#   server        spawner with the server started as a headless server (RangeRuntime --server): no render, no
#                 audio, dedicated (no host player); also prints the CPU time of both processes
#   scene         the .range files are authored by the editor (make_net_scenes.py, needs build-linux-editor):
#                 Replicate checkbox, Rep property and the scene mode (Host/Client) open the session
#   scene-server  scene with the server started as --server: the Host scene must run as Dedicated
#   predict-cube  dynamic box (make_dyn_scene.py): the server gives the Car body to the client, both predict it
#                 (Bullet runs on the client too; the replay integrates the velocity); same simulator default as predict
#   relevance     spawner; after 5 s the server narrows the client's view (net.set_client_view): the Spawner
#                 leaves it and freezes on the client, the spawned Rig stays inside and keeps moving
#   rpc           spawner plus game RPCs (@net.rpc, net.call, obj.net): every target and argument type, refusals
#   predict       spawner plus a rig owned by the client, moved by net.predict() with the client's input
#                 (prediction, reconciliation) and shots at the Spawner through the input (lag compensation);
#                 runs through the network simulator, 40 ms / 5 ms / 1 % on each side unless a net-sim is given
#                 (the server rewinds at most 400 ms: a longer round trip plus the interpolation delay is clamped)
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
SCENARIO="${1:-spawner}"
LABEL="$SCENARIO"
BUILD="${2:-$ROOT/build-linux}"
SIM="${3:-}"
PORT="${NET_PORT:-$((20000 + RANDOM % 20000))}"
SECONDS_RUN="${NET_SECONDS:-10}"
OUT="${TMPDIR:-/tmp}/net_engine_test.$$"
mkdir -p "$OUT"
SCENE_SERVER=""; SCENE_CLIENT=""
SERVER_ARGS=""
case "$SCENARIO" in
  server) SERVER_ARGS="--server"; export NET_HEADLESS=1; SCENARIO=spawner
    SCENE_SERVER="$ROOT/projects-teste/halfanim_crash/halfanim_crash.range"; SCENE_CLIENT="$SCENE_SERVER" ;;
  relevance) export NET_RELEVANCE=1; SCENARIO=spawner; SECONDS_RUN="${NET_SECONDS:-11}"
    SCENE_SERVER="$ROOT/projects-teste/halfanim_crash/halfanim_crash.range"; SCENE_CLIENT="$SCENE_SERVER" ;;
  rpc) export NET_RPC=1; SCENARIO=spawner
    SCENE_SERVER="$ROOT/projects-teste/halfanim_crash/halfanim_crash.range"; SCENE_CLIENT="$SCENE_SERVER" ;;
  predict) export NET_PREDICT=1; SCENARIO=spawner; SIM="${SIM:-40,5,1}"; SECONDS_RUN="${NET_SECONDS:-12}"
    SCENE_SERVER="$ROOT/projects-teste/halfanim_crash/halfanim_crash.range"; SCENE_CLIENT="$SCENE_SERVER" ;;
  spawner) SCENE_SERVER="$ROOT/projects-teste/halfanim_crash/halfanim_crash.range"; SCENE_CLIENT="$SCENE_SERVER" ;;
  predict-cube) export NET_PREDICT_DYN=1; SCENARIO=car; SIM="${SIM:-40,5,1}"; SECONDS_RUN="${NET_SECONDS:-12}"
    EDITOR_BIN="${EDITOR_BIN:-$ROOT/build-linux-editor/bin/RangeEngine}"
    ( cd "$(dirname "$EDITOR_BIN")" && BLENDER_SYSTEM_SCRIPTS="$ROOT/source/release/scripts" BLENDER_SYSTEM_DATAFILES="$ROOT/source/release/datafiles" xvfb-run -a "$EDITOR_BIN" -b --python "$HERE/make_dyn_scene.py" -- "$OUT/cube.range" ) \
      > "$OUT/make.log" 2>&1
    grep -q "NETDYN SAVED" "$OUT/make.log" || { echo "NET ENGINE TEST (predict-cube): FAIL (editor step, logs in $OUT)"; exit 1; }
    SCENE_SERVER="$OUT/cube.range"; SCENE_CLIENT="$SCENE_SERVER" ;;
  car) SCENE_SERVER="$ROOT/projects-teste/car_framerate/car_com_fr0.range"; SCENE_CLIENT="$SCENE_SERVER" ;;
  scene|scene-server)
    if [ "$SCENARIO" = scene-server ]; then SERVER_ARGS="--server"; export NET_HEADLESS=1; fi
    EDITOR_BIN="${EDITOR_BIN:-$ROOT/build-linux-editor/bin/RangeEngine}"
    ( cd "$(dirname "$EDITOR_BIN")" && BLENDER_SYSTEM_SCRIPTS="$ROOT/source/release/scripts" BLENDER_SYSTEM_DATAFILES="$ROOT/source/release/datafiles" xvfb-run -a "$EDITOR_BIN" -b --python "$HERE/make_net_scenes.py" -- "$PORT" "$OUT" ) \
      > "$OUT/make.log" 2>&1
    grep -h "NETSCENE" "$OUT/make.log"
    grep -q "NETSCENE PASS" "$OUT/make.log" || { echo "NET ENGINE TEST (scene): FAIL (editor step, logs in $OUT)"; exit 1; }
    export NET_EXPECT_ID="$(sed -n 's/^NETSCENE id=//p' "$OUT/make.log")" NET_FROM_SCENE=1
    SCENE_SERVER="$OUT/net_host.range"; SCENE_CLIENT="$OUT/net_client.range"
    SCENARIO=spawner ;;
  *) echo "scenario?" >&2; exit 2 ;;
esac
# The player writes its log next to the .range: work on copies, never dirty projects-teste/.
if [ "$SCENE_SERVER" = "$SCENE_CLIENT" ]; then
  cp "$SCENE_SERVER" "$OUT/scene.range"; SCENE_SERVER="$OUT/scene.range"; SCENE_CLIENT="$OUT/scene.range"
fi
export NET_PORT="$PORT" NET_SECONDS="$SECONDS_RUN" NET_SIM="$SIM" NET_SCENARIO="$SCENARIO"
export PYTHONPATH="${PYTHONPATH:-}"

run() { # role scene [extra player args: the server's go first, -w after them would override --server's window]
  local role="$1" scene="$2"; shift 2
  local window="-w 160 120"
  [ $# -gt 0 ] && window=""
  # --server opens no window: it runs without xvfb and with DISPLAY unset, which proves it needs no display.
  local xvfb="xvfb-run -a"
  case " $* " in *" --server "*) xvfb="env -u DISPLAY -u WAYLAND_DISPLAY" ;; esac
  # /usr/bin/time -f: user+system CPU seconds of the player (xvfb-run is outside the measured command).
  ( cd "$BUILD/bin" && NET_ROLE="$role" timeout 120 $xvfb /usr/bin/time -f "NETCPU $role %U %S" \
      ./RangeRuntime "$@" $window -p "$HERE/net_engine_test.py" "$scene" > "$OUT/$role.log" 2>&1 ) &
}
run server "$SCENE_SERVER" $SERVER_ARGS
sleep 1
run client "$SCENE_CLIENT"
wait
grep -h "NETTEST\|NETCPU" "$OUT/server.log" "$OUT/client.log"
if grep -q "NETTEST server PASS" "$OUT/server.log" && grep -q "NETTEST client PASS" "$OUT/client.log"; then
  echo "NET ENGINE TEST ($LABEL): PASS"
  exit 0
fi
echo "NET ENGINE TEST ($LABEL): FAIL (logs in $OUT)"
exit 1
