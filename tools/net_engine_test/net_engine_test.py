"""Two-process test of Range.network in the real engine (see run_net_test.sh).

Run through the player's Python main loop, once as server and once as client:
  NET_ROLE=server|client NET_PORT=7777 NET_SCENARIO=spawner|car NET_SECONDS=12 \
    RangeRuntime -p net_engine_test.py <scene>.range

Scenarios (existing scenes of projects-teste/, no editor needed):
  spawner  halfanim_crash.range: Spawner moves on a circle (kinematic), its game property 'hp' counts up,
           the inactive prototype 'Rig' is spawned by the server and moved too.
  car      car_framerate/car_com_fr0.range: the dynamic 'Car' drives on physics (server) and is followed on the
           client (dynamics suspended there).
With NET_PREDICT=1 (runner scenario "predict", spawner scene) the server also spawns a 'Rig' owned by the client,
moved by net.predict() with the client's input (client prediction + reconciliation), and gives the Spawner a hitbox
the client shoots at through the input (lag compensation, net.raycast_past()).
With NET_RPC=1 (scenario "rpc") the peers register game RPCs and check every target, argument type, obj.net and
the refusals.
NET_DEBUG=1 logs every shot, aim and prediction state.
With NET_HEADLESS=1 the server runs as RangeRuntime --server: it must report net.headless, draw nothing and host
as Dedicated (no host player in the lobby).

Prints one "NETTEST <role> ..." line per check and "NETTEST <role> PASS|FAIL" at the end; the exit code is
not used (the player does not forward it), the runner greps the output.
"""

import math
import os
import struct
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
# Scene mode: the .range files (make_net_scenes.py) carry the Network panel settings, so the session opens
# when the game starts and the script neither replicates nor hosts/joins.
FROM_SCENE = os.environ.get("NET_FROM_SCENE") == "1"
# The name goes in the Hello message, so a scene-mode client (connected before any script runs) is "Player".
CLIENT_NAME = "Player" if FROM_SCENE else "Tester-client"
HEADLESS = os.environ.get("NET_HEADLESS") == "1"
PREDICT = os.environ.get("NET_PREDICT") == "1"
RPC = os.environ.get("NET_RPC") == "1"

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


# Input of the predicted rig: x speed, shot sequence (0 = none), shot origin and direction.
INPUT = struct.Struct("<fB3f3f")
RIG_SPEED = 2.0
RIG_REPORT = {"x": None}  # last rig position the server sent (RPC rig_pos)
HITBOX_RADIUS = 0.35


