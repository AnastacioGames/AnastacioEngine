"""Server side of the browser client test (see run_net_web_test.sh).

  NET_PORT=7777 NET_WS_PORT=7778 NET_SECONDS=20 RangeRuntime --server -p net_web_server.py halfanim_crash.range

Hosts with a WebSocket port, replicates the Spawner (moving on a circle, 'hp' counting up) and spawns the 'Rig'
prototype once a client joins. Passes when a client named "browser" joined (the wasm net_web_watch running in
Chromium) and was still connected after receiving the replication for a while.
"""

import math
import os
import time
import traceback

from Range import logic
import Range.network as net

PORT = int(os.environ.get("NET_PORT", "7777"))
WS_PORT = int(os.environ.get("NET_WS_PORT", "7778"))
SECONDS = float(os.environ.get("NET_SECONDS", "20"))
failures = []


def log(msg):
    print("NETTEST server %s" % msg, flush=True)


def check(name, ok, detail=""):
    log("%s %s %s" % ("ok  " if ok else "FAIL", name, detail))
    if not ok:
        failures.append(name)


def run():
    scene = logic.getCurrentScene()
    joins = []
    leaves = []
    net.on_player_join(lambda cid, name: joins.append((cid, name, time.time())))
    net.on_player_leave(lambda cid: leaves.append((cid, time.time())))
    spawner = [o for o in scene.objects if o.name == "Spawner"][0]
    spawner["hp"] = 0
    net.replicate(spawner, props=["hp"], velocity=False)
    check("host() with a WebSocket port", net.host(PORT, max_players=4, room_name="web-test", websocket_port=WS_PORT))
    log("READY")
    rig = None
    start = time.time()
    while time.time() - start < SECONDS:
        t = time.time() - start
        spawner.worldPosition = [math.cos(t) * 4.0, math.sin(t) * 4.0, 1.0]
        spawner["hp"] = int(t * 2)
        if joins and rig is None:
            rig = net.spawn("Rig", owner=0, position=[1.0, 2.0, 3.0])
            log("browser client %d (%s) joined, spawned the Rig" % (joins[0][0], joins[0][1]))
        if rig is not None:
            rig.worldPosition = [-math.cos(t) * 2.0, -math.sin(t) * 2.0, 3.0]
        if joins and leaves:
            break
        logic.NextFrame()
    check("the browser client joined", any(name == "browser" for _, name, _ in joins), repr(joins))
    stayed = leaves[0][1] - joins[0][2] if joins and leaves else (time.time() - joins[0][2] if joins else 0.0)
    check("it stayed while it watched the replication", stayed > 0.5, "%.2f s" % stayed)
    net.disconnect()
    log("PASS" if not failures else "FAIL " + ",".join(failures))
    logic.endGame()
    logic.NextFrame()


try:
    run()
except Exception:
    traceback.print_exc()
    log("FAIL exception")
    logic.endGame()
    logic.NextFrame()
