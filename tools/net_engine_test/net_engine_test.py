"""Two-process test of Range.network in the real engine (see run_net_test.sh).

Run through the player's Python main loop, once as server and once as client:
  NET_ROLE=server|client NET_PORT=7777 NET_SCENARIO=spawner|car NET_SECONDS=12 \
    RangeRuntime -p net_engine_test.py <scene>.range

Scenarios (existing scenes of projects-teste/, no editor needed):
  spawner  halfanim_crash.range: Spawner moves on a circle (kinematic), its game property 'hp' counts up,
           the inactive prototype 'Rig' is spawned by the server and moved too.
  car      car_framerate/car_com_fr0.range: the dynamic 'Car' drives on physics (server) and is followed on the
           client (dynamics suspended there).

Prints one "NETTEST <role> ..." line per check and "NETTEST <role> PASS|FAIL" at the end; the exit code is
not used (the player does not forward it), the runner greps the output.
"""

import math
import os
import sys
import time
import traceback

from Range import logic
import Range.network as net

ROLE = os.environ.get("NET_ROLE", "server")
PORT = int(os.environ.get("NET_PORT", "7777"))
SCENARIO = os.environ.get("NET_SCENARIO", "spawner")
SECONDS = float(os.environ.get("NET_SECONDS", "10"))
CAR_SPEED = 5.0
SIM = os.environ.get("NET_SIM", "")  # "latency,jitter,loss", for the network simulator

failures = []


def log(msg):
    print("NETTEST %s %s" % (ROLE, msg), flush=True)


def check(name, ok, detail=""):
    log("%s %s %s" % ("ok  " if ok else "FAIL", name, detail))
    if not ok:
        failures.append(name)


def find(scene, name):
    for obj in scene.objects:
        if obj.name == name:
            return obj
    return None


