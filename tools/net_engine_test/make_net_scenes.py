"""Authors the scenes of the scene-mode network test with the real editor (RNA, versioning and DNA).

  RangeEngine -b --python tools/net_engine_test/make_net_scenes.py -- <port> <out dir>

Opens projects-teste/halfanim_crash/halfanim_crash.blend (saved before the network settings existed, so this
also exercises the versioning that seeds the scene defaults) and writes net_host.range and net_client.range:
same scene, 'Spawner' with Replicate on and a replicated 'hp' game property; the scene mode is Host in one and
Client (127.0.0.1:<port>) in the other. Prints NETSCENE lines and ends with NETSCENE PASS or FAIL.
"""

import os
import sys

import bpy

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
port = int(argv[0]) if argv else 27777
out_dir = argv[1] if len(argv) > 1 else "."
root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
source = os.path.join(root, "projects-teste", "halfanim_crash", "halfanim_crash.blend")

failures = []


def check(name, ok, detail=""):
    print("NETSCENE %s %s %s" % ("ok  " if ok else "FAIL", name, detail), flush=True)
    if not ok:
        failures.append(name)


bpy.ops.wm.open_mainfile(filepath=source)
scene = bpy.context.scene
net = scene.game_settings.network

# Versioning: a file from before the settings gets the same defaults as a new scene.
check("old file gets the scene defaults", (net.mode, net.port, net.websocket_port, net.max_players, net.snapshot_rate) ==
      ('OFFLINE', 7777, 7778, 8, 20), str((net.mode, net.port, net.websocket_port, net.max_players, net.snapshot_rate)))
check("default names", net.server_name == "Anastacio Server" and net.address == "127.0.0.1" and net.game_id == "anastacio-game",
      "%r %r %r" % (net.server_name, net.address, net.game_id))

spawner = bpy.data.objects["Spawner"]
nobj = spawner.game.network
check("object starts without id", not nobj.use_replicate and nobj.net_id == 0)
nobj.use_replicate = True
first_id = nobj.net_id
check("Replicate generates a net id", 0 < first_id <= 0x7FFFFFFF, str(first_id))
check("Replicate seeds the sync defaults", nobj.sync_transform and nobj.use_interpolate and nobj.priority == 1.0)
nobj.sync_velocity = False

# Duplicates must not share the id.
bpy.ops.object.select_all(action='DESELECT')
spawner.select = True
bpy.context.scene.objects.active = spawner
bpy.ops.object.duplicate()
copy = bpy.context.scene.objects.active
check("duplicate gets another net id", copy != spawner and copy.game.network.use_replicate
      and copy.game.network.net_id not in (0, first_id), "%d vs %d" % (copy.game.network.net_id, first_id))
bpy.data.objects.remove(copy, do_unlink=True)

# Replicated game property.
bpy.context.scene.objects.active = spawner
bpy.ops.object.game_property_new(type='INT', name="hp")
prop = spawner.game.properties["hp"]
check("property flag defaults to off", not prop.use_replicate)
prop.use_replicate = True
check("property flag sticks", prop.use_replicate)

os.makedirs(out_dir, exist_ok=True)
for mode, name in (('HOST', "net_host.range"), ('CLIENT', "net_client.range")):
    net.mode = mode
    net.port = port
    net.websocket_port = 0
    net.address = "127.0.0.1:%d" % port
    net.server_name = "scene-mode-test"
    net.max_players = 4
    path = os.path.join(out_dir, name)
    bpy.ops.wm.save_as_mainfile(filepath=path, copy=True)
    check("wrote " + name, os.path.exists(path))

# Read it back: DNA round trip.
bpy.ops.wm.open_mainfile(filepath=os.path.join(out_dir, "net_host.range"))
net = bpy.context.scene.game_settings.network
spawner = bpy.data.objects["Spawner"]
check("DNA round trip (scene)", (net.mode, net.port, net.max_players, net.server_name) == ('HOST', port, 4, "scene-mode-test"),
      str((net.mode, net.port, net.max_players, net.server_name)))
check("DNA round trip (object)", spawner.game.network.use_replicate and spawner.game.network.net_id == first_id
      and spawner.game.properties["hp"].use_replicate, str(spawner.game.network.net_id))
print("NETSCENE id=%d" % first_id)
print("NETSCENE PASS" if not failures else "NETSCENE FAIL " + ",".join(failures), flush=True)
