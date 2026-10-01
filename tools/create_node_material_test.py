"""Node material test scene (Phase 1 GLSL fixes).

Run with:  RangeEngine -b --python tools/create_node_material_test.py -- <output.range>
Spheres, left to right:
  1 Glossy roughness 0 (must not turn black)
  2 Glossy roughness 0.5
  3 Diffuse (shadow side follows the World color)
  4 Diffuse with color alpha 0.4
  5 Mix Shader Diffuse + Transparent, factor 0.5 (must be see-through)
A striped wall behind the spheres helps to see the transparency.
In game: 1 grey world, 2 red world, 3 blue world, 4 black world.
Switch the render engine (Cycles / Blender Render / Game) to check the node badges.
"""
import bpy
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = argv[0] if argv else "node_material_test.range"

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.resolution_x = 960
scene.game_settings.resolution_y = 540
scene.game_settings.use_shading_nodes = True  # Game uses the BSDF nodes (PBR)
world = bpy.data.worlds.new("NodeTest World")
world.horizon_color = (0.5, 0.5, 0.5)
scene.world = world


def node_material(name, build):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.use_constant_world = False  # World color can change in game (keys 1-4)
    tree = mat.node_tree
    tree.nodes.clear()
    out = tree.nodes.new("ShaderNodeOutputMaterial")
    out.location = (400, 0)
    shader = build(tree)
    tree.links.new(shader.outputs[0], out.inputs["Surface"])
    return mat


def glossy(roughness):
    def build(tree):
        n = tree.nodes.new("ShaderNodeBsdfGlossy")
        n.inputs["Color"].default_value = (0.8, 0.6, 0.2, 1.0)
        n.inputs["Roughness"].default_value = roughness
        return n
    return build


def diffuse(alpha):
    def build(tree):
        n = tree.nodes.new("ShaderNodeBsdfDiffuse")
        n.inputs["Color"].default_value = (0.2, 0.7, 0.3, alpha)
        return n
    return build


def mix_transparent(tree):
    d = tree.nodes.new("ShaderNodeBsdfDiffuse")
    d.location = (-300, 100)
    d.inputs["Color"].default_value = (0.8, 0.2, 0.2, 1.0)
    t = tree.nodes.new("ShaderNodeBsdfTransparent")
    t.location = (-300, -100)
    m = tree.nodes.new("ShaderNodeMixShader")
    m.inputs["Fac"].default_value = 0.5
    tree.links.new(d.outputs[0], m.inputs[1])
    tree.links.new(t.outputs[0], m.inputs[2])
    return m


specs = [
    ("GlossyRough0", glossy(0.0)),
    ("GlossyRough05", glossy(0.5)),
    ("Diffuse", diffuse(1.0)),
    ("DiffuseAlpha", diffuse(0.4)),
    ("MixTransparent", mix_transparent),
]
for i, (name, build) in enumerate(specs):
    bpy.ops.mesh.primitive_uv_sphere_add(location=((i - 2) * 2.5, 0, 1), segments=48, ring_count=24)
    obj = bpy.context.object
    obj.name = name
    bpy.ops.object.shade_smooth()
    mat = node_material(name + "Mat", build)
    if name in ("DiffuseAlpha", "MixTransparent"):
        mat.game_settings.alpha_blend = 'ALPHA'
    obj.data.materials.append(mat)

# Striped wall behind the spheres.
for i in range(10):
    bpy.ops.mesh.primitive_cube_add(location=((i - 4.5) * 1.4, 4, 1.5))
    bar = bpy.context.object
    bar.scale = (0.35, 0.2, 2.5)
    mat = bpy.data.materials.new("Bar%d" % i)
    mat.diffuse_color = (1, 1, 1) if i % 2 else (0.05, 0.05, 0.05)
    bar.data.materials.append(mat)

bpy.ops.mesh.primitive_plane_add(location=(0, 0, 0))
ground = bpy.context.object
ground.scale = (15, 15, 1)
gmat = bpy.data.materials.new("GroundMat")
gmat.diffuse_color = (0.35, 0.35, 0.35)
ground.data.materials.append(gmat)

bpy.ops.object.lamp_add(type='SUN', location=(4, -6, 8))
bpy.context.object.rotation_euler = (0.7, 0.3, 0.6)

bpy.ops.object.camera_add(location=(0, -11, 3.5), rotation=(1.35, 0, 0))
cam = bpy.context.object
scene.camera = cam

# Keys 1-4 change the World color in game.
text = bpy.data.texts.new("world_color.py")
text.write('''import bge
COLORS = {bge.events.ONEKEY: (0.5, 0.5, 0.5, 1.0), bge.events.TWOKEY: (0.8, 0.1, 0.1, 1.0),
          bge.events.THREEKEY: (0.1, 0.2, 0.9, 1.0), bge.events.FOURKEY: (0.0, 0.0, 0.0, 1.0)}
kb = bge.logic.keyboard
for key, color in COLORS.items():
    if kb.events[key] == bge.logic.KX_INPUT_JUST_ACTIVATED:
        bge.logic.getCurrentScene().world.horizonColor = color
        print("World color", color)
''')
bpy.context.scene.objects.active = cam
bpy.ops.logic.sensor_add(type='KEYBOARD', object=cam.name)
sens = cam.game.sensors[-1]
sens.use_all_keys = True
bpy.ops.logic.controller_add(type='PYTHON', object=cam.name)
cont = cam.game.controllers[-1]
cont.text = text
sens.link(cont)

bpy.ops.wm.save_as_mainfile(filepath=output)
print("Saved", output)