class Predict:
    """net.predict() + net.raycast_past() check (NET_PREDICT=1)."""

    def __init__(self, scene, tracked):
        @net.rpc(target="others")
        def rig_pos(sender, x):
            RIG_REPORT["x"] = x

        self.scene = scene
        self.tracked = tracked
        self.rig = None
        self.t0 = None
        self.vx = 0.0
        self.seq = 0
        self.last_shot = 0.0
        self.shots = {}  # server: seq -> (hit in the past, hit now)
        self.flip = None  # client: (tick, x) when the input turned around
        self.response_ticks = None
        self.server_x = None
        self.server_xs = []
        self.inputs_seen = 0
        self.last_report = 0.0
        self.stats = None
        self.stopped_at = None
        self.last_x = None

    def step(self, obj, data):
        if len(data) != INPUT.size:
            return
        vals = INPUT.unpack(data)
        p = obj.worldPosition.copy()
        p.x += vals[0] / logic.getLogicTicRate()
        obj.worldPosition = p
        if net.isServer and vals[1] and vals[1] not in self.shots:
            origin, direction = vals[2:5], vals[5:8]
            owner = net.owner(obj)
            # The software-rendered test machine draws ~0.5 s in the past (slow frames make the snapshots arrive
            # in bursts and the interpolation delay grows), beyond the default 400 ms limit.
            past = net.raycast_past(origin, direction, 20.0, client=owner, ignore=obj, max_rewind_ms=1000)
            now = net.raycast_past(origin, direction, 20.0, ignore=obj)
            self.shots[vals[1]] = (past is not None and past[0] == self.tracked, now is not None and now[0] == self.tracked)
            if os.environ.get("NET_DEBUG") or len(self.shots) <= 3:
                log("shot %d tick=%d view=%s dir=%s past=%s now=%s spawner=%s" % (
                    vals[1], net.tick, net.view_time(owner), tuple(round(v, 2) for v in direction),
                    past and (past[0].name, tuple(round(v, 2) for v in past[1])), now and now[0].name,
                    tuple(round(v, 2) for v in self.tracked.worldPosition)))

    def spin(self, obj, data):
        # The host's object, moved every tick by the step function (host input): the hitbox history then
        # changes every tick like the snapshots. Moved once per frame it would jump in steps the client
        # interpolates differently when a snapshot is missing.
        self.angle += 1.0 / logic.getLogicTicRate()
        obj.worldPosition = [math.cos(self.angle) * 4.0, math.sin(self.angle) * 4.0, 1.0]

    def server_start(self):
        self.angle = 0.0
        check("set_hitbox() on a replicated object", net.set_hitbox(self.tracked, HITBOX_RADIUS))
        net.set_input(b"")
        check("predict() on a host object", net.predict(self.tracked, self.spin))

    def server_frame(self, t, joined):
        if self.rig is None and joined:
            self.rig = net.spawn("Rig", owner=joined, position=[0.0, -6.0, 3.0])
            check("predict() on the server", self.rig is not None and net.predict(self.rig, self.step))
        if self.rig is not None:
            if net.input(joined) is not None:
                self.inputs_seen += 1
            self.server_xs.append(self.rig.worldPosition.x)
            if t - self.last_report > 0.25:
                self.last_report = t
                net.call("rig_pos", self.rig.worldPosition.x)

    def client_frame(self, t, events):
        self.server_x = RIG_REPORT["x"]
        if self.rig is None:
            for o in self.scene.objects:
                if o.name == "Rig" and net.net_id(o) != 0 and net.is_owner(o):
                    self.rig = o
                    check("predict() on the owning client", net.predict(o, self.step))
                    self.t0 = t
            if self.rig is None:
                return
        if net.view_time() is None:
            return
        age = t - self.t0
        x = self.rig.worldPosition.x
        self.last_x = x
        if self.flip is not None and self.response_ticks is None and net.tick > self.flip[0]:
            # First look after the input turned around (a frame may hold several ticks): ticks elapsed minus the
            # ticks the rig has already moved back. Without prediction it keeps going forward for a round trip.
            moved = (self.flip[1] - x) * logic.getLogicTicRate() / RIG_SPEED
            self.response_ticks = (net.tick - self.flip[0]) - moved
        vx = RIG_SPEED if age < 2.5 else (-RIG_SPEED if age < 4.5 else 0.0)
        if vx < 0.0 and self.flip is None:
            self.flip = (net.tick, x)
        if vx == 0.0 and self.stopped_at is None:
            self.stopped_at = t
        shot = 0
        if age > 0.5 and t - self.last_shot > 0.4 and self.seq < 250:
            # Aim at the Spawner where this client draws it (in the past of the server).
            self.last_shot = t
            self.seq += 1
            shot = self.seq
        origin = (0.0, 0.0, 1.0)
        target = self.tracked.worldPosition
        direction = (target.x - origin[0], target.y - origin[1], target.z - origin[2])
        net.set_input(INPUT.pack(vx, shot, *origin, *direction))
        if shot and os.environ.get("NET_DEBUG"):
            log("aim %d view=%s target=%s" % (shot, net.view_time(), tuple(round(v, 2) for v in target)))
        self.stats = net.prediction_stats(self.rig)
        if os.environ.get("NET_DEBUG") and self.stats:
            log("pred tick=%d x=%.3f server=%s %s" % (net.tick, x, self.server_x, self.stats))

    def server_checks(self):
        check("server applied the client's input", self.inputs_seen > 30, "frames=%d" % self.inputs_seen)
        xs = self.server_xs
        check("rig moved by the input on the server", bool(xs) and max(xs) - min(xs) > 2.0,
              "x %.2f..%.2f" % (min(xs or [0]), max(xs or [0])))
        shots = len(self.shots)
        past = sum(1 for v in self.shots.values() if v[0])
        now = sum(1 for v in self.shots.values() if v[1])
        check("lag compensation: shots hit the Spawner where the client saw it", shots >= 5 and past >= 0.8 * shots,
              "%d/%d hit in the past, %d/%d now" % (past, shots, now, shots))
        check("lag compensation: the same shots mostly miss the present", now <= shots // 2,
              "%d/%d hit now" % (now, shots))

    def client_checks(self, t_end):
        check("client found its rig", self.rig is not None)
        if self.rig is None:
            return
        check("prediction: the rig answers the input within 2 ticks", self.response_ticks is not None and
              self.response_ticks <= 2.0, "delay=%s ticks" % (None if self.response_ticks is None else
                                                              round(self.response_ticks, 2)))
        st = self.stats or {}
        check("prediction: inputs recorded", st.get("inputs", 0) > 60, str(st))
        settled = self.stopped_at is not None and t_end - self.stopped_at > 1.5
        x = self.last_x  # the rig itself is gone once the server left
        check("prediction: rig ends where the server has it", settled and self.server_x is not None and
              x is not None and abs(x - self.server_x) < 0.05, "client %s server %s settled=%s" % (x, self.server_x, settled))
        check("prediction: corrections stay small", st.get("max_error", 99.0) < 0.5, str(st))


