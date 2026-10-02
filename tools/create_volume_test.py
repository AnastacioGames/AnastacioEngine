"""Volume nodes test scene (Game PBR, Shading Nodes): Volume Scatter, Volume Absorption, Principled Volume.

Run with:  RangeEngine -b --python tools/create_volume_test.py -- <output.range>
Three default cubes (volume = the object's local box) with Blend Mode Alpha Blend, in front of a
checker wall, lit by a Point lamp. From left:
- Volume Scatter (white, density 0.6): grey fog, brighter towards the lamp; a red sphere inside
  shows through less the deeper it is (the fog stops at the opaque scene);
- Volume Absorption (orange, density 1.2): the checker behind tinted orange (blue absorbed), no light of its own;
- Principled Volume (dark smoke, blackbody 2500 K, density 1): an orange glow from inside.
The middle cube is scaled (1.5 x 1 x 1): the thickness follows the object's scale.
"""
import bpy
import math
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = argv[0] if argv else "volume_test.range"

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.use_shading_nodes = True

world = bpy.data.worlds.new("Volume World")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.03, 0.03, 0.04, 1.0)
scene.world = world


def surface_material(name, color, checker=False):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    t = mat.node_tree
    bsdf = t.nodes["Diffuse BSDF"]
    bsdf.inputs["Color"].default_value = color
    if checker:
        ch = t.nodes.new("ShaderNodeTexChecker")
        ch.inputs["Scale"].default_value = 12.0
        ch.inputs["Color1"].default_value = (0.9, 0.9, 0.9, 1.0)
        ch.inputs["Color2"].default_value = (0.05, 0.05, 0.05, 1.0)
        t.links.new(ch.outputs["Color"], bsdf.inputs["Color"])
    return mat


def volume_material(name, kind, **inputs):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.game_settings.alpha_blend = 'ALPHA'
    t = mat.node_tree
    out = t.nodes["Material Output"]
    t.nodes.remove(t.nodes["Diffuse BSDF"])
    vol = t.nodes.new(kind)
    for key, value in inputs.items():
        vol.inputs[key].default_value = value
    t.links.new(vol.outputs["Volume"], out.inputs["Volume"])
    return mat


def add(op, mat, **kw):
    op(**kw)
    ob = bpy.context.object
    ob.data.materials.append(mat)
    return ob


add(bpy.ops.mesh.primitive_plane_add, surface_material("Floor", (0.5, 0.5, 0.5, 1.0)), radius=12, location=(0, 0, 0))
add(bpy.ops.mesh.primitive_plane_add, surface_material("Wall", (1, 1, 1, 1), checker=True),
    radius=12, location=(0, 4, 6), rotation=(math.pi / 2, 0, 0))
add(bpy.ops.mesh.primitive_uv_sphere_add, surface_material("Red", (0.8, 0.05, 0.05, 1.0)),
    size=0.5, location=(-4.5, 0.4, 1.0))

add(bpy.ops.mesh.primitive_cube_add, volume_material(
    "Scatter", "ShaderNodeVolumeScatter", Color=(1, 1, 1, 1), Density=0.6), location=(-4.5, 0, 1.2))
cube = add(bpy.ops.mesh.primitive_cube_add, volume_material(
    "Absorption", "ShaderNodeVolumeAbsorption", Color=(1.0, 0.5, 0.1, 1), Density=1.2), location=(0, 0, 1.2))
cube.scale = (1.5, 1.0, 1.0)
add(bpy.ops.mesh.primitive_cube_add, volume_material(
    "Principled", "ShaderNodeVolumePrincipled", Color=(0.05, 0.05, 0.05, 1), Density=1.0, **{"Blackbody Intensity": 1.0,
                                                               "Temperature": 2500.0}), location=(4.5, 0, 1.2))

bpy.ops.object.lamp_add(type='POINT', location=(-2, -3, 5))
bpy.context.object.data.energy = 1.5
bpy.context.object.data.distance = 15.0

bpy.ops.object.camera_add(location=(0, -14, 5), rotation=(1.32, 0, 0))
scene.camera = bpy.context.object

bpy.ops.wm.save_as_mainfile(filepath=output)
print("Saved", output)
