#!/usr/bin/env bash
# Web client test: starts net_echo (ENet + WebSocket) and runs the wasm client against it in node.
#   tools/web_echo_test.sh <net_echo> <net_web_echo.js> [wsPort=17778]
# Exits with the client's code (0 = Hello and 3 Chat echoed).
set -u
ECHO_BIN=$1
CLIENT_JS=$2
PORT=${3:-17778}
NODE=${EMSDK_NODE:-node}

"$ECHO_BIN" server $((PORT - 1)) "$PORT" &
SERVER=$!
trap 'kill $SERVER 2>/dev/null' EXIT
# Wait for the WebSocket port (up to 5 s).
i=0
while [ $i -lt 50 ]; do
	if (exec 3<>"/dev/tcp/127.0.0.1/$PORT") 2>/dev/null; then
		break
	fi
	sleep 0.1
	i=$((i + 1))
done
"$NODE" "$CLIENT_JS" 127.0.0.1 "$PORT"
