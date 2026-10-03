"""Visual check for the GLSL shader cache: a wide shot of many spheres with varied materials.

Run with:  RangeEngine -b --python tools/create_shader_cache_test.py -- <output.range>
Play it with RangeRuntime: after a few frames it saves <output>_<tag>.png next to the file and ends the
game. The tag comes from the RANGE_SHOT_TAG environment variable (default "shot"). Take one shot with
RANGE_NO_SHADER_CACHE=1 (every material compiled alone) and one without, then compare the images with
tools/compare_images.py; they must match.

Materials cover what can share a program by mistake: same structure with different colors, exact
duplicates (Mat, Mat.001), diffuse/specular shader models, shadeless, emit, alpha, ramps and one texture.
"""
import bpy
import os
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = os.path.abspath(argv[0] if argv else "shader_cache_test.range")

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.name = "Scene"
scene.game_settings.show_framerate_profile = False
scene.world = bpy.data.worlds.new("World")
scene.world.horizon_color = (0.05, 0.05, 0.08)
scene.world.ambient_color = (0.15, 0.15, 0.15)

bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, calc_uvs=True)
base = bpy.context.object.data
bpy.data.objects.remove(bpy.context.object, do_unlink=True)

image = bpy.data.images.new("Checker", 64, 64)
image.generated_type = 'COLOR_GRID'
texture = bpy.data.textures.new("Checker", 'IMAGE')
texture.image = image

DIFFUSE = ['LAMBERT', 'OREN_NAYAR', 'TOON', 'MINNAERT', 'FRESNEL']
SPECULAR = ['COOKTORR', 'PHONG', 'BLINN', 'TOON', 'WARDISO']


def color(i):
    return ((i * 0.37) % 1.0, (i * 0.61) % 1.0, (i * 0.83) % 1.0)


def material(i):
    """Row by row variety; every 20 materials the values repeat so the cache has real duplicates."""
    k = i % 20
    row = (i // 20) % 8
    mat = bpy.data.materials.new("Mat")
    mat.diffuse_color = color(k + row * 3)
    mat.specular_color = color(k * 7 + 1)
    mat.specular_intensity = 0.2 + 0.04 * (k % 10)
    mat.specular_hardness = 10 + 20 * (k % 5)
    mat.diffuse_shader = DIFFUSE[row % len(DIFFUSE)]
    mat.specular_shader = SPECULAR[(row + k) % len(SPECULAR)]
    if row == 5:
        mat.use_shadeless = k % 2 == 0
        mat.emit = 0.0 if k % 2 == 0 else 0.6
    if row == 6:
        mat.use_transparency = True
        mat.alpha = 0.3 + 0.03 * k
        mat.game_settings.alpha_blend = 'ALPHA'
    if row == 7:
        if k % 2 == 0:
            mat.use_diffuse_ramp = True
            mat.diffuse_ramp.elements[0].color = (*color(k), 1.0)
            mat.diffuse_ramp.elements[1].color = (*color(k + 5), 1.0)
        else:
            slot = mat.texture_slots.add()
            slot.texture = texture
            slot.texture_coords = 'UV'
            slot.diffuse_color_factor = 0.3 + 0.03 * k
    return mat


COLS, ROWS = 20, 10
for i in range(COLS * ROWS):
    me = base.copy()
    me.materials.append(material(i))
    ob = bpy.data.objects.new("Sphere%03d" % i, me)
    scene.objects.link(ob)
    ob.location = ((i % COLS) * 2.2 - COLS * 1.1, (i // COLS) * 2.2, 0.0)
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
lamp("PointWarm", 'POINT', (-12, 5, 4), 1.5, (1.0, 0.6, 0.3))
lamp("PointCold", 'POINT', (12, 15, 4), 1.5, (0.3, 0.6, 1.0))
lamp("Hemi", 'HEMI', (0, 10, 10), 0.2, (0.8, 0.8, 1.0))

cam_data = bpy.data.cameras.new("Camera")
cam_data.lens = 18  # Wide angle: the whole grid in one shot.
cam = bpy.data.objects.new("Camera", cam_data)
scene.objects.link(cam)
cam.location = (0, -16, 18)
cam.rotation_euler = (0.82, 0, 0)
scene.camera = cam

text = bpy.data.texts.new("shot.py")
text.write('''import Range
import os

g = Range.logic.globalDict
g["frame"] = g.get("frame", 0) + 1
if g["frame"] == 30:
    tag = os.environ.get("RANGE_SHOT_TAG", "shot")
    path = Range.logic.expandPath("//shader_cache_%s.png" % tag)
    Range.render.makeScreenshot(path)
    print("[ShaderCacheTest] screenshot", path)
elif g["frame"] == 40:
    Range.logic.endGame()
''')
scene.objects.active = cam
bpy.ops.logic.sensor_add(type='ALWAYS', name="Always", object=cam.name)
bpy.ops.logic.controller_add(type='PYTHON', name="Shot", object=cam.name)
sensor = cam.game.sensors["Always"]
sensor.use_pulse_true_level = True
controller = cam.game.controllers["Shot"]
controller.text = text
sensor.link(controller)

os.makedirs(os.path.dirname(output), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=output, check_existing=False, compress=False)
print("[ShaderCacheTest] wrote", output)
