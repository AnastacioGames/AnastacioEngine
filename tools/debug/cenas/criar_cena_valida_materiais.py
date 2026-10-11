"""Cena de validacao visual - MATERIAIS / NOS (varios itens de uma vez).

Rodar:
  AnastacioEngine -b --factory-startup --python tools/debug/cenas/criar_cena_valida_materiais.py -- <saida.range>

Esferas, da esquerda p/ direita, cada uma valida um item pendente:
  1 Principled roughness 0   -> NAO pode aparecer ponto branco estourado (piso 0.15, commit f4705337)
  2 Principled roughness 0.3 -> referencia de brilho normal
  3 Glossy roughness 0       -> NAO pode ficar preta (fix de nos)
  4 Emission (forca 2)       -> deve brilhar constante, sem receber sombra
  5 Toon BSDF                -> degrade em faixas (size/smooth), nao liso
  6 Mix Diffuse+Transparent  -> deve dar pra ver a parede listrada atras
A parede listrada atras ajuda a enxergar transparencia e o especular.
"""
import bpy
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = argv[0] if argv else "valida_materiais.range"

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.resolution_x = 1280
scene.game_settings.resolution_y = 540
scene.game_settings.use_shading_nodes = True

world = bpy.data.worlds.new("ValidaMat World")
world.horizon_color = (0.45, 0.5, 0.6)
world.mist_settings.use_mist = False
scene.world = world


def node_material(name, build, alpha_blend=None):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    tree = mat.node_tree
    tree.nodes.clear()
    out = tree.nodes.new("ShaderNodeOutputMaterial")
    out.location = (400, 0)
    shader = build(tree)
    tree.links.new(shader.outputs[0], out.inputs["Surface"])
    if alpha_blend:
        mat.game_settings.alpha_blend = alpha_blend
    return mat


def principled(rough):
    def build(tree):
        n = tree.nodes.new("ShaderNodeBsdfPrincipled")
        n.inputs["Base Color"].default_value = (0.8, 0.1, 0.1, 1.0)
        n.inputs["Roughness"].default_value = rough
        n.inputs["Metallic"].default_value = 0.0
        return n
    return build


def glossy0(tree):
    n = tree.nodes.new("ShaderNodeBsdfGlossy")
    n.inputs["Color"].default_value = (0.85, 0.7, 0.3, 1.0)
    n.inputs["Roughness"].default_value = 0.0
    return n


def emission(tree):
    n = tree.nodes.new("ShaderNodeEmission")
    n.inputs["Color"].default_value = (0.1, 0.9, 0.3, 1.0)
    n.inputs["Strength"].default_value = 2.0
    return n


def toon(tree):
    n = tree.nodes.new("ShaderNodeBsdfToon")
    n.inputs["Color"].default_value = (0.2, 0.5, 0.95, 1.0)
    n.inputs["Size"].default_value = 0.5
    n.inputs["Smooth"].default_value = 0.0
    return n


def mix_transparent(tree):
    d = tree.nodes.new("ShaderNodeBsdfDiffuse")
    d.location = (-300, 100)
    d.inputs["Color"].default_value = (0.9, 0.5, 0.1, 1.0)
    t = tree.nodes.new("ShaderNodeBsdfTransparent")
    t.location = (-300, -100)
    m = tree.nodes.new("ShaderNodeMixShader")
    m.inputs["Fac"].default_value = 0.5
    tree.links.new(d.outputs[0], m.inputs[1])
    tree.links.new(t.outputs[0], m.inputs[2])
    return m


specs = [
    ("PrincipledRough0", principled(0.0), None),
    ("PrincipledRough03", principled(0.3), None),
    ("GlossyRough0", glossy0, None),
    ("Emission", emission, None),
    ("Toon", toon, None),
    ("MixTransparent", mix_transparent, 'ALPHA'),
]
for i, (name, build, ab) in enumerate(specs):
    bpy.ops.mesh.primitive_uv_sphere_add(location=((i - 2.5) * 2.4, 0, 1.2), segments=48, ring_count=24)
    obj = bpy.context.object
    obj.name = name
    bpy.ops.object.shade_smooth()
    obj.data.materials.append(node_material(name + "Mat", build, ab))

# Parede listrada atras das esferas.
for i in range(14):
    bpy.ops.mesh.primitive_cube_add(location=((i - 6.5) * 1.1, 3.2, 1.8))
    bar = bpy.context.object
    bar.scale = (0.28, 0.2, 3.0)
    mat = bpy.data.materials.new("Bar%d" % i)
    mat.diffuse_color = (0.95, 0.95, 0.95) if i % 2 else (0.05, 0.05, 0.05)
    bar.data.materials.append(mat)

bpy.ops.mesh.primitive_plane_add(location=(0, 0, 0))
ground = bpy.context.object
ground.scale = (20, 20, 1)
gmat = bpy.data.materials.new("GroundMat")
gmat.diffuse_color = (0.3, 0.32, 0.35)
ground.data.materials.append(gmat)

bpy.ops.object.lamp_add(type='SUN', location=(5, -7, 9))
sun = bpy.context.object
sun.rotation_euler = (0.7, 0.25, 0.6)

# Camera mirando o centro das esferas.
from mathutils import Vector
cam_loc = Vector((0.0, -12.0, 3.6))
alvo = Vector((0.0, 0.0, 1.2))
bpy.ops.object.camera_add(location=cam_loc)
cam = bpy.context.object
cam.data.type = 'PERSP'
cam.data.lens = 24
cam.rotation_euler = (alvo - cam_loc).to_track_quat('-Z', 'Y').to_euler()
scene.camera = cam

bpy.ops.wm.save_as_mainfile(filepath=output)
print("Saved", output)
