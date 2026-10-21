# Cena de regressao do Choice para o no GLSL Script.
# Uso:
#   AnastacioEngine.exe -b --factory-startup --python criar_cena_smart_node_choice.py -- saida.range
#
# Objetos:
#   LegacyRaw       uniform numerico sem @choice (regressao).
#   ChoiceLocal     @choice com valores nao sequenciais, valor local 7 (Smooth).
#   ChoiceLinked    mesmo @choice, mas ligado a Value=12; o menu deve ficar oculto.
#
# A cena nao executa o jogo. Ela e feita para abrir no editor, salvar/reabrir e
# inspecionar sockets antes e depois do patch Choice.
import sys
import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
out_path = argv[0]

scene = bpy.context.scene
for ob in list(scene.objects):
    scene.objects.unlink(ob)
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.use_shading_nodes = True

world = bpy.data.worlds.new("ChoiceWorld")
world.horizon_color = (0.055, 0.075, 0.11)
world.mist_settings.use_mist = False
scene.world = world


def text(name, code):
    value = bpy.data.texts.new(name)
    value.from_string(code)
    return value


def material_with_script(name, source):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    tree = mat.node_tree
    for node in list(tree.nodes):
        tree.nodes.remove(node)
    output = tree.nodes.new("ShaderNodeOutputMaterial")
    output.location = (450, 0)
    bsdf = tree.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (220, 0)
    coord = tree.nodes.new("ShaderNodeTexCoord")
    coord.location = (-450, 0)
    script = tree.nodes.new("ShaderNodeGLSLScript")
    script.location = (-120, 0)
    script.script = source
    script.update()
    tree.update_tag()
    tree.links.new(coord.outputs["Object"], script.inputs["Vector"])
    tree.links.new(script.outputs["Color"], bsdf.inputs["Base Color"])
    tree.links.new(bsdf.outputs[0], output.inputs["Surface"])
    return mat, tree, script


legacy_text = text("choice_legacy_raw.glsl", """// Regressao: este campo continua numerico, sem menu Choice.
uniform int u_mode; // @default 1

void main(vec3 Vector, out vec4 Color)
{
    float stripe = step(0.5, fract(Vector.x * 3.0));
    Color = mix(vec4(0.08, 0.22, 0.85, 1.0), vec4(0.75, 0.95, 1.0, 1.0), stripe);
}
""")

choice_text = text("choice_modes.glsl", """// Valores propositalmente nao sequenciais: o dropdown deve gravar o valor,
 // nao o indice da opcao.
uniform int u_mode; // @choice Linear=2, Smooth=7, Step=12 @default 7

void main(vec3 Vector, out vec4 Color)
{
    float x = clamp(Vector.x * 0.5 + 0.5, 0.0, 1.0);
    float value = (u_mode == 2) ? x : ((u_mode == 7) ? smoothstep(0.15, 0.85, x) : step(0.5, x));
    Color = mix(vec4(0.04, 0.06, 0.10, 1.0), vec4(1.0, 0.34, 0.05, 1.0), value);
}
""")


def cube(name, location, mat):
    bpy.ops.mesh.primitive_cube_add(location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.data.materials.append(mat)
    return obj


legacy_mat, legacy_tree, legacy = material_with_script("ChoiceLegacyRaw", legacy_text)
choice_mat, choice_tree, choice_local = material_with_script("ChoiceLocal", choice_text)
linked_mat, linked_tree, choice_linked = material_with_script("ChoiceLinked", choice_text)

# Explicitly keep a valid local selection even if the parser's default behavior changes.
choice_local.inputs["u_mode"].default_value = 7.0
choice_linked.inputs["u_mode"].default_value = 7.0
value = linked_tree.nodes.new("ShaderNodeValue")
value.name = "ChoiceLinkedValue"
value.label = "Linked mode: Step (12)"
value.location = (-350, -150)
value.outputs[0].default_value = 12.0
linked_tree.links.new(value.outputs[0], choice_linked.inputs["u_mode"])

cube("LegacyRaw", (-3.2, 0.0, 1.1), legacy_mat)
cube("ChoiceLocal", (0.0, 0.0, 1.1), choice_mat)
cube("ChoiceLinked", (3.2, 0.0, 1.1), linked_mat)

# Ground and readable lighting.
ground = bpy.data.materials.new("ChoiceGround")
ground.diffuse_color = (0.10, 0.12, 0.16)
bpy.ops.mesh.primitive_plane_add(location=(0, 0, 0))
bpy.context.active_object.name = "Ground"
bpy.context.active_object.scale = (6.5, 3.5, 1.0)
bpy.context.active_object.data.materials.append(ground)

lamp_data = bpy.data.lamps.new("ChoiceSun", 'SUN')
lamp_data.energy = 1.4
sun = bpy.data.objects.new("ChoiceSun", lamp_data)
scene.objects.link(sun)
sun.rotation_euler = (0.55, -0.35, 0.45)

camera = bpy.data.objects.new("ChoiceCamera", bpy.data.cameras.new("ChoiceCamera"))
camera.data.lens = 32
camera.location = (0.0, -10.5, 4.5)
camera.rotation_euler = (Vector((0.0, 0.0, 1.0)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
scene.objects.link(camera)
scene.camera = camera

bpy.ops.wm.save_as_mainfile(filepath=out_path)
for node in (legacy, choice_local, choice_linked):
    socket = node.inputs["u_mode"]
    print("CHOICE_SCENE_SOCKET", node.name, socket.identifier, socket.default_value, socket.is_linked)

