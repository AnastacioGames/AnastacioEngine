"""Frame time check for RANGE_SHADER_UNIFORM_VALUES: a heavy scene of many spheres, many lights and an orbiting
camera, with vsync and the frame cap off.

Run with:  RangeEngine -b --python tools/create_shader_fps_test.py -- <output.range>
Play it with RangeRuntime: it skips WARMUP logic ticks, samples the render frame time on the next SAMPLES ticks
(10 s), appends the average to <output dir>/fps_<tag>.txt and ends the game. The tag comes from RANGE_SHOT_TAG
(default "run").
Compare runs with and without RANGE_SHADER_UNIFORM_VALUES=1, alternating, several times each.

Materials vary like in create_shader_cache_test.py so the uniform mode shares programs between them.
"""
import bpy
import os
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = os.path.abspath(argv[0] if argv else "shader_fps_test.range")

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.name = "Scene"
game = scene.game_settings
game.show_framerate_profile = False
game.vsync = 'OFF'
game.use_frame_rate = False
game.resolution_x = 1920
game.resolution_y = 1080
scene.world = bpy.data.worlds.new("World")
scene.world.horizon_color = (0.05, 0.05, 0.08)
scene.world.ambient_color = (0.15, 0.15, 0.15)

bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, calc_uvs=True)
base = bpy.context.object.data
bpy.data.objects.remove(bpy.context.object, do_unlink=True)

image = bpy.data.images.new("Checker", 256, 256)
image.generated_type = 'COLOR_GRID'
texture = bpy.data.textures.new("Checker", 'IMAGE')
texture.image = image

DIFFUSE = ['LAMBERT', 'OREN_NAYAR', 'TOON', 'MINNAERT', 'FRESNEL']
SPECULAR = ['COOKTORR', 'PHONG', 'BLINN', 'TOON', 'WARDISO']


def color(i):
    return ((i * 0.37) % 1.0, (i * 0.61) % 1.0, (i * 0.83) % 1.0)


def material(i):
    """Every material has its own values; rows change the shader models so there are several programs."""
    row = (i // 40) % 6
    mat = bpy.data.materials.new("Mat")
    mat.diffuse_color = color(i)
    mat.specular_color = color(i * 7 + 1)
    mat.specular_intensity = 0.2 + 0.004 * (i % 100)
    mat.specular_hardness = 10 + (i % 90)
    mat.diffuse_shader = DIFFUSE[row % len(DIFFUSE)]
    mat.specular_shader = SPECULAR[(row + i) % len(SPECULAR)]
    if row == 5:
        slot = mat.texture_slots.add()
        slot.texture = texture
        slot.texture_coords = 'UV'
        slot.diffuse_color_factor = 0.3 + 0.002 * (i % 300)
    return mat


COLS, ROWS = 40, 20
for i in range(COLS * ROWS):
    me = base.copy()
    me.materials.append(material(i))
    ob = bpy.data.objects.new("Sphere%03d" % i, me)
    scene.objects.link(ob)
    ob.location = ((i % COLS) * 2.1 - COLS * 1.05, (i // COLS) * 2.1 - ROWS * 1.05, 0.0)
    ob.game.physics_type = 'STATIC'


def lamp(name, type_, location, energy, col, rotation=(0, 0, 0)):
    data = bpy.data.lamps.new(name, type_)
    data.energy = energy
    data.color = col
    ob = bpy.data.objects.new(name, data)
    scene.objects.link(ob)
    ob.location = location
    ob.rotation_euler = rotation
    return ob


lamp("Sun", 'SUN', (0, 0, 20), 0.8, (1.0, 0.95, 0.9), (0.6, 0.2, 0.4))
lamp("Hemi", 'HEMI', (0, 0, 10), 0.2, (0.8, 0.8, 1.0))
for k in range(16):
    lamp("Point%d" % k, 'POINT', ((k % 4) * 20 - 30, (k // 4) * 12 - 18, 4), 1.2, color(k * 3 + 2))

cam_data = bpy.data.cameras.new("Camera")
cam_data.lens = 22
cam = bpy.data.objects.new("Camera", cam_data)
scene.objects.link(cam)
cam.location = (0, -30, 22)
cam.rotation_euler = (0.9, 0, 0)
scene.camera = cam

# The camera orbits the grid so every frame draws a different view. Logic runs at a fixed 60 Hz while drawing
# is free, so each logic tick samples the engine's last render frame time; the first ticks are skipped while
# the drivers still settle.
text = bpy.data.texts.new("fps.py")
text.write('''import Range
import math
import os

WARMUP, SAMPLES = 60, 600
g = Range.logic.globalDict
cam = Range.logic.getCurrentController().owner
n = g["frame"] = g.get("frame", 0) + 1
a = n * 0.004
cam.worldPosition = (math.sin(a) * 30.0, -math.cos(a) * 30.0, 22.0)
cam.worldOrientation = (0.9, 0.0, a)
if n > WARMUP:
    g["ms"] = g.get("ms", 0.0) + 1000.0 / max(Range.logic.getAverageFrameRate(), 1e-3)
if n == WARMUP + SAMPLES:
    ms = g["ms"] / SAMPLES
    tag = os.environ.get("RANGE_SHOT_TAG", "run")
    with open(Range.logic.expandPath("//fps_%s.txt" % tag), "a") as f:
        f.write("%.3f ms  %.1f fps\\n" % (ms, 1000.0 / ms))
    Range.logic.endGame()
''')
scene.objects.active = cam
bpy.ops.logic.sensor_add(type='ALWAYS', name="Always", object=cam.name)
bpy.ops.logic.controller_add(type='PYTHON', name="Fps", object=cam.name)
sensor = cam.game.sensors["Always"]
sensor.use_pulse_true_level = True
controller = cam.game.controllers["Fps"]
controller.text = text
sensor.link(controller)

os.makedirs(os.path.dirname(output), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=output, check_existing=False, compress=False)
print("[ShaderFpsTest] wrote", output)
