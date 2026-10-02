"""Hair BSDF test scene (Game PBR, Shading Nodes).

Run with:  RangeEngine -b --python tools/create_hair_bsdf_test.py -- <output.range>
Spheres with the Hair BSDF; with the Tangent unlinked the strands run around the object Z axis, so the
highlight is a vertical band (across the strands) that moves with RoughnessU/Offset. From left: Reflection RoughnessU 0.1,
Reflection RoughnessU 0.3, Reflection Offset 0.2 (band shifted), Transmission (lit by the back lamp: a glow
on the rim). A sun lights from the front-left and a point lamp sits behind the spheres.
"""
import bpy
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = argv[0] if argv else "hair_bsdf_test.range"

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.use_shading_nodes = True

world = bpy.data.worlds.new("Hair World")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.05, 0.05, 0.06, 1.0)
scene.world = world


def hair(name, component, color, **inputs):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    t = m.node_tree
    t.nodes.clear()
    out = t.nodes.new("ShaderNodeOutputMaterial")
    n = t.nodes.new("ShaderNodeBsdfHair")
    n.component = component
    n.inputs["Color"].default_value = color
    for k, v in inputs.items():
        n.inputs[k].default_value = v
    t.links.new(n.outputs[0], out.inputs["Surface"])
    return m


brown = (0.6, 0.35, 0.15, 1.0)
specs = [
    hair("HairR01", 'Reflection', brown, RoughnessU=0.1, RoughnessV=1.0),
    hair("HairR03", 'Reflection', brown, RoughnessU=0.3, RoughnessV=1.0),
    hair("HairROff", 'Reflection', brown, RoughnessU=0.1, RoughnessV=1.0, Offset=0.2),
    hair("HairT", 'Transmission', (1.0, 0.8, 0.5, 1.0), RoughnessU=0.2, RoughnessV=0.4),
]
for i, m in enumerate(specs):
    bpy.ops.mesh.primitive_uv_sphere_add(location=((i - 1.5) * 2.6, 0, 1), segments=48, ring_count=24)
    bpy.ops.object.shade_smooth()
    bpy.context.object.data.materials.append(m)

bpy.ops.object.lamp_add(type='SUN', location=(-4, -6, 6), rotation=(0.9, 0, -0.6))
bpy.ops.object.lamp_add(type='POINT', location=(3.9, 2.5, 1.3))
bpy.context.object.data.energy = 6.0
bpy.context.object.data.distance = 6.0

bpy.ops.object.camera_add(location=(0, -14, 1.6), rotation=(1.53, 0, 0))
scene.camera = bpy.context.object

bpy.ops.wm.save_as_mainfile(filepath=output)
print("Saved", output)
