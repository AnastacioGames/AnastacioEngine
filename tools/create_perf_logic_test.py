"""Logic stress: per-object logic every frame, with almost nothing to draw.

    RangeEngine -b --python tools/create_perf_logic_test.py -- projects-teste/perf/logic
    python tools/run_perf_suite.py projects-teste/perf/logic

Each object carries the same work in one of two forms:

  bricks  Always (pulse) -> AND -> Motion (rotate) and Property (add 1 to "n")
  python  Always (pulse) -> Python module controller doing the same in logic_mod.run

Tiny cubes, one shared material, no lamps and no shadows: the frame is logic bound, so the
"Logic" and "Python" categories of the report are what moves. Reports go through
tools/tests/perf/perf_probe.py like the pbr_lights cases.
"""
import bpy
import math
import os
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
outdir = os.path.abspath(argv[0] if argv else "projects-teste/perf/logic")

HERE = os.path.dirname(os.path.abspath(__file__))
PROBE = os.path.join(HERE, "tests", "perf", "perf_probe.py")

CASES = [500, 2000]
KINDS = ["bricks", "python"]
TICRATE = 1000

RUNTIME = '''import Range
import perf_probe

perf_probe.tick("%(case)s", [("objects", %(objects)d), ("kind", "%(kind)s")])
'''

MODULE = '''def run(cont):
    own = cont.owner
    own.applyRotation((0.0, 0.0, 0.01), True)
    own["n"] += 1
'''


def setup_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_GAME'
    scene.name = "Scene"
    game = scene.game_settings
    game.vsync = 'OFF'
    game.use_frame_rate = False
    game.show_framerate_profile = False
    game.use_dynamic_resolution = False
    game.fps = TICRATE
    game.resolution_x, game.resolution_y = 1280, 720
    scene.world = bpy.data.worlds.new("World")
    scene.world.horizon_color = (0.05, 0.05, 0.08)
    return scene


def template(scene, kind, module_text):
    bpy.ops.mesh.primitive_cube_add(radius=0.3)
    ob = bpy.context.object
    ob.name = "Tmpl"
    ob.data.materials.append(bpy.data.materials.new("Mat"))
    ob.game.physics_type = 'NO_COLLISION'
    scene.objects.active = ob

    bpy.ops.object.game_property_new(type='INT', name="n")
    bpy.ops.logic.sensor_add(type='ALWAYS', name="Always", object=ob.name)
    sensor = ob.game.sensors["Always"]
    sensor.use_pulse_true_level = True

    if kind == "bricks":
        bpy.ops.logic.controller_add(type='LOGIC_AND', name="And", object=ob.name)
        bpy.ops.logic.actuator_add(type='MOTION', name="Rot", object=ob.name)
        bpy.ops.logic.actuator_add(type='PROPERTY', name="Add", object=ob.name)
        cont = ob.game.controllers["And"]
        rot = ob.game.actuators["Rot"]
        rot.offset_rotation = (0.0, 0.0, 0.01)
        add = ob.game.actuators["Add"]
        add.mode = 'ADD'
        add.property = "n"
        add.value = "1"
        sensor.link(cont)
        cont.link(actuator=rot)
        cont.link(actuator=add)
    else:
        bpy.ops.logic.controller_add(type='PYTHON', name="Py", object=ob.name)
        cont = ob.game.controllers["Py"]
        cont.mode = 'MODULE'
        cont.module = "logic_mod.run"
        sensor.link(cont)
    return ob


def build(objects, kind, case):
    scene = setup_scene()
    module_text = bpy.data.texts.new("logic_mod.py")
    module_text.write(MODULE)
    tmpl = template(scene, kind, module_text)

    cols = int(math.ceil(math.sqrt(objects)))
    step = 1.0
    for i in range(objects):
        ob = tmpl if i == 0 else tmpl.copy()
        if i:
            ob.name = "Obj%04d" % i
            scene.objects.link(ob)
        ob.location = ((i % cols) * step - cols * step * 0.5,
                       (i // cols) * step - cols * step * 0.5, 0.0)

    span = cols * step
    cam_data = bpy.data.cameras.new("Camera")
    cam_data.clip_end = span * 4.0
    cam = bpy.data.objects.new("Camera", cam_data)
    scene.objects.link(cam)
    cam.location = (0.0, 0.0, span * 1.6)
    scene.camera = cam

    probe = bpy.data.texts.new("perf_probe.py")
    with open(PROBE) as f:
        probe.write(f.read())
    text = bpy.data.texts.new("perf.py")
    text.write(RUNTIME % {"case": case, "objects": objects, "kind": kind})

    scene.objects.active = cam
    bpy.ops.logic.sensor_add(type='ALWAYS', name="Always", object=cam.name)
    bpy.ops.logic.controller_add(type='PYTHON', name="Perf", object=cam.name)
    sensor = cam.game.sensors["Always"]
    sensor.use_pulse_true_level = True
    controller = cam.game.controllers["Perf"]
    controller.text = text
    sensor.link(controller)

    path = os.path.join(outdir, "%s.range" % case)
    bpy.ops.wm.save_as_mainfile(filepath=path, check_existing=False, compress=False)
    print("[PerfLogic] wrote", path)


if not os.path.isdir(outdir):
    os.makedirs(outdir)

for kind in KINDS:
    for objects in CASES:
        build(objects, kind, "logic_%s_%do" % (kind, objects))

print("[PerfLogic] %d cases in %s" % (len(KINDS) * len(CASES), outdir))
