"""Physics and animation stress, with almost nothing else to do.

    RangeEngine -b --python tools/create_perf_physics_anim_test.py -- projects-teste/perf/physanim

  physics_<N>o  N rigid boxes stacked in columns of 5 on a static floor, deactivation off, so every
                body keeps its contacts and is simulated every frame (a resting pile, stable over time).
  anim_<N>c     N characters: 12-bone armature deforming a ~1500 vertex mesh, Action actuator playing
                a looped action. No physics on them.

Plain materials, one Sun without shadow: the frame is physics or animation bound. Reports go through
tools/tests/perf/perf_probe.py like the pbr_lights and logic cases.
"""
import bpy
import math
import os
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
outdir = os.path.abspath(argv[0] if argv else "projects-teste/perf/physanim")

HERE = os.path.dirname(os.path.abspath(__file__))
PROBE = os.path.join(HERE, "tests", "perf", "perf_probe.py")

PHYSICS_CASES = [500, 2000]
ANIM_CASES = [100, 400]
TICRATE = 1000
BONES = 12

RUNTIME = '''import Range
import perf_probe

perf_probe.tick("%(case)s", [("objects", %(objects)d), ("kind", "%(kind)s")])
'''


def setup_scene(ticrate=TICRATE):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_GAME'
    scene.name = "Scene"
    game = scene.game_settings
    game.vsync = 'OFF'
    game.use_frame_rate = False
    game.show_framerate_profile = False
    game.use_dynamic_resolution = False
    game.physics_engine = 'BULLET'
    game.fps = ticrate
    game.resolution_x, game.resolution_y = 1280, 720
    scene.world = bpy.data.worlds.new("World")
    scene.world.horizon_color = (0.05, 0.05, 0.08)
    scene.world.mist_settings.use_mist = False
    sun = bpy.data.objects.new("Sun", bpy.data.lamps.new("Sun", 'SUN'))
    sun.data.use_shadow = False
    sun.rotation_euler = (0.7, 0.2, 0.5)
    scene.objects.link(sun)
    return scene


def material(name, rgb):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = rgb
    return mat


def camera(scene, loc, target, clip):
    from mathutils import Vector
    data = bpy.data.cameras.new("Camera")
    data.clip_end = clip
    data.lens = 18
    cam = bpy.data.objects.new("Camera", data)
    scene.objects.link(cam)
    cam.location = loc
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    scene.camera = cam
    return cam


def finish(scene, cam, case, objects, kind):
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
    print("[PerfPhysAnim] wrote", path)


