"""Hair Info test scene (Game PBR, Shading Nodes).

Run with:  RangeEngine -b --python tools/create_hair_info_test.py -- <output.range>
One sphere per Hair Info output (Is Strand, Intercept, Thickness, Tangent Normal, Random). Each output drives
the Fac of a Mix between green (0) and red (1), into an Emission: on a mesh every output is zero, so all
spheres must be green, and the console must not warn "nodes not supported".
"""
import bpy
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = argv[0] if argv else "hair_info_test.range"

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.use_shading_nodes = True

for i, socket in enumerate(["Is Strand", "Intercept", "Thickness", "Tangent Normal", "Random"]):
    m = bpy.data.materials.new("HairInfo " + socket)
    m.use_nodes = True
    t = m.node_tree
    t.nodes.clear()
    out = t.nodes.new("ShaderNodeOutputMaterial")
    info = t.nodes.new("ShaderNodeHairInfo")
    mix = t.nodes.new("ShaderNodeMixRGB")
    mix.inputs["Color1"].default_value = (0.0, 1.0, 0.0, 1.0)
    mix.inputs["Color2"].default_value = (1.0, 0.0, 0.0, 1.0)
    em = t.nodes.new("ShaderNodeEmission")
    t.links.new(info.outputs[socket], mix.inputs["Fac"])
    t.links.new(mix.outputs[0], em.inputs["Color"])
    t.links.new(em.outputs[0], out.inputs["Surface"])
    bpy.ops.mesh.primitive_uv_sphere_add(location=((i - 2) * 2.4, 0, 1), size=0.9)
    bpy.context.object.data.materials.append(m)

bpy.ops.object.camera_add(location=(0, -14, 1), rotation=(1.5708, 0, 0))
scene.camera = bpy.context.object

bpy.ops.wm.save_as_mainfile(filepath=output)
print("Saved", output)
