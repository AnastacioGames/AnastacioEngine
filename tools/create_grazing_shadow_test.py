"""Grazing-angle shadow acne test (slope-scaled shadow bias).

Run with:  RangeEngine -b --python tools/create_grazing_shadow_test.py -- <output.range>
Then:      RangeRuntime <output.range>

A large grey floor and a cube lit by a shadow-casting sun that slowly sweeps from overhead down to
almost parallel with the floor (and back). Before the slope-scaled bias the floor broke into
stripes/columns along the light direction near the grazing end; now it should stay clean while the
cube's shadow stays attached to its base.
"""
import bpy
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = argv[0] if argv else "grazing_shadow_test.range"

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'


def material(name, color):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = color
    mat.specular_intensity = 0.1
    return mat


def link(ob):
    scene.objects.link(ob)
    ob.layers = [i == 0 for i in range(20)]
    return ob


floor_me = bpy.data.meshes.new("Floor")
s = 20.0
floor_me.from_pydata([(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)], [], [(0, 1, 2, 3)])
floor_me.update()
floor_me.materials.append(material("FloorMat", (0.6, 0.6, 0.6)))
link(bpy.data.objects.new("Floor", floor_me))

cube_me = bpy.data.meshes.new("Cube")
v = [(x, y, z) for x in (-1, 1) for y in (-1, 1) for z in (0, 2)]
cube_me.from_pydata(v, [], [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)])
cube_me.update()
cube_me.materials.append(material("CubeMat", (0.8, 0.3, 0.1)))
link(bpy.data.objects.new("Cube", cube_me))

lamp_data = bpy.data.lamps.new("Sun", 'SUN')
lamp_data.use_shadow = True
lamp_data.shadow_frustum_size = 30.0
lamp = link(bpy.data.objects.new("Sun", lamp_data))
lamp.location = (0.0, 0.0, 10.0)
lamp.rotation_euler = (1.45, 0.0, 0.6)

# Sun elevation sweep: 0.3 rad (near overhead) .. 1.55 rad (almost parallel to the floor).
text = bpy.data.texts.new("sweep.py")
text.write(
    "import math\n"
    "from bge import logic\n"
    "own = logic.getCurrentController().owner\n"
    "t = own.get('t', 0.0) + 1.0 / 60.0\n"
    "own['t'] = t\n"
    "x = 0.925 + 0.625 * math.sin(t * 0.4 - math.pi / 2)\n"
    "own.worldOrientation = __import__('mathutils').Euler((x, 0.0, 0.6)).to_matrix()\n"
)
bpy.context.scene.objects.active = lamp
bpy.ops.logic.sensor_add(type='ALWAYS', object=lamp.name)
bpy.ops.logic.controller_add(type='PYTHON', object=lamp.name)
sens = lamp.game.sensors[-1]
sens.use_pulse_true_level = True
cont = lamp.game.controllers[-1]
cont.text = text
sens.link(cont)

cam = link(bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera")))
cam.location = (-9.0, -14.0, 6.0)
cam.rotation_euler = (1.25, 0.0, -0.55)
scene.camera = cam

scene.layers = [i == 0 for i in range(20)]
bpy.ops.wm.save_as_mainfile(filepath=output)
print("GRAZING_SHADOW_TEST saved", output)
