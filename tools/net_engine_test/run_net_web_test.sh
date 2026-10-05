#!/usr/bin/env bash
# Browser client test: RangeRuntime --server hosts halfanim_crash.range with a WebSocket port and the wasm client
# net_web_watch (Network/tools/net_web_watch.cpp) joins it from headless Chromium, through the page served by HTTP.
#   tools/net_engine_test/run_net_web_test.sh <dir with net_web_watch.html/.js/.wasm> [build dir]
# Build the client with Emscripten: emcmake cmake -S source/source/gameengine/Network -B <dir> -DNET_STANDALONE=ON
#   && cmake --build <dir> --target net_web_watch. Needs node with playwright (NODE_PATH) and Chromium.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
WEB="$(cd "$1" && pwd)"
BUILD="${2:-$ROOT/build-linux}"
PORT="${NET_PORT:-$((20000 + RANDOM % 20000))}"
WS_PORT=$((PORT + 1)); HTTP_PORT=$((PORT + 2))
OUT="${TMPDIR:-/tmp}/net_web_test.$$"
mkdir -p "$OUT"
cp "$ROOT/projects-teste/halfanim_crash/halfanim_crash.range" "$OUT/scene.range"
( cd "$BUILD/bin" && NET_PORT=$PORT NET_WS_PORT=$WS_PORT NET_SECONDS=25 timeout 60 env -u DISPLAY -u WAYLAND_DISPLAY \
    ./RangeRuntime --server -p "$HERE/net_web_server.py" "$OUT/scene.range" > "$OUT/server.log" 2>&1 ) &
SERVER=$!
python3 -m http.server "$HTTP_PORT" --bind 127.0.0.1 --directory "$WEB" > "$OUT/http.log" 2>&1 &
HTTP=$!
trap 'kill $HTTP 2>/dev/null' EXIT
HASH=""
for _ in $(seq 100); do
  HASH="$(sed -n 's/.*network: hosting .*scene hash \([0-9a-f]*\).*/\1/p' "$OUT/server.log" | head -1)"
  [ -n "$HASH" ] && grep -q "NETTEST server READY" "$OUT/server.log" && break
  sleep 0.1
done
[ -n "$HASH" ] || { echo "NET WEB TEST: FAIL (server did not host, logs in $OUT)"; exit 1; }
node "$HERE/net_web_browser.js" "http://127.0.0.1:$HTTP_PORT/net_web_watch.html?host=127.0.0.1&port=$WS_PORT&hash=$HASH" \
  > "$OUT/browser.log" 2>&1
wait $SERVER
grep -h "NETTEST\|NETWEB\|network:" "$OUT/server.log" "$OUT/browser.log"
if grep -q "NETTEST server PASS" "$OUT/server.log" && grep -q "^NETWEB PASS" "$OUT/browser.log"; then
  echo "NET WEB TEST: PASS"; exit 0
fi
echo "NET WEB TEST: FAIL (logs in $OUT)"; exit 1
