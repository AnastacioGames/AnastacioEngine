# Cena de validacao visual (branch shader-nodes): no GLSL Script com erro proposital (deve pintar
# vermelho no editor) + nos de World Bloom/SSR (devem aparecer em tela ao rodar).
# Uso: AnastacioEngine.exe -b --factory-startup --python criar_cena_erro_bloom_ssr.py -- saida.range shot.png evidencia.txt
# Depois, PARA CONFERIR O VISUAL:
#   1. Abrir saida.range no editor normal (com GUI), ir no Shader Editor com o material "Quebrado"
#      do cubo "Erro" selecionado: o no GLSL Script deve aparecer com cabecalho/corpo vermelho e um
#      selo de erro (tooltip com a mensagem do compilador). Esse e o unico passo que precisa do editor.
#   2. Rodar AnastacioRuntime.exe -w 1280 720 saida.range (tira o print no quadro 90 e fecha) e olhar
#      shot.png: a esfera emissiva central deve "vazar" luz nas bordas (Bloom) e o piso espelhado deve
#      refletir a esfera e o teto colorido (SSR). evidencia.txt confirma que o jogo rodou sem crash.
# Objetos:
#   Erro     - cubo com GLSL Script cujo Text tem um erro de sintaxe proposital (falta ';').
#   Emissora - esfera com Emission forte, pensada pra disparar o Bloom.
#   Piso     - plano com Principled de baixo roughness/alto metallic, pensado pra refletir no SSR.
#   Teto     - placa colorida acima da cena, só pra dar algo visivel pro SSR refletir no piso.
# World "World" tem os nos Bloom (Enable=True) e Screen Space Reflections (Enable=True) ligados
# soltos (sem ir ao World Output), igual ao uso real descrito em docs/shader-nodes.md.
import sys
import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
out_path = argv[0]
shot = argv[1].replace("\\", "/")
evidence = argv[2].replace("\\", "/")

scene = bpy.context.scene
for ob in list(scene.objects):
    scene.objects.unlink(ob)
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.use_shading_nodes = True

world = bpy.data.worlds.new("World")
world.horizon_color = (0.05, 0.05, 0.08)
world.mist_settings.use_mist = False
scene.world = world

wtree_tree = world.node_tree if world.use_nodes else None
world.use_nodes = True
wtree = world.node_tree
for n in list(wtree.nodes):
    wtree.nodes.remove(n)
wout = wtree.nodes.new("ShaderNodeOutputWorld")
wout.location = (400, 0)
wbg = wtree.nodes.new("ShaderNodeBackground")
wbg.location = (150, 0)
wbg.inputs["Color"].default_value = (0.05, 0.05, 0.08, 1.0)
wtree.links.new(wbg.outputs[0], wout.inputs["Surface"])

bloom = wtree.nodes.new("ShaderNodeWorldBloomFX")
bloom.location = (150, 250)
bloom.inputs["Enable"].default_value = True
bloom.inputs["Threshold"].default_value = 0.6
bloom.inputs["Intensity"].default_value = 3.0

ssr = wtree.nodes.new("ShaderNodeWorldSSRFX")
ssr.location = (150, 450)
ssr.inputs["Enable"].default_value = True
ssr.inputs["Max Steps"].default_value = 32
ssr.inputs["Lod"].default_value = 1
ssr.inputs["Bias"].default_value = 3.0
ssr.inputs["Max Distance"].default_value = 100.0


def node_material(name):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    tree = mat.node_tree
    for n in list(tree.nodes):
        tree.nodes.remove(n)
    out = tree.nodes.new("ShaderNodeOutputMaterial")
    out.location = (500, 0)
    bsdf = tree.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (250, 0)
    tree.links.new(bsdf.outputs[0], out.inputs["Surface"])
    return mat, tree, out, bsdf


def text(name, code):
    txt = bpy.data.texts.new(name)
    txt.from_string(code)
    return txt


def mesh(op, name, loc, mat, **kw):
    op(location=loc, **kw)
    ob = bpy.context.active_object
    ob.name = name
    ob.data.materials.append(mat)
    return ob