class Rpc:
    """@net.rpc, net.call() and obj.net (NET_RPC=1): every target, argument type, owner check and refusal."""

    def __init__(self, tracked):
        self.tracked = tracked
        self.got = {}  # name -> list of calls seen here
        self.rig = None
        self.sent = False
        self.unreliable = 0
        self.local = {}
        self.late = None

        def keep(name):
            def fn(*args):
                # Objects by name, vectors as tuples: the objects are freed before the checks run.
                norm = tuple(a.name if hasattr(a, "worldPosition") else
                             tuple(round(v, 4) for v in a) if hasattr(a, "__len__") and not isinstance(a, str) else a
                             for a in args)
                self.got.setdefault(name, []).append(norm)
            fn.__name__ = name
            return fn

        net.rpc(keep("hello"))  # bare form: target 'server'
        net.rpc(target="all")(keep("notice"))
        net.rpc(target="owner")(keep("poke"))
        net.rpc(target="server", owner_only=True)(keep("move_req"))
        net.rpc(target="others")(keep("shout"))
        net.rpc(target="server", reliable=False)(keep("tick_u"))
        net.rpc(name="renamed", target="all")(keep("renamed"))

    def server_frame(self, t, joined):
        if self.rig is None and joined:
            self.rig = net.spawn("Rig", owner=joined, position=[0.0, -6.0, 3.0])
            self.t_spawn = t
        if self.rig is not None and not self.sent and t - self.t_spawn > 2.0:
            self.sent = True
            self.local["notice"] = net.call("notice", 42)
            self.local["poke"] = self.rig.net.call("poke", 7)
            self.local["shout"] = net.call("shout", "from-server")
            self.local["renamed"] = net.call("renamed", -1)

    def client_frame(self, scene):
        if self.rig is None:
            for o in scene.objects:
                if o.name == "Rig" and o.net.replicated and o.net.isOwner:
                    self.rig = o
            return
        if not self.sent:
            self.sent = True
            q = [0.70710678, 0.0, 0.0, 0.70710678]  # w, x, y, z
            self.local["hello"] = net.call("hello", 3, 2.5, "olá", True, [1.0, 2.0, 3.0], q, self.tracked)
            self.local["move_req"] = self.rig.net.call("move_req", 0.5)
            self.local["move_not_owner"] = self.tracked.net.call("move_req", 0.5)
            self.local["poke_from_client"] = self.rig.net.call("poke", 1)
            self.local["shout"] = net.call("shout", "from-client")
            self.local["owner"] = (self.rig.net.owner == net.localId, self.rig.net.isOwner,
                                   self.tracked.net.id == net.net_id(self.tracked) != 0)
            try:
                net.rpc(lambda sender: None, name="too_late")
            except RuntimeError:
                self.late = "refused"
            try:
                net.call("nope")
            except KeyError:
                self.local["unknown"] = "KeyError"
        if self.unreliable < 30:
            self.unreliable += 1
            net.call("tick_u", self.unreliable)

    def server_checks(self):
        hello = self.got.get("hello", [])
        ok = bool(hello) and hello[0][0] == 1 and hello[0][1:5] == (3, 2.5, "olá", True) and \
            hello[0][5] == (1.0, 2.0, 3.0) and hello[0][6] == (0.7071, 0.0, 0.0, 0.7071) and hello[0][7] == "Spawner"
        check("rpc: client to server, every argument type and the sender", ok, str(hello))
        check("rpc: target 'all' runs on the server too", (0, 42) in self.got.get("notice", []), str(self.got.get("notice")))
        mv = self.got.get("move_req", [])
        check("rpc: object call with owner_only reaches the server once", len(mv) == 1 and mv[0][0] == "Rig" and
              mv[0][1:] == (1, 0.5), str(mv))
        check("rpc: target 'others' from the client reaches the server", (1, "from-client") in self.got.get("shout", []),
              str(self.got.get("shout")))
        check("rpc: 'others' from the server does not run here", (0, "from-server") not in self.got.get("shout", []))
        check("rpc: calls made here", all(self.local.get(k) for k in ("notice", "poke", "shout", "renamed")), str(self.local))
        n = len(self.got.get("tick_u", []))
        check("rpc: unreliable calls arrive", n >= 15, "%d/30" % n)

    def client_checks(self):
        check("rpc: client found its rig through obj.net", self.rig is not None)
        loc = self.local
        check("rpc: obj.net owner/isOwner/id", loc.get("owner") == (True, True, True), str(loc.get("owner")))
        check("rpc: calls accepted here", loc.get("hello") and loc.get("move_req") and loc.get("shout"), str(loc))
        check("rpc: owner_only on an object of someone else is refused here", loc.get("move_not_owner") is False)
        check("rpc: a client cannot call an 'owner' RPC", loc.get("poke_from_client") is False)
        check("rpc: unknown name raises KeyError", loc.get("unknown") == "KeyError")
        check("rpc: registering during a session raises", self.late == "refused")
        check("rpc: target 'all' from the server runs here", (0, 42) in self.got.get("notice", []), str(self.got.get("notice")))
        check("rpc: registered under another name", (0, -1) in self.got.get("renamed", []))
        poke = self.got.get("poke", [])
        check("rpc: target 'owner' reaches the owner with its object", len(poke) == 1 and poke[0][0] == "Rig" and
              poke[0][1:] == (0, 7), str(poke))
        shout = self.got.get("shout", [])
        check("rpc: 'others' reaches the client, not the caller", (0, "from-server") in shout and
              not any(a[1] == "from-client" for a in shout), str(shout))


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
        props = ["hp"]
        if not FROM_SCENE:
            tracked["hp"] = 0
            net.replicate(tracked, props=props, velocity=False)
        proto = "Rig"
    else:
        tracked = find(scene, "Car")
        props = []
        net.replicate(tracked, velocity=True)
        proto = None
    pred = Predict(scene, tracked) if PREDICT else None
    rpc = Rpc(tracked) if RPC else None
    check("replicate gives an id", net.net_id(tracked) != 0, "id=%d" % net.net_id(tracked))
    initial = tuple(tracked.worldPosition)

    room = "scene-mode-test" if FROM_SCENE else "engine-test"
    if ROLE == "server":
        check("headless flag matches --server", net.headless == HEADLESS, "headless=%r" % net.headless)
        if HEADLESS:
            logic.setRender(True)  # must be refused: a headless server never draws
            check("headless server does not render", not logic.getRender())
    else:
        check("client is not headless", not net.headless)
    if FROM_SCENE:
        expected = int(os.environ.get("NET_EXPECT_ID", "0"))
        check("the saved net id reached the engine", net.net_id(tracked) == expected, "%d vs %d" % (net.net_id(tracked), expected))
        if ROLE == "server":
            check("scene mode opened the server", net.isServer and net.roomName == room and net.maxPlayers == 4,
                  "%r %r" % (net.roomName, net.maxPlayers))
    elif ROLE == "server":
        if pred:
            # The test machine renders two players in software: at 60 Hz neither keeps the tick rate, and
            # prediction needs both sides to run every tick on time.
            logic.setLogicTicRate(30.0)
        ok = net.host(PORT, max_players=4, room_name=room, websocket_port=0)
        check("host() opens the room", ok)
        check("isServer", net.isServer and net.isConnected)
        check("roomName/maxPlayers", net.roomName == room and net.maxPlayers == 4,
              "%r %r" % (net.roomName, net.maxPlayers))
        if pred:
            pred.server_start()
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
                if not pred:
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
            if pred:
                joined = [e[1] for e in events if e[0] == "join"]
                pred.server_frame(t, joined[0] if joined else 0)
            if rpc:
                joined = [e[1] for e in events if e[0] == "join"]
                rpc.server_frame(t, joined[0] if joined else 0)
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
                if any(entry["name"] == room for entry in found):
                    lobby["lan"] = found
            if net.isConnected:
                p = tracked.worldPosition
                if (p.x, p.y, p.z) != initial or positions:  # nothing before the first snapshot
                    positions.append((p.x, p.y, p.z))
                    times.append(time.time())
                if props:
                    hps.append(tracked["hp"])
                if proto:
                    if pred:
                        pred.client_frame(t, events)
                    if rpc:
                        rpc.client_frame(scene)
                    rig = [o for o in scene.objects if o.name == proto and net.net_id(o) != 0]
                    spawn_seen.append(len(rig))
            if any(e[0] == "reject" for e in events):
                break
        if t - last_log > 2.0:
            last_log = t
            log("t=%.1f tick=%d connected=%s rtt=%.0f pos=%s" % (
                t, net.tick, net.isConnected, net.rtt, tuple(round(v, 2) for v in tracked.worldPosition)))
        logic.NextFrame()

    if ROLE == "server":
        check("a client joined", any(e[0] == "join" for e in events), str(events))
        if HEADLESS:
            check("headless server hosts as Dedicated (net.clients has only the client)", clients_seen == 1,
                  "max=%d" % clients_seen)
        else:
            check("net.clients lists host + client", clients_seen >= 2, "max=%d" % clients_seen)
        names = [c.name for c in net.clients]
        check("client name arrived", any(n == CLIENT_NAME for n in names), str(names))
        check("lobby: client chat reached the server", ("chat", 1, "hello") in events, str(events))
        check("lobby: ready + start_game()", lobby["start"] is True, str(lobby["start"]))
        if pred:
            pred.server_checks()
        if rpc:
            rpc.server_checks()
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
        has_host = (0, "Tester-server", True) in [c[:3] for c in lobby["clients"]]
        has_self = any(c[0] == 1 and c[1] == CLIENT_NAME for c in lobby["clients"])
        if HEADLESS:
            check("lobby: dedicated server is not listed, the client is", not has_host and has_self, str(lobby["clients"]))
        else:
            check("lobby: client list has the host and itself", has_host and has_self, str(lobby["clients"]))
        check("lobby: server chat reached the client", ("chat", 0, "welcome") in events, str(events))
        check("lobby: on_start fired on the client", ("start",) in events, str(events))
        if lobby["lan"]:
            entry = [e for e in lobby["lan"] if e["name"] == room][0]
            check("LAN discovery lists the room", entry["port"] == PORT and entry["max_players"] == 4, str(entry))
        else:
            log("skip LAN discovery (no answer on this network)")
        check("client has no reject", not any(e[0] == "reject" for e in events), str(events))
        if pred:
            pred.client_checks(time.time() - start)
        if rpc:
            rpc.client_checks()

    net.disconnect()
    if ROLE == "server" and not FROM_SCENE:
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
