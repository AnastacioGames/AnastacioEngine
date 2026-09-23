"""Run with RangeEngine -b --python tools/create_web_capabilities_scene.py.

Jogo de teste das capacidades de simulacao/transicao no runtime Web: fisica (queda de corpo rigido),
addObject/endObject, addScene (overlay) e replace de cena. O script de cada cena imprime linhas
"[cap] ..." que tools/web/verify-capabilities.cjs (modo sim) confere. Saida: build-web/bin/web-capabilities.range.
"""
import os
import bpy
from mathutils import Vector
from pathlib import Path

bpy.ops.wm.read_factory_settings(use_empty=True)

# Variantes para isolar defeitos do runtime (CAP_VARIANT=nophys|nolamp|onescene); padrao: jogo completo.
VARIANT = os.environ.get("CAP_VARIANT", "")

CONTROL_A = '''import Range
cont = Range.logic.getCurrentController()
obj = cont.owner
scene = Range.logic.getCurrentScene()
tick = obj.get("tick", 0) + 1
obj["tick"] = tick

if tick == 1:
    faller = scene.objects["Faller"]
    obj["z0"] = faller.worldPosition.z
    print("[cap] scene A running", flush=True)
elif tick == 90:
    z = scene.objects["Faller"].worldPosition.z
    print("[cap] physics %s z0=%.2f z=%.2f" % ("fell" if z < obj["z0"] - 0.5 else "STUCK", obj["z0"], z), flush=True)
elif tick == 100:
    new = scene.addObject("Template", obj, 0)
    obj["spawn_name"] = new.name
    print("[cap] spawn %s" % ("ok" if new and "Template" in new.name else "FAIL"), flush=True)
elif tick == 110:
    names = [o.name for o in scene.objects]
    spawned = [n for n in names if n.startswith("Template")]
    print("[cap] spawn present=%d" % len(spawned), flush=True)
    for o in scene.objects:
        if o.name == obj.get("spawn_name"):
            o.endObject()
elif tick == 120:
    names = [o.name for o in scene.objects]
    print("[cap] endObject %s" % ("ok" if obj.get("spawn_name") not in names else "FAIL"), flush=True)
    Range.logic.addScene("B", 1)
elif tick == 140:
    names = [s.name for s in Range.logic.getSceneList()]
    print("[cap] overlay %s scenes=%s" % ("ok" if "B" in names else "FAIL", ",".join(sorted(names))), flush=True)
elif tick == 150:
    scene.replace("C")
    print("[cap] replace requested", flush=True)
'''

PROBE = '''import Range
print("[probe] 0 start", flush=True)
scene = Range.logic.getCurrentScene()
print("[probe] 1 getCurrentScene", flush=True)
objs = scene.objects
print("[probe] 2 scene.objects", flush=True)
f = objs["Faller"]
print("[probe] 3 objects[name]", flush=True)
p = f.worldPosition
print("[probe] 4 worldPosition", flush=True)
z = p.z
print("[probe] 5 .z", flush=True)
n = scene.name
print("[probe] 6 scene.name", flush=True)
'''

CONTROL_MARK = '''import Range
cont = Range.logic.getCurrentController()
obj = cont.owner
tick = obj.get("tick", 0) + 1
obj["tick"] = tick
if tick == 1:
    print("[cap] scene %s running" % Range.logic.getCurrentScene().name, flush=True)
if tick == 60:
    print("[cap] scene %s alive after 60 ticks" % Range.logic.getCurrentScene().name, flush=True)
'''


def add_camera(scene, name):
    cam = bpy.data.objects.new(name, bpy.data.cameras.new(name))
    scene.objects.link(cam)
    cam.location = (0, -10, 4)
    cam.rotation_euler = (Vector((0, 0, 0)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    scene.camera = cam
    return cam


def add_controller(scene, ob, text_name, source):
    text = bpy.data.texts.new(text_name)
    text.write(source)
    scene.objects.active = ob
    bpy.ops.logic.sensor_add(type='ALWAYS', object=ob.name)
    sensor = ob.game.sensors[-1]
    sensor.use_pulse_true_level = True
    bpy.ops.logic.controller_add(type='PYTHON', object=ob.name)
    controller = ob.game.controllers[-1]
    controller.text = text
    sensor.link(controller)


def base_scene(scene, name):
    scene.name = name
    scene.render.engine = 'BLENDER_GAME'
    scene.game_settings.resolution_x = 640
    scene.game_settings.resolution_y = 480
    scene.world = bpy.data.worlds.new(name + " world")
    add_camera(scene, name + "Cam")
    if VARIANT != "nolamp":
        lamp = bpy.data.objects.new(name + "Sun", bpy.data.lamps.new(name + "Sun", 'SUN'))
        scene.objects.link(lamp)
        lamp.rotation_euler = (0.9, 0.2, 0.6)


scene_a = bpy.context.scene
base_scene(scene_a, "A")
scene_a.layers = [True] + [False] * 19

bpy.ops.mesh.primitive_plane_add(location=(0, 0, 0))
floor = bpy.context.object
floor.name = "Floor"
floor.scale = (10, 10, 1)
floor.game.physics_type = 'STATIC'

bpy.ops.mesh.primitive_cube_add(location=(0, 0, 5))
faller = bpy.context.object
faller.name = "Faller"
faller.game.physics_type = 'NO_COLLISION' if VARIANT == "nophys" else 'RIGID_BODY'

bpy.ops.mesh.primitive_cube_add(location=(3, 0, 1))
ctrl = bpy.context.object
ctrl.name = "Ctrl"
ctrl.game.physics_type = 'NO_COLLISION'

# Template fica fora da camada ativa (layer 2): so existe para addObject.
bpy.ops.mesh.primitive_cube_add(location=(-3, 0, 1))
template = bpy.context.object
template.name = "Template"
template.game.physics_type = 'NO_COLLISION'
template.layers = [False, True] + [False] * 18
add_controller(scene_a, ctrl, "cap_a.py", PROBE if VARIANT == "probe" else CONTROL_A)

for name in (() if VARIANT == "onescene" else ("B", "C")):
    sc = bpy.data.scenes.new(name)
    base_scene(sc, name)
    bpy.context.screen.scene = sc if bpy.context.screen else sc
    bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0))
    mark = bpy.context.object
    mark.name = "Mark" + name
    mark.game.physics_type = 'NO_COLLISION'
    add_controller(sc, mark, "cap_%s.py" % name.lower(), CONTROL_MARK)

bpy.context.screen.scene = scene_a
output = Path(__file__).resolve().parents[1] / 'build-web' / 'bin' / ('web-capabilities%s.range' % (('-' + VARIANT) if VARIANT else ''))
bpy.ops.wm.save_as_mainfile(filepath=str(output))
print('[web-cap] saved', str(output))