# --- GLSL Script with a deliberate syntax error (missing ';'), to check the red-node badge
broken = text("broken.glsl", """void main(vec3 color, out vec3 result)
{
	result = color * 2.0
}
""")
mat, tree, out, bsdf = node_material("Quebrado")
coord = tree.nodes.new("ShaderNodeTexCoord")
coord.location = (-300, 0)
node = tree.nodes.new("ShaderNodeGLSLScript")
node.script = broken
node.location = (0, 0)
node.update()
tree.update_tag()
tree.links.new(coord.outputs["Object"], node.inputs["color"])
tree.links.new(node.outputs["result"], bsdf.inputs["Base Color"])
mesh(bpy.ops.mesh.primitive_cube_add, "Erro", (-3.5, 0, 1.0), mat)

# --- Emissive sphere, meant to trigger Bloom
mat, tree, out, bsdf = node_material("Emissora")
bsdf.inputs["Base Color"].default_value = (1.0, 0.9, 0.2, 1.0)
if "Emission" in bsdf.inputs:
    bsdf.inputs["Emission"].default_value = (1.0, 0.9, 0.2, 1.0)
    bsdf.inputs["Emission Strength"].default_value = 6.0
mesh(bpy.ops.mesh.primitive_uv_sphere_add, "Emissora", (0, 0, 1.6), mat, segments=48, ring_count=24)
bpy.ops.object.shade_smooth()

# --- Reflective floor, meant to show SSR
mat, tree, out, bsdf = node_material("Piso")
bsdf.inputs["Base Color"].default_value = (0.2, 0.2, 0.25, 1.0)
bsdf.inputs["Roughness"].default_value = 0.05
bsdf.inputs["Metallic"].default_value = 0.9
mesh(bpy.ops.mesh.primitive_plane_add, "Piso", (0, 0, 0), mat, radius=8)

# --- Coloured ceiling slab, just something visible for SSR to reflect
mat, tree, out, bsdf = node_material("Teto")
bsdf.inputs["Base Color"].default_value = (0.2, 0.6, 1.0, 1.0)
mesh(bpy.ops.mesh.primitive_plane_add, "Teto", (0, 0, 6), mat, radius=6)
bpy.context.active_object.rotation_euler = (3.14159, 0, 0)

# Light + camera
lamp = bpy.data.lamps.new("Sun", 'SUN')
sun = bpy.data.objects.new("Sun", lamp)
scene.objects.link(sun)
sun.rotation_euler = (0.8, 0.2, 0.6)
cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
cam.data.lens = 28
scene.objects.link(cam)
cam.location = (3.5, -9, 3.2)
cam.rotation_euler = (Vector((0, 0, 1.4)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
scene.camera = cam

logic = bpy.data.texts.new("probe.py")
logic.from_string("""import bge

def tick(cont):
    own = cont.owner
    scene = bge.logic.getCurrentScene()
    own['t'] = own.get('t', 0) + 1
    t = own['t']
    if t == 90:
        bge.render.makeScreenshot(%r)
    if t == 95:
        with open(%r, 'w') as f:
            f.write('frames_ok=%%d\\n' %% t)
        bge.logic.endGame()
""" % (shot, evidence))
scene.objects.active = cam
bpy.ops.logic.sensor_add(type='ALWAYS', object=cam.name)
bpy.ops.logic.controller_add(type='PYTHON', object=cam.name)
s = cam.game.sensors[-1]
s.use_pulse_true_level = True
c = cam.game.controllers[-1]
c.mode = 'MODULE'
c.module = 'probe.tick'
s.link(c)

bpy.ops.wm.save_as_mainfile(filepath=out_path)
print("WORLD_FX_NODES", [n.bl_idname for n in wtree.nodes if n.bl_idname.startswith("ShaderNodeWorld")])
print("BROKEN_SCRIPT_SOCKETS", [(s.identifier, s.bl_idname) for s in node.inputs], [s.identifier for s in node.outputs])
