"""Heavy loading benchmark: many external .range chunks + many inactive-layer objects.

Run with:  RangeEngine -b --python tools/create_load_bench.py -- <output_dir> [chunks] [per_chunk] [inactive] [async] [nolamp]
Defaults:  20 chunks, 15 objects per chunk, 200 inactive objects in main, synchronous LibLoad, one lamp per chunk.

Writes <output_dir>/chunk_XX.range and <output_dir>/main.range. Play main.range with the system
console open: the engine prints its "[Load]" stage lines (open, link, convert, merge/shaders) and the
script prints "[LoadBench]" with the total, then ends the game. Every object has its own mesh copy with
UVs (tangents) and its own material copy, the costly case the load analysis plan wants to measure.
"""
import bpy
import os
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output_dir = os.path.abspath(argv[0] if argv else "load_bench")
chunks = int(argv[1]) if len(argv) > 1 else 20
per_chunk = int(argv[2]) if len(argv) > 2 else 15
inactive = int(argv[3]) if len(argv) > 3 else 200
use_async = "async" in argv[4:]
no_lamp = "nolamp" in argv[4:]  # Chunks without lamps: the merge then compiles only the new materials.

os.makedirs(output_dir, exist_ok=True)


def new_file():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_GAME'
    scene.game_settings.obstacle_simulation = 'NONE'
    return scene


def base_mesh(name, kind):
    if kind == 0:
        bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, calc_uvs=True)
    elif kind == 1:
        bpy.ops.mesh.primitive_cylinder_add(vertices=32, calc_uvs=True)
    else:
        bpy.ops.mesh.primitive_monkey_add(calc_uvs=True)
    ob = bpy.context.object
    me = ob.data
    me.name = name
    bpy.data.objects.remove(ob, do_unlink=True)
    return me


def add_objects(scene, prefix, count, layer, spacing, offset):
    """Objects with their own mesh and material copies, on the given layer (0-based)."""
    meshes = [base_mesh(prefix + "Base%d" % k, k) for k in range(3)]
    side = max(1, int(count ** 0.5))
    layers = [i == layer for i in range(20)]
    for i in range(count):
        me = meshes[i % 3].copy()
        mat = bpy.data.materials.new(prefix + "Mat")  # Mat, Mat.001...: duplicates on purpose.
        mat.diffuse_color = ((i * 0.37) % 1.0, (i * 0.61) % 1.0, (i * 0.83) % 1.0)
        mat.specular_intensity = 0.3
        me.materials.append(mat)
        ob = bpy.data.objects.new("%s%03d" % (prefix, i), me)
        scene.objects.link(ob)
        ob.layers = layers
        ob.location = (offset[0] + (i % side) * spacing, offset[1] + (i // side) * spacing, offset[2])
        ob.game.physics_type = 'RIGID_BODY' if i % 4 == 0 else 'STATIC'
    for me in meshes:
        if me.users == 0:
            bpy.data.meshes.remove(me)


def add_lamp(scene, name, type_, location, layer=0):
    lamp = bpy.data.lamps.new(name, type_)
    ob = bpy.data.objects.new(name, lamp)
    scene.objects.link(ob)
    ob.layers = [i == layer for i in range(20)]
    ob.location = location
    return ob


for c in range(chunks):
    scene = new_file()
    scene.name = "Scene"
    prefix = "C%02d_" % c
    add_objects(scene, prefix, per_chunk, 0, 2.5, ((c % 5) * 15.0, (c // 5) * 15.0, 1.0))
    if not no_lamp:
        add_lamp(scene, prefix + "Lamp", 'POINT', ((c % 5) * 15.0 + 5.0, (c // 5) * 15.0 + 5.0, 6.0))
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(output_dir, "chunk_%02d.range" % c),
                                check_existing=False, compress=False)

scene = new_file()
scene.name = "Scene"
add_lamp(scene, "Sun", 'SUN', (0, 0, 20))
cam_data = bpy.data.cameras.new("Camera")
cam = bpy.data.objects.new("Camera", cam_data)
scene.objects.link(cam)
cam.location = (35, -40, 45)
cam.rotation_euler = (0.85, 0, 0)
scene.camera = cam
add_objects(scene, "Inactive_", inactive, 1, 2.5, (0, 0, 1))

text = bpy.data.texts.new("load_bench.py")
text.write('''import Range
import time

CHUNKS = %d
ASYNC = %s

g = Range.logic.globalDict
if "load_bench" not in g:
    t0 = time.perf_counter()
    status = [Range.logic.LibLoad(Range.logic.expandPath("//chunk_%%02d.range" %% i), "Scene",
                                  asynchronous=ASYNC) for i in range(CHUNKS)]
    g["load_bench"] = (t0, status)
t0, status = g["load_bench"]
if all(s.finished for s in status):
    scene = Range.logic.getCurrentScene()
    print("[LoadBench] %%d chunks (%%s): %%.0f ms, %%d objects, %%d inactive" %% (
        CHUNKS, "async" if ASYNC else "sync", (time.perf_counter() - t0) * 1000.0,
        len(scene.objects), len(scene.objectsInactive)))
    Range.logic.endGame()
''' % (chunks, use_async))

bpy.context.scene.objects.active = cam
bpy.ops.logic.sensor_add(type='ALWAYS', name="Always", object=cam.name)
bpy.ops.logic.controller_add(type='PYTHON', name="Bench", object=cam.name)
sensor = cam.game.sensors["Always"]
sensor.use_pulse_true_level = True
controller = cam.game.controllers["Bench"]
controller.text = text
sensor.link(controller)

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(output_dir, "main.range"), check_existing=False, compress=False)
print("[LoadBench] wrote %d chunks + main.range to %s" % (chunks, output_dir))
