"""IES Texture test scene (Game PBR, Shading Nodes): IES profiles on lamps.

Run with:  RangeEngine -b --python tools/create_ies_test.py -- <output.range>
Three Point lamps over a floor with a back wall, same color and Energy. From left:
- IES "cone": symmetric downlight, a round spot on the floor with a sharp edge (~35 degrees), wall dark;
- no IES: plain Point lamp, soft light everywhere (reference);
- IES "asymmetric": light only towards one side of the lamp (horizontal angle 0 = lamp -Y, towards the camera),
  the floor in front of it bright and the wall behind it dark.
The profiles are internal Text datablocks (photometric type C).
"""
import bpy
import math
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = argv[0] if argv else "ies_test.range"

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.use_shading_nodes = True

world = bpy.data.worlds.new("IES World")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.01, 0.01, 0.012, 1.0)
scene.world = world


def ies_text(name, v_angles, h_angles, intensity):
    """intensity(h, v) in candela; writes an IES LM-63 type C file into a Text datablock."""
    lines = ["IESNA:LM-63-2002", "[TEST] " + name, "TILT=NONE",
             "1 1000 1 %d %d 1 2 0 0 0" % (len(v_angles), len(h_angles)), "1 1 100",
             " ".join("%g" % v for v in v_angles), " ".join("%g" % h for h in h_angles)]
    for h in h_angles:
        lines.append(" ".join("%.1f" % intensity(h, v) for v in v_angles))
    t = bpy.data.texts.new(name + ".ies")
    t.write("\n".join(lines) + "\n")
    return t


def cone(h, v):
    return 1000.0 * (1.0 if v <= 25 else max(0.0, 1.0 - (v - 25) / 10.0))


def asymmetric(h, v):
    # strong at horizontal 0, none from 90 to 270; wide vertically
    side = max(0.0, math.cos(math.radians(h)))
    return 1000.0 * side * (1.0 if v <= 80 else 0.0)


texts = [
    ies_text("cone", list(range(0, 91, 5)), [0], cone),
    None,
    ies_text("asymmetric", list(range(0, 91, 10)), [0, 45, 90, 135, 180, 225, 270, 315, 360], asymmetric),
]

mat = bpy.data.materials.new("Floor")
mat.use_nodes = True
mat.node_tree.nodes["Diffuse BSDF"].inputs["Color"].default_value = (0.8, 0.8, 0.8, 1.0)

bpy.ops.mesh.primitive_plane_add(location=(0, 0, 0), radius=10)
bpy.context.object.data.materials.append(mat)
bpy.ops.mesh.primitive_plane_add(location=(0, 4, 5), radius=10, rotation=(math.pi / 2, 0, 0))
bpy.context.object.data.materials.append(mat)

for i, text in enumerate(texts):
    bpy.ops.object.lamp_add(type='POINT', location=((i - 1) * 6, 0, 3))
    lamp = bpy.context.object.data
    lamp.energy = 0.6
    lamp.distance = 8.0
    lamp.use_nodes = True
    if text:
        t = lamp.node_tree
        ies = t.nodes.new("ShaderNodeTexIES")
        ies.mode = 'INTERNAL'
        ies.ies = text
        t.links.new(ies.outputs["Fac"], t.nodes["Emission"].inputs["Strength"])

bpy.ops.object.camera_add(location=(0, -16, 9), rotation=(1.1, 0, 0))
scene.camera = bpy.context.object

bpy.ops.wm.save_as_mainfile(filepath=output)
print("Saved", output)
