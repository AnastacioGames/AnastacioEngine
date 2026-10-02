"""Glass screen-space refraction test scene (Game PBR, Shading Nodes).

Run with:  RangeEngine -b --python tools/create_glass_refraction_test.py -- <output.range>
A colored checker wall and floor behind a row of spheres. With Blend Mode Alpha Blend the Glass and
Refraction nodes refract the scene behind them (lens-like, upside down through the sphere center):
Glass at Roughness 0, 0.3 and 0.7 (blurrier), a tinted Refraction sphere, and on the far right a
Glass with solid blend for comparison (refracts only the World, as before).
"""
import bpy
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = argv[0] if argv else "glass_refraction_test.range"

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.resolution_x = 1280
scene.game_settings.resolution_y = 720
scene.game_settings.use_shading_nodes = True

world = bpy.data.worlds.new("Glass World")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.25, 0.3, 0.4, 1.0)
scene.world = world


def checker_material(name, c1, c2, scale):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    tree = mat.node_tree
    tree.nodes.clear()
    out = tree.nodes.new("ShaderNodeOutputMaterial")
    em = tree.nodes.new("ShaderNodeEmission")
    chk = tree.nodes.new("ShaderNodeTexChecker")
    chk.inputs["Scale"].default_value = scale
    chk.inputs["Color1"].default_value = c1
    chk.inputs["Color2"].default_value = c2
    coord = tree.nodes.new("ShaderNodeTexCoord")
    # offset so no face lies exactly on a checker boundary (flat faces at object coord +-1)
    add = tree.nodes.new("ShaderNodeVectorMath")
    add.operation = 'ADD'
    add.inputs[1].default_value = (0.13, 0.13, 0.13)
    tree.links.new(coord.outputs["Object"], add.inputs[0])
    tree.links.new(add.outputs["Vector"], chk.inputs["Vector"])
    tree.links.new(chk.outputs["Color"], em.inputs["Color"])
    tree.links.new(em.outputs[0], out.inputs["Surface"])
    return mat


def bsdf_material(name, kind, color, alpha_blend, **inputs):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    tree = mat.node_tree
    tree.nodes.clear()
    out = tree.nodes.new("ShaderNodeOutputMaterial")
    n = tree.nodes.new(kind)
    n.inputs["Color"].default_value = color
    for k, v in inputs.items():
        n.inputs[k].default_value = v
    tree.links.new(n.outputs[0], out.inputs["Surface"])
    if alpha_blend:
        mat.game_settings.alpha_blend = 'ALPHA'
    return mat


def box(name, loc, scale, mat):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    obj.data.materials.append(mat)
    return obj


box("Wall", (0, 4, 2.5), (9, 0.1, 3),
    checker_material("WallChecker", (0.9, 0.2, 0.1, 1.0), (0.1, 0.3, 0.9, 1.0), 2.0))
box("Floor", (0, 0, -0.1), (9, 5, 0.1),
    checker_material("FloorChecker", (0.9, 0.9, 0.9, 1.0), (0.1, 0.1, 0.1, 1.0), 1.5))
bpy.ops.mesh.primitive_cylinder_add(location=(0, 2.0, 0.8), radius=0.15, depth=1.6)
bpy.context.object.data.materials.append(
    checker_material("Pole", (1.0, 0.9, 0.1, 1.0), (1.0, 0.9, 0.1, 1.0), 1.0))

white = (1.0, 1.0, 1.0, 1.0)
spheres = [
    ("GlassR0", bsdf_material("Glass r0", "ShaderNodeBsdfGlass", white, True, Roughness=0.0, IOR=1.45)),
    ("GlassR03", bsdf_material("Glass r0.3", "ShaderNodeBsdfGlass", white, True, Roughness=0.3, IOR=1.45)),
    ("GlassR07", bsdf_material("Glass r0.7", "ShaderNodeBsdfGlass", white, True, Roughness=0.7, IOR=1.45)),
    ("RefrGreen", bsdf_material("Refraction green", "ShaderNodeBsdfRefraction", (0.4, 1.0, 0.5, 1.0), True,
                                Roughness=0.0, IOR=1.33)),
    ("GlassSolid", bsdf_material("Glass solid", "ShaderNodeBsdfGlass", white, False, Roughness=0.0, IOR=1.45)),
]
for i, (name, mat) in enumerate(spheres):
    bpy.ops.mesh.primitive_uv_sphere_add(location=(-6 + i * 3, 0.5, 1.2), size=1.1, segments=48, ring_count=24)
    obj = bpy.context.object
    obj.name = name
    bpy.ops.object.shade_smooth()
    obj.data.materials.append(mat)

bpy.ops.object.lamp_add(type='SUN', location=(0, -4, 8), rotation=(0.6, 0, 0.3))

bpy.ops.object.camera_add(location=(0, -9, 2.2), rotation=(1.48, 0, 0))
cam = bpy.context.object
cam.data.lens = 22
scene.camera = cam

bpy.ops.wm.save_as_mainfile(filepath=output)
print("Saved", output)
