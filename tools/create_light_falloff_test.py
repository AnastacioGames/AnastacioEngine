"""Light Falloff / Light Path Ray Length test scene (Game PBR, Shading Nodes).

Run with:  RangeEngine -b --python tools/create_light_falloff_test.py -- <output.range>
Two rows of spheres receding from the camera (distance 6 to 30).
Left row: Emission strength = Light Falloff Linear (Strength 0.05): farther spheres are brighter.
Right row: Emission color = Light Path Ray Length / 30 (gray ramp): near dark, far white.
"""
import bpy
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = argv[0] if argv else "light_falloff_test.range"

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.use_shading_nodes = True


def falloff_mat():
    mat = bpy.data.materials.new("FalloffMat")
    mat.use_nodes = True
    t = mat.node_tree
    t.nodes.clear()
    out = t.nodes.new("ShaderNodeOutputMaterial")
    fo = t.nodes.new("ShaderNodeLightFalloff")
    fo.inputs["Strength"].default_value = 0.05
    em = t.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (1.0, 0.6, 0.2, 1.0)
    t.links.new(fo.outputs["Linear"], em.inputs["Strength"])
    t.links.new(em.outputs[0], out.inputs["Surface"])
    return mat


def raylength_mat():
    mat = bpy.data.materials.new("RayLengthMat")
    mat.use_nodes = True
    t = mat.node_tree
    t.nodes.clear()
    out = t.nodes.new("ShaderNodeOutputMaterial")
    lp = t.nodes.new("ShaderNodeLightPath")
    div = t.nodes.new("ShaderNodeMath")
    div.operation = 'DIVIDE'
    div.inputs[1].default_value = 30.0
    em = t.nodes.new("ShaderNodeEmission")
    t.links.new(lp.outputs["Ray Length"], div.inputs[0])
    t.links.new(div.outputs[0], em.inputs["Color"])
    t.links.new(em.outputs[0], out.inputs["Surface"])
    return mat


fm, rm = falloff_mat(), raylength_mat()
for i in range(5):
    y = i * 6.0
    for x, m in ((-2.0, fm), (2.0, rm)):
        bpy.ops.mesh.primitive_uv_sphere_add(location=(x, y, 1), segments=32, ring_count=16)
        bpy.ops.object.shade_smooth()
        bpy.context.object.data.materials.append(m)

bpy.ops.object.camera_add(location=(0, -6, 2), rotation=(1.48, 0, 0))
scene.camera = bpy.context.object

bpy.ops.wm.save_as_mainfile(filepath=output)
print("Saved", output)
