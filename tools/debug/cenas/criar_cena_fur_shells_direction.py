# Cena de validacao headless (branch shader-nodes) do socket novo "Direction"/"Direction Strength"
# do no Fur Shells (ver docs/shader-nodes.md). Confirma que os sockets existem em bpy.types, que
# dao pra ligar/configurar, e que o .range salvo roda sem crash no AnastacioRuntime (sobrevivencia +
# screenshot pra inspecao manual -- NAO confirma visualmente que o pelo "penteia" na direcao certa).
# Uso: AnastacioEngine.exe -b --factory-startup --python criar_cena_fur_shells_direction.py -- saida.range shot.png evidencia.txt
# Objetos:
#   FurNormal    - esfera com Fur Shells classico (Direction Strength 0, so a normal, compatibilidade).
#   FurDirecao   - esfera com Fur Shells + Direction fixo (vento) e Direction Strength 1 (penteado).
#   FurMisto     - esfera com Direction Strength 0.5 (mistura normal + direcao).
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
scene.world = world


def node_material(name):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    tree = mat.node_tree
    for n in list(tree.nodes):
        tree.nodes.remove(n)
    out = tree.nodes.new("ShaderNodeOutputMaterial")
    out.location = (600, 0)
    bsdf = tree.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (300, 0)
    tree.links.new(bsdf.outputs[0], out.inputs["Surface"])
    mat.game_settings.alpha_blend = 'CLIP'
    return mat, tree, out, bsdf


def mesh(op, name, loc, mat, **kw):
    op(location=loc, **kw)
    ob = bpy.context.active_object
    ob.name = name
    bpy.ops.object.shade_smooth()
    ob.data.materials.append(mat)
    return ob


checks = {}


def make_fur(name, loc, direction, strength):
    mat, tree, out, bsdf = node_material(name)
    fur = tree.nodes.new("ShaderNodeFurShells")
    fur.location = (0, 250)
    checks["%s_INPUTS" % name] = [s.identifier for s in fur.inputs]
    checks["%s_OUTPUTS" % name] = [s.identifier for s in fur.outputs]
    fur.inputs["Length"].default_value = 0.25
    fur.inputs["Layers"].default_value = 10.0
    fur.inputs["Density"].default_value = 180.0
    fur.inputs["Direction"].default_value = direction
    fur.inputs["Direction Strength"].default_value = strength
    tree.links.new(fur.outputs["Alpha"], bsdf.inputs["Base Color"])
    ob = mesh(bpy.ops.mesh.primitive_uv_sphere_add, name, loc, mat)
    return ob


# --- Classico: sem Direction (retrocompatibilidade, deve ficar igual ao Fur Shells de antes)
make_fur("FurNormal", (-3.2, 0, 1.2), (0.0, 0.0, 0.0), 0.0)

# --- Direcao total: pelo "penteado" todo na direcao do vento (eixo +X), ignora a normal
make_fur("FurDirecao", (0, 0, 1.2), (1.0, 0.0, 0.0), 1.0)

# --- Mistura: metade normal, metade direcao
make_fur("FurMisto", (3.2, 0, 1.2), (1.0, 0.0, 0.3), 0.5)

# Light + camera
lamp = bpy.data.lamps.new("Sun", 'SUN')
sun = bpy.data.objects.new("Sun", lamp)
scene.objects.link(sun)
sun.rotation_euler = (0.8, 0.2, 0.6)
cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
cam.data.lens = 28
scene.objects.link(cam)
cam.location = (0, -9, 3.5)
cam.rotation_euler = (Vector((0, 0, 1.2)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
scene.camera = cam

logic = bpy.data.texts.new("probe.py")
logic.from_string("""import bge

def tick(cont):
    own = cont.owner
    own['t'] = own.get('t', 0) + 1
    t = own['t']
    if t == 60:
        bge.render.makeScreenshot(%r)
    if t == 65:
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
for k in sorted(checks):
    print("CHECK", k, checks[k])
