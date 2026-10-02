"""Sky Texture Hosek / Wilkie test scene (Game PBR, Shading Nodes).

Run with:  RangeEngine -b --python tools/create_sky_hosek_test.py -- <output.range>
World: Sky Texture Hosek / Wilkie, low sun ahead and to the right (turbidity 3, ground albedo 0.3).
The sky should be blue overhead with a bright warm glow around the sun near the horizon, like a Cycles
render of the same World. Spheres: mirror (Glossy 0), white Diffuse, Principled Roughness 0.4.
To compare with Preetham, switch the Sky Texture node to Preetham in the editor and press P again.
"""
import bpy
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = argv[0] if argv else "sky_hosek_test.range"

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.use_shading_nodes = True
scene.view_settings.view_transform = 'Filmic'

world = bpy.data.worlds.new("Hosek World")
world.use_nodes = True
wt = world.node_tree
wt.nodes.clear()
sky = wt.nodes.new("ShaderNodeTexSky")
sky.sky_type = 'HOSEK_WILKIE'
sky.sun_direction = (0.5, 0.85, 0.15)
sky.turbidity = 3.0
sky.ground_albedo = 0.3
bg = wt.nodes.new("ShaderNodeBackground")
wout = wt.nodes.new("ShaderNodeOutputWorld")
wt.links.new(sky.outputs["Color"], bg.inputs["Color"])
wt.links.new(bg.outputs[0], wout.inputs["Surface"])
scene.world = world


def mat(name, kind, color, **inputs):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    t = m.node_tree
    t.nodes.clear()
    out = t.nodes.new("ShaderNodeOutputMaterial")
    n = t.nodes.new(kind)
    n.inputs["Base Color" if "Base Color" in n.inputs else "Color"].default_value = color
    for k, v in inputs.items():
        n.inputs[k].default_value = v
    t.links.new(n.outputs[0], out.inputs["Surface"])
    return m


specs = [
    ("Mirror", "ShaderNodeBsdfGlossy", (1, 1, 1, 1), dict(Roughness=0.0)),
    ("Diffuse", "ShaderNodeBsdfDiffuse", (0.8, 0.8, 0.8, 1), {}),
    ("Principled", "ShaderNodeBsdfPrincipled", (0.8, 0.3, 0.2, 1), dict(Roughness=0.4)),
]
for i, (name, kind, color, inputs) in enumerate(specs):
    bpy.ops.mesh.primitive_uv_sphere_add(location=((i - 1) * 2.6, 0, 1), segments=48, ring_count=24)
    bpy.ops.object.shade_smooth()
    bpy.context.object.data.materials.append(mat(name + "Mat", kind, color, **inputs))

bpy.ops.object.camera_add(location=(0, -9, 2.0), rotation=(1.45, 0, 0))
scene.camera = bpy.context.object

bpy.ops.wm.save_as_mainfile(filepath=output)
print("Saved", output)