def run():
    scene = logic.getCurrentScene()
    events = []

    net.on_connect(lambda cid: events.append(("connect", cid)))
    net.on_disconnect(lambda reason, detail: events.append(("disconnect", reason)))
    net.on_reject(lambda reason, detail: events.append(("reject", reason, detail)))
    net.on_chat(lambda cid, text: events.append(("chat", cid, text)))
    net.on_start(lambda: events.append(("start",)))
    net.on_player_join(lambda cid, name: events.append(("join", cid, name)))
    net.on_player_leave(lambda cid: events.append(("leave", cid)))
    net.playerName = "Tester-" + ROLE

    if SIM:
        lat, jit, loss = [float(v) for v in SIM.split(",")]
        net.set_simulation(lat, jit, loss)

    if SCENARIO == "spawner":
        tracked = find(scene, "Spawner")
        tracked["hp"] = 0
        props = ["hp"]
        net.replicate(tracked, props=props, velocity=False)
        proto = "Rig"
    else:
        tracked = find(scene, "Car")
        props = []
        net.replicate(tracked, velocity=True)
        proto = None
    check("replicate gives an id", net.net_id(tracked) != 0, "id=%d" % net.net_id(tracked))
    initial = tuple(tracked.worldPosition)

    if ROLE == "server":
        ok = net.host(PORT, max_players=4, room_name="engine-test", websocket_port=0)
        check("host() opens the room", ok)
        check("isServer", net.isServer and net.isConnected)
        check("roomName/maxPlayers", net.roomName == "engine-test" and net.maxPlayers == 4,
              "%r %r" % (net.roomName, net.maxPlayers))
    else:
        time.sleep(float(os.environ.get("NET_CLIENT_DELAY", "1.5")))
        ok = net.join("127.0.0.1:%d" % PORT)
        check("join() starts", ok)

    start = time.time()
    spawned = None
    positions = []
    times = []
    hps = []
    spawn_seen = []
    clients_seen = 0
    lobby = {"chat_sent": False, "start": None, "ready_sent": False, "lan": None, "clients": []}
    t_connected = None
    last_log = 0.0

    while time.time() - start < SECONDS:
        t = time.time() - start
        if ROLE == "server":
            if SCENARIO == "spawner":
                tracked.worldPosition = [math.cos(t) * 4.0, math.sin(t) * 4.0, 1.0]
                tracked["hp"] = int(t * 2)
                if proto and spawned is None and any(e[0] == "join" for e in events):
                    spawned = net.spawn(proto, owner=0, position=[1.0, 2.0, 3.0])
                    check("spawn() returns the replica", spawned is not None and net.net_id(spawned) >= 0x80000000,
                          "id=%s" % (net.net_id(spawned) if spawned else None))
                if spawned is not None:
                    spawned.worldPosition = [-math.cos(t) * 2.0, -math.sin(t) * 2.0, 3.0]
            else:
                # constant speed along +y: the client must see a slope of CAR_SPEED m/s
                tracked.setLinearVelocity([0.0, CAR_SPEED, 0.0], False)
            clients_seen = max(clients_seen, len(net.clients))
            if not lobby["chat_sent"] and any(e[0] == "join" for e in events):
                lobby["chat_sent"] = net.send_chat("welcome")
            if lobby["start"] is None and any(c.ready and not c.isHost for c in net.clients):
                lobby["start"] = net.start_game()
                log("start_game() -> %s" % lobby["start"])
        else:
            if t_connected is None and net.isConnected:
                t_connected = t
                log("connected as client %d" % net.localId)
            if net.isConnected and t_connected is not None and t - t_connected > 0.5 and not lobby["ready_sent"]:
                lobby["ready_sent"] = True
                net.set_ready(True)
                net.send_chat("hello")
            if net.isConnected and net.clients:
                lobby["clients"] = [(c.id, c.name, c.isHost, c.ready) for c in net.clients]
            if net.isConnected and not lobby["lan"]:
                found = net.discover_lan()
                if any(entry["name"] == "engine-test" for entry in found):
                    lobby["lan"] = found
            if net.isConnected:
                p = tracked.worldPosition
                if (p.x, p.y, p.z) != initial or positions:  # nothing before the first snapshot
                    positions.append((p.x, p.y, p.z))
                    times.append(time.time())
                if props:
                    hps.append(tracked["hp"])
                if proto:
                    rig = [o for o in scene.objects if o.name == proto and net.net_id(o) != 0]
                    spawn_seen.append(len(rig))
            if any(e[0] == "reject" for e in events):
                break
        if t - last_log > 2.0:
            last_log = t
            log("t=%.1f tick=%d connected=%s pos=%s" % (
                t, net.tick, net.isConnected, tuple(round(v, 2) for v in tracked.worldPosition)))
        logic.NextFrame()

    if ROLE == "server":
        check("a client joined", any(e[0] == "join" for e in events), str(events))
        check("net.clients lists host + client", clients_seen >= 2, "max=%d" % clients_seen)
        names = [c.name for c in net.clients]
        check("client name arrived", any(n == "Tester-client" for n in names), str(names))
        check("lobby: client chat reached the server", ("chat", 1, "hello") in events, str(events))
        check("lobby: ready + start_game()", lobby["start"] is True, str(lobby["start"]))
    else:
        check("client connected", t_connected is not None, str(events))
        if positions:
            xs = [p[0] for p in positions]
            ys = [p[1] for p in positions]
            zs = [p[2] for p in positions]
            span = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
            check("replicated object moves on the client", span > 1.0, "span=%.2f over %d frames" % (span, len(positions)))
            if SCENARIO == "car" and len(positions) > 20:
                dt = times[-1] - times[0]
                slope = (positions[-1][1] - positions[0][1]) / dt if dt > 0 else 0.0
                check("client follows the dynamic car at the server's speed", abs(slope - CAR_SPEED) < 0.2 * CAR_SPEED,
                      "slope=%.2f m/s over %.1f s" % (slope, dt))
            if SCENARIO == "spawner":
                # The server moves it on a circle of radius 4 at z = 1: any wrong transform shows here.
                radii = [math.hypot(p[0], p[1]) for p in positions]
                # Interpolating across a stall of the server draws a chord (radius < 4), so a few samples may be
                # inside the circle on a loaded machine; the large majority must be on it.
                on_path = sum(1 for r in radii if 3.9 < r < 4.05)
                check("client positions stay on the server's path", on_path >= 0.8 * len(radii) and max(radii) < 4.05
                      and all(abs(p[2] - 1.0) < 0.05 for p in positions),
                      "%d/%d samples on the circle, radius %.2f..%.2f" % (on_path, len(radii), min(radii), max(radii)))
        else:
            check("replicated object moves on the client", False, "never connected")
        if props:
            check("replicated property changes", len(set(hps)) > 3, "hp values %s..%s" % (min(hps) if hps else None, max(hps) if hps else None))
        if proto:
            check("spawned object appears on the client", any(n >= 1 for n in spawn_seen), "max=%d" % max(spawn_seen or [0]))
        check("lobby: client list has the host and itself", (0, "Tester-server", True) in [c[:3] for c in lobby["clients"]]
              and any(c[0] == 1 and c[1] == "Tester-client" for c in lobby["clients"]), str(lobby["clients"]))
        check("lobby: server chat reached the client", ("chat", 0, "welcome") in events, str(events))
        check("lobby: on_start fired on the client", ("start",) in events, str(events))
        if lobby["lan"]:
            entry = [e for e in lobby["lan"] if e["name"] == "engine-test"][0]
            check("LAN discovery lists the room", entry["port"] == PORT and entry["max_players"] == 4, str(entry))
        else:
            log("skip LAN discovery (no answer on this network)")
        check("client has no reject", not any(e[0] == "reject" for e in events), str(events))

    net.disconnect()
    if ROLE == "server":
        # The registration of a scene object survives leaving and hosting again.
        check("disconnect() leaves the session", not net.isServer and not net.isConnected)
        first_id = net.net_id(tracked)
        again = net.host(PORT + 1, max_players=2, room_name="again", websocket_port=0)
        check("host() again after disconnect()", again and net.isServer and net.net_id(tracked) == first_id and first_id != 0,
              "id=%d" % net.net_id(tracked))
        for _ in range(30):
            logic.NextFrame()
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
