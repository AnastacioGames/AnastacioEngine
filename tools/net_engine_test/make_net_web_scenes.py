"""Authors the Web end-to-end network test scenes with the real editor (RNA/DNA), like make_net_scenes.py
but with the HOST scene hosting a WebSocket port and the CLIENT scene carrying its own Python check
(no '-p' CLI available once packaged for the browser).

  RangeEngine -b --python tools/net_engine_test/make_net_web_scenes.py -- <port> <ws_port> <out dir>

Writes net_host.range (HOST, native, run with -p net_engine_test.py NET_FROM_SCENE=1 like the scene-server
test) and net_client.range (CLIENT, packaged for the Web with package-web.py): same 'Spawner' with Replicate
on and a replicated 'hp' property. The client scene gets an Always sensor + Python controller that watches
net.isConnected, 'hp' changing and the Spawner moving, and prints 'NETWEB client PASS|FAIL ...' once settled.
"""

import os
import sys

import bpy

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
port = int(argv[0]) if argv else 27777
ws_port = int(argv[1]) if len(argv) > 1 else port + 1
out_dir = argv[2] if len(argv) > 2 else "."
root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
source = os.path.join(root, "projects-teste", "halfanim_crash", "halfanim_crash.blend")

failures = []


def check(name, ok, detail=""):
    print("NETWEBSCENE %s %s %s" % ("ok  " if ok else "FAIL", name, detail), flush=True)
    if not ok:
        failures.append(name)


bpy.ops.wm.open_mainfile(filepath=source)
scene = bpy.context.scene
net = scene.game_settings.network

spawner = bpy.data.objects["Spawner"]
nobj = spawner.game.network
nobj.use_replicate = True
first_id = nobj.net_id
check("Replicate generates a net id", 0 < first_id <= 0x7FFFFFFF, str(first_id))
nobj.sync_velocity = False

bpy.ops.object.game_property_new(type='INT', name="hp")
spawner.game.properties["hp"].use_replicate = True

CHECK_SCRIPT = """import time
from Range import logic
import Range.network as net

cont = logic.getCurrentController()
owner = cont.owner

if "t0" not in owner:
    owner["t0"] = time.time()
    owner["hp0"] = owner.get("hp", 0)
    owner["p0x"] = owner.worldPosition.x
    owner["p0y"] = owner.worldPosition.y
    owner["connected"] = False
    owner["hp_changed"] = False
    owner["moved"] = False
    owner["done"] = False

if not owner["done"]:
    if net.isConnected:
        owner["connected"] = True
    if owner.get("hp", owner["hp0"]) != owner["hp0"]:
        owner["hp_changed"] = True
    dx = owner.worldPosition.x - owner["p0x"]
    dy = owner.worldPosition.y - owner["p0y"]
    if (dx * dx + dy * dy) ** 0.5 > 0.5:
        owner["moved"] = True
    if time.time() - owner["t0"] > 12.0:
        owner["done"] = True
        ok = owner["connected"] and owner["hp_changed"] and owner["moved"]
        print("NETWEB client %s connected=%s hp_changed=%s moved=%s" % (
            "PASS" if ok else "FAIL", owner["connected"], owner["hp_changed"], owner["moved"]), flush=True)
"""
script = bpy.data.texts.new("net_web_client_check.py")
script.write(CHECK_SCRIPT)
bpy.ops.logic.sensor_add(type='ALWAYS', object=spawner.name)
sens = spawner.game.sensors[-1]
sens.use_pulse_true_level = True
bpy.ops.logic.controller_add(type='PYTHON', object=spawner.name)
ctrl = spawner.game.controllers[-1]
ctrl.text = script
sens.link(ctrl)

os.makedirs(out_dir, exist_ok=True)
net.mode = 'HOST'
net.port = port
net.websocket_port = ws_port
net.server_name = "web-e2e-test"
net.max_players = 4
host_path = os.path.join(out_dir, "net_host.range")
bpy.ops.wm.save_as_mainfile(filepath=host_path, copy=True)
check("wrote net_host.range", os.path.exists(host_path))

net.mode = 'CLIENT'
net.port = port
# The Web client only speaks WebSocket: its address must point at the host's websocket_port, not the ENet
# port (NET_TransportWebClient wraps a plain "host:port" into "ws://host:port/" verbatim).
net.address = "127.0.0.1:%d" % ws_port
net.server_name = "web-e2e-test"
net.max_players = 4
client_path = os.path.join(out_dir, "net_client.range")
bpy.ops.wm.save_as_mainfile(filepath=client_path, copy=True)
check("wrote net_client.range", os.path.exists(client_path))

print("NETWEBSCENE id=%d" % first_id)
print("NETWEBSCENE PASS" if not failures else "NETWEBSCENE FAIL " + ",".join(failures), flush=True)
