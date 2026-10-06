"""Bottleneck A: cost of re-uploading the light uniforms once per drawn object.

Writes the whole case matrix in one run:

  RangeEngine -b --python tools/create_perf_pbr_lights_test.py -- projects-teste/perf/pbr_lights
  RangeRuntime projects-teste/perf/pbr_lights/pbr_900o_8l_1m_cpu.range

Each case appends to perf_<case>_<tag>.txt (tag from RANGE_SHOT_TAG) via tools/tests/perf/perf_probe.py.

The decisive axis is materials: 1 material (one bucket) vs N (one per object). If the light
uniforms were bound per bucket, the 1-material case would be nearly free; if they are bound per
object, both cost the same. That is what separates bottleneck A from a wrong guess.

Materials use nodes, because material->use_scene_lights only turns on when the shader has
unflightsource[] (gpu_material.c) -- a classic Blender Internal material never exercises this path,
which is why tools/create_shader_fps_test.py cannot measure it.

The camera is static and frames the whole grid: every object stays visible in every frame of every
run, so the counters are constant by construction and the only variable is the case itself.
"""
import bpy
import math
import os
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
outdir = os.path.abspath(argv[0] if argv else "projects-teste/perf/pbr_lights")

HERE = os.path.dirname(os.path.abspath(__file__))
PROBE = os.path.join(HERE, "tests", "perf", "perf_probe.py")

# (objects, lights). 900 across every light count isolates the light axis; 100 and 400 at the
# worst light count give the slope against object count.
CASES = [(900, 1), (900, 4), (900, 8), (100, 8), (400, 8)]
MATERIALS = [("1m", False), ("Nm", True)]
# cpu: poor mesh at 720p, so the per-object CPU work dominates. gpu: heavy mesh at 1080p, to show
# whether the same saving disappears once the frame is fill/vertex bound.
TICRATE = 1000
VARIANTS = {
    "cpu": {"segments": 8, "rings": 6, "res": (1280, 720)},
    "gpu": {"segments": 48, "rings": 24, "res": (1920, 1080)},
}

RUNTIME = '''import Range
import perf_probe

perf_probe.tick("%(case)s", [("objects", %(objects)d), ("lights", %(lights)d),
                             ("materials", "%(materials)s"), ("variant", "%(variant)s"),
                             ("res", "%(res)s")])
'''


def material(index, per_object):
    """One node material shared by every object, or a distinct one per object. Only the base
    colour differs, so the shader program is the same and the material count is the only variable."""
    mat = bpy.data.materials.new("Pbr%03d" % index if per_object else "Pbr")
    mat.use_nodes = True
    node = mat.node_tree.nodes.get("Diffuse BSDF")
    if node is not None:
        node.inputs["Color"].default_value = ((index * 0.37) % 1.0, (index * 0.61) % 1.0,
                                             (index * 0.83) % 1.0, 1.0)
    return mat


def build(objects, lights, mat_label, per_object, variant, spec, case):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_GAME'
    scene.name = "Scene"

    game = scene.game_settings
    game.use_shading_nodes = True
    game.vsync = 'OFF'
    game.use_frame_rate = False
    game.show_framerate_profile = False
    game.show_render_queries = False
    game.use_dynamic_resolution = False
    # KX_KetsjiEngine::UpdateSleepTime() runs unconditionally and sleeps up to 1/ticrate, so the
    # frame rate can never exceed the logic ticrate even with "Use Frame Rate" off. A high ticrate
    # puts the cap far above the cost under test; without this every case just reads 60 fps.
    game.fps = TICRATE
    game.resolution_x, game.resolution_y = spec["res"]

    scene.world = bpy.data.worlds.new("World")
    scene.world.horizon_color = (0.05, 0.05, 0.08)
    scene.world.ambient_color = (0.10, 0.10, 0.10)

    bpy.ops.mesh.primitive_uv_sphere_add(segments=spec["segments"], ring_count=spec["rings"],
                                         calc_uvs=True)
    base = bpy.context.object.data
    bpy.data.objects.remove(bpy.context.object, do_unlink=True)

    cols = int(math.ceil(math.sqrt(objects)))
    shared = None if per_object else material(0, False)
    step = 2.4
    for i in range(objects):
        me = base.copy()
        me.materials.append(material(i, True) if per_object else shared)
        ob = bpy.data.objects.new("Obj%04d" % i, me)
        scene.objects.link(ob)
        ob.location = ((i % cols) * step - cols * step * 0.5,
                       (i // cols) * step - cols * step * 0.5, 0.0)
        ob.game.physics_type = 'NO_COLLISION'

    # The first light is a sun so there is always one directional shadow; the rest are points
    # spread over the grid. All cast shadows, so the shadow lamp slots fill up as well.
    span = cols * step
    for k in range(lights):
        if k == 0:
            data = bpy.data.lamps.new("Sun", 'SUN')
            data.energy = 0.8
            loc, rot = (0.0, 0.0, span), (0.6, 0.2, 0.4)
        else:
            data = bpy.data.lamps.new("Point%d" % k, 'POINT')
            data.energy = 1.5
            data.distance = span
            angle = (k - 1) * 2.0 * math.pi / max(lights - 1, 1)
            loc = (math.cos(angle) * span * 0.35, math.sin(angle) * span * 0.35, span * 0.25)
            rot = (0.0, 0.0, 0.0)
        data.use_shadow = True
        data.color = (1.0, 0.95 - 0.05 * (k % 3), 0.9)
        lamp = bpy.data.objects.new(data.name, data)
        scene.objects.link(lamp)
        lamp.location = loc
        lamp.rotation_euler = rot

    cam_data = bpy.data.cameras.new("Camera")
    cam_data.lens = 35
    cam_data.clip_end = span * 4.0
    cam = bpy.data.objects.new("Camera", cam_data)
    scene.objects.link(cam)
    # Straight down the Z axis from far enough that the whole grid fits in the *vertical* FOV
    # (the narrow one at 16:9), so cullingVisible equals the object count and nothing is culled.
    cam.location = (0.0, 0.0, span * 2.4)
    cam.rotation_euler = (0.0, 0.0, 0.0)
    scene.camera = cam

    probe = bpy.data.texts.new("perf_probe.py")
    with open(PROBE) as f:
        probe.write(f.read())

    text = bpy.data.texts.new("perf.py")
    text.write(RUNTIME % {"case": case, "objects": objects, "lights": lights,
                          "materials": mat_label, "variant": variant,
                          "res": "%dx%d" % spec["res"]})

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
    print("[PerfPbrLights] wrote", path)


if not os.path.isdir(outdir):
    os.makedirs(outdir)

for variant, spec in sorted(VARIANTS.items()):
    for objects, lights in CASES:
        for mat_label, per_object in MATERIALS:
            build(objects, lights, mat_label, per_object, variant, spec,
                  "pbr_%do_%dl_%s_%s" % (objects, lights, mat_label, variant))

print("[PerfPbrLights] %d cases in %s" % (len(VARIANTS) * len(CASES) * len(MATERIALS), outdir))