def build_physics(objects, case):
    # 60 Hz like a game: one physics step per logic tick (at 1000 Hz the frame ran ~5 catch-up steps).
    scene = setup_scene(60)
    cols = int(math.ceil(math.sqrt(objects / 5.0)))
    step = 1.5
    half = cols * step * 0.5

    bpy.ops.mesh.primitive_cube_add(radius=1, location=(0, 0, -0.5))
    floor = bpy.context.object
    floor.name = "Floor"
    floor.scale = (half + 2, half + 2, 0.5)
    floor.data.materials.append(material("Floor", (0.5, 0.5, 0.5)))
    floor.game.physics_type = 'STATIC'

    bpy.ops.mesh.primitive_cube_add(radius=0.5, location=(0, 0, 0))
    tmpl = bpy.context.object
    tmpl.name = "Box"
    tmpl.data.materials.append(material("Box", (0.8, 0.4, 0.2)))
    tmpl.game.physics_type = 'RIGID_BODY'
    tmpl.game.use_sleep = True  # "No Sleeping": the pile never deactivates
    tmpl.game.mass = 1.0
    tmpl.game.use_collision_bounds = True
    tmpl.game.collision_bounds_type = 'BOX'

    for i in range(objects):
        ob = tmpl if i == 0 else tmpl.copy()
        if i:
            ob.name = "Box%04d" % i
            scene.objects.link(ob)
        col, level = i // 5, i % 5
        ob.location = ((col % cols) * step - half, (col // cols) * step - half, 0.55 + level * 1.1)  # gap: touching boxes overlap by the margin and explode

    cam = camera(scene, (0, -half * 2.2, half * 1.6), (0, 0, 0), half * 8)
    finish(scene, cam, case, objects, "physics")


def build_character():
    """Armature with a vertical chain of BONES bones and a stretched sphere skinned by height."""
    height = 2.0
    arm_data = bpy.data.armatures.new("Rig")
    rig = bpy.data.objects.new("Rig", arm_data)
    bpy.context.scene.objects.link(rig)
    bpy.context.scene.objects.active = rig
    bpy.ops.object.mode_set(mode='EDIT')
    prev = None
    for b in range(BONES):
        bone = arm_data.edit_bones.new("B%02d" % b)
        bone.head = (0, 0, height * b / BONES)
        bone.tail = (0, 0, height * (b + 1) / BONES)
        if prev:
            bone.parent = prev
            bone.use_connect = True
        prev = bone
    bpy.ops.object.mode_set(mode='OBJECT')

    # UV sphere stretched to the bone chain: 24 x 59 rings + 2 poles = 1418 vertices.
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=60, size=1.0, location=(0, 0, height / 2))
    body = bpy.context.object
    body.name = "Body"
    body.scale = (0.25, 0.25, height / 2)
    bpy.ops.object.transform_apply(scale=True)
    body.data.materials.append(material("Body", (0.3, 0.6, 0.9)))
    body.game.physics_type = 'NO_COLLISION'
    groups = [body.vertex_groups.new("B%02d" % b) for b in range(BONES)]
    for v in body.data.vertices:
        z = (body.matrix_world * v.co).z
        f = max(0.0, min(BONES - 1.0001, z / height * BONES - 0.5))
        b = int(f)
        groups[b].add([v.index], 1.0 - (f - b), 'REPLACE')
        groups[b + 1].add([v.index], f - b, 'REPLACE')
    body.parent = rig
    mod = body.modifiers.new("Armature", 'ARMATURE')
    mod.object = rig

    action = bpy.data.actions.new("Sway")
    action.use_fake_user = True  # only the actuator uses it after animation_data is cleared
    rig.animation_data_create()
    rig.animation_data.action = action
    for b in range(BONES):
        pb = rig.pose.bones["B%02d" % b]
        pb.rotation_mode = 'XYZ'
        for frame, angle in ((1, -0.12), (21, 0.12), (41, -0.12)):
            pb.rotation_euler = (angle, angle * 0.5 * (1 if b % 2 else -1), 0)
            pb.keyframe_insert("rotation_euler", frame=frame)
    rig.animation_data.action = None
    rig.game.physics_type = 'NO_COLLISION'

    bpy.context.scene.objects.active = rig
    bpy.ops.logic.sensor_add(type='ALWAYS', name="Always", object=rig.name)
    bpy.ops.logic.controller_add(type='LOGIC_AND', name="And", object=rig.name)
    bpy.ops.logic.actuator_add(type='ACTION', name="Play", object=rig.name)
    act = rig.game.actuators["Play"]
    act.action = action
    act.play_mode = 'LOOPEND'
    act.frame_start = 1
    act.frame_end = 41
    rig.game.sensors["Always"].link(rig.game.controllers["And"])
    rig.game.controllers["And"].link(actuator=act)
    return rig, body


def build_anim(chars, case):
    scene = setup_scene()
    rig, body = build_character()
    cols = int(math.ceil(math.sqrt(chars)))
    step = 1.2
    half = cols * step * 0.5
    for i in range(chars):
        if i == 0:
            r, m = rig, body
        else:
            r = rig.copy()
            r.name = "Rig%04d" % i
            scene.objects.link(r)
            m = body.copy()
            m.name = "Body%04d" % i
            scene.objects.link(m)
            m.parent = r
            m.modifiers["Armature"].object = r
        r.location = ((i % cols) * step - half, (i // cols) * step - half, 0)

    bpy.ops.mesh.primitive_plane_add(radius=half + 2, location=(0, 0, 0))
    floor = bpy.context.object
    floor.data.materials.append(material("Floor", (0.5, 0.5, 0.5)))
    floor.game.physics_type = 'NO_COLLISION'

    cam = camera(scene, (0, -half * 2.0, half * 1.4 + 2), (0, 0, 1), half * 8)
    finish(scene, cam, case, chars, "anim")


if not os.path.isdir(outdir):
    os.makedirs(outdir)

for n in PHYSICS_CASES:
    build_physics(n, "physics_%do" % n)
for n in ANIM_CASES:
    build_anim(n, "anim_%dc" % n)

print("[PerfPhysAnim] %d cases in %s" % (len(PHYSICS_CASES) + len(ANIM_CASES), outdir))
