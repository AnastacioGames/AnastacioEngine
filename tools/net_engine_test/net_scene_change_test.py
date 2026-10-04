"""Scene change during a match (run_net_test.sh scene-change, file from make_scene_change.py).

  NET_ROLE=server|client|late NET_PORT=7777 RangeRuntime -p net_scene_change_test.py change.range

The server hosts in "Arena1" (replicated "Ball" on a circle) and calls net.change_scene("Arena2") at CHANGE_AT s;
there it moves the replicated "Box" and spawns the prototype "Shot". The client joins in Arena1 and must follow:
on_scene("Arena2"), Box moving, Shot spawned. The late client joins after the change with the same file (still
starting in Arena1) and must be moved to Arena2 too. Prints NETTEST lines like net_engine_test.py.
"""

import math
import os
import time
import traceback

from Range import logic
import Range.network as net

ROLE = os.environ.get("NET_ROLE", "server")
PORT = int(os.environ.get("NET_PORT", "7777"))
SECONDS = {"server": 19.0, "client": 14.0, "late": 9.0}[ROLE]
CHANGE_AT = 4.0
failures = []


def log(msg):
    print("NETTEST %s %s" % (ROLE, msg), flush=True)


def check(name, ok, detail=""):
    log("%s %s %s" % ("ok  " if ok else "FAIL", name, detail))
    if not ok:
        failures.append(name)


def current():
    scenes = logic.getSceneList()
    return scenes[0] if scenes else None


def obj(name):
    scene = current()
    for o in (scene.objects if scene else []):
        if o.name == name and net.net_id(o) != 0:
            return o
    return None


def raises(fn):
    try:
        fn()
    except RuntimeError:
        return True
    return False


def run():
    events = []
    net.on_scene(lambda name: events.append(("scene", name)))
    net.on_player_join(lambda cid, name: events.append(("join", cid)))
    net.on_disconnect(lambda reason, detail: events.append(("disconnect", reason, detail)))
    net.on_reject(lambda reason, detail: events.append(("reject", reason, detail)))
    net.playerName = "Tester-" + ROLE
    check("starts in Arena1", current().name == "Arena1", current().name)

    if ROLE == "server":
        check("host()", net.host(PORT, max_players=4, websocket_port=0))
        check("change_scene() refuses an unknown scene", raises(lambda: net.change_scene("Nowhere")))
        check("change_scene() refuses the current scene", raises(lambda: net.change_scene("Arena1")))
    else:
        check("change_scene() is server only", raises(lambda: net.change_scene("Arena2")))
        time.sleep(1.5 if ROLE == "client" else 0.5)
        check("join()", net.join("127.0.0.1:%d" % PORT))

    start = time.time()
    changed = False
    shot = None
    seen = {"Ball": [], "Box": [], "Shot": []}
    scene_at = None
    while time.time() - start < SECONDS:
        t = time.time() - start
        name = current().name if current() else None
        if ROLE == "server":
            ball, box = obj("Ball"), obj("Box")
            if ball:
                ball.worldPosition = [math.cos(t) * 4.0, math.sin(t) * 4.0, 1.0]
            if box:
                box.worldPosition = [math.cos(t) * 3.0, 4.0, math.sin(t) * 3.0 + 2.0]
            if not changed and t > CHANGE_AT and any(e[0] == "join" for e in events):
                net.change_scene("Arena2")
                changed = True
                log("change_scene(Arena2) at %.1f" % t)
            if ("scene", "Arena2") in events and shot is None:
                shot = net.spawn("Shot", owner=0, position=[0.0, 0.0, 5.0])
                check("spawn() in the new scene", shot is not None and net.net_id(shot) >= 0x80000000)
            if shot is not None and not shot.invalid:
                shot.worldPosition = [-math.cos(t) * 2.0, -math.sin(t) * 2.0, 5.0]
        elif net.isConnected:
            if scene_at is None and ("scene", "Arena2") in events:
                scene_at = t
            for key in seen:
                o = obj(key)
                if o is not None:
                    seen[key].append((name, tuple(o.worldPosition)))
        if any(e[0] in ("reject", "disconnect") for e in events):
            break
        logic.NextFrame()

    def span(samples):
        if len(samples) < 2:
            return 0.0
        return max(max(p[i] for _, p in samples) - min(p[i] for _, p in samples) for i in range(3))

    check("no disconnect or reject", not any(e[0] in ("reject", "disconnect") for e in events), str(events))
    check("on_scene('Arena2') fired", ("scene", "Arena2") in events, str(events))
    check("ends in Arena2", current() is not None and current().name == "Arena2",
          current().name if current() else None)
    if ROLE == "server":
        check("two clients joined", len([e for e in events if e[0] == "join"]) == 2, str(events))
    else:
        if ROLE == "client":
            check("Ball moved in Arena1 before the change", span(seen["Ball"]) > 1.0, "%.2f" % span(seen["Ball"]))
        check("Box moves in Arena2", span(seen["Box"]) > 1.0, "%.2f over %d" % (span(seen["Box"]), len(seen["Box"])))
        check("Shot spawned in Arena2 and moves", span(seen["Shot"]) > 1.0, "%.2f" % span(seen["Shot"]))
        check("nothing from Arena1 after the change", all(n == "Arena2" for n, _ in seen["Box"] + seen["Shot"]))
    net.disconnect()


try:
    run()
except Exception:
    traceback.print_exc()
    failures.append("exception")
log("PASS" if not failures else "FAIL " + ",".join(failures))
logic.endGame()
logic.NextFrame()
