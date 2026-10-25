# Cena de teste da sonda de luz em tempo real (KX_LightProbe com "probe_realtime"): um cubo vermelho
# grande e emissivo gira em volta da sonda, então a luz ambiente das esferas brancas muda com o tempo.
# A sonda é um Empty com as game properties "probe" (raio), "probe_size" e "probe_realtime" = 1.
# Uso: AnastacioEngine.exe -b --factory-startup --python criar_cena_sh9_sonda_tempo_real.py -- saida.range
# Env: TESTE_SH9_SHOT=<pasta> tira screenshots nos frames 30 e 90 e fecha;
#      TESTE_SH9_ESTATICA=1 deixa a sonda sem tempo real (captura única) para comparar.
import bpy
import os
import sys
from mathutils import Vector

saida = sys.argv[sys.argv.index("--") + 1]
shot = os.environ.get("TESTE_SH9_SHOT", "")
estatica = os.environ.get("TESTE_SH9_ESTATICA") == "1"

scene = bpy.context.scene
for ob in list(scene.objects):
    scene.objects.unlink(ob)
    bpy.data.objects.remove(ob)
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.use_shading_nodes = True
scene.game_settings.resolution_x = 960
scene.game_settings.resolution_y = 540

world = scene.world or bpy.data.worlds.new("World")
scene.world = world
world.use_nodes = False
world.use_sky_blend = False
world.horizon_color = (0.02, 0.02, 0.03)
world.light_settings.use_environment_light = False


def material(nome, cor, emissao=0.0):
    mat = bpy.data.materials.new(nome)
    mat.diffuse_color = cor
    mat.specular_intensity = 0.0
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    for n in list(nodes):
        nodes.remove(n)
    out_node = nodes.new('ShaderNodeOutputMaterial')
    if emissao > 0.0:
        em = nodes.new('ShaderNodeEmission')
        em.inputs['Color'].default_value = (cor[0], cor[1], cor[2], 1.0)
        em.inputs['Strength'].default_value = emissao
        mat.node_tree.links.new(em.outputs[0], out_node.inputs[0])
    else:
        bsdf = nodes.new('ShaderNodeBsdfPrincipled')
        bsdf.inputs['Base Color'].default_value = (cor[0], cor[1], cor[2], 1.0)
        bsdf.inputs['Roughness'].default_value = 1.0
        bsdf.inputs['Specular'].default_value = 0.0
        mat.node_tree.links.new(bsdf.outputs[0], out_node.inputs[0])
    return mat


branco = material("Branco", (0.8, 0.8, 0.8))
vermelho = material("VermelhoEmissivo", (1.0, 0.1, 0.05), 4.0)
azul = material("AzulEmissivo", (0.1, 0.25, 1.0), 1.5)

for x in (-2.5, 0.0, 2.5):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, size=1.0, location=(x, 0.0, 1.0), calc_uvs=True)
    ob = bpy.context.object
    bpy.ops.object.shade_smooth()
    ob.data.materials.append(branco)
bpy.ops.mesh.primitive_plane_add(radius=10.0, location=(0.0, 0.0, 0.0), calc_uvs=True)
bpy.context.object.data.materials.append(branco)

# Pivô no centro; o cubo vermelho é filho e gira em volta da sonda (lado oposto: azul fraco, fixo).
pivo = bpy.data.objects.new("Pivo", None)
scene.objects.link(pivo)
pivo.location = (0.0, 0.0, 1.5)
bpy.ops.mesh.primitive_cube_add(radius=1.5, location=(6.0, 0.0, 1.5))
cubo = bpy.context.object
cubo.name = "CuboVermelho"
cubo.data.materials.append(vermelho)
cubo.parent = pivo
cubo.location = (6.0, 0.0, 0.0)
bpy.ops.mesh.primitive_cube_add(radius=1.0, location=(0.0, 7.0, 1.0))
bpy.context.object.data.materials.append(azul)

sonda = bpy.data.objects.new("Sonda", None)
scene.objects.link(sonda)
sonda.location = (0.0, 0.0, 1.5)
scene.objects.active = sonda
for nome, tipo, valor in (("probe", 'FLOAT', 20.0), ("probe_size", 'INT', 64),
                          ("probe_realtime", 'INT', 0 if estatica else 1)):
    bpy.ops.object.game_property_new(type=tipo, name=nome)
    sonda.game.properties[nome].value = valor

# Giro do pivô por controlador Python (90 graus por segundo a 60 fps).
t = bpy.data.texts.new("gira.py")
t.write('''import math
def tick(cont):
    cont.owner.applyRotation((0.0, 0.0, math.radians(1.5)), False)
''')
scene.objects.active = pivo
bpy.ops.logic.sensor_add(type='ALWAYS', object=pivo.name)
bpy.ops.logic.controller_add(type='PYTHON', object=pivo.name)
pivo.game.sensors[0].use_pulse_true_level = True
pivo.game.controllers[0].mode = 'MODULE'
pivo.game.controllers[0].module = 'gira.tick'
pivo.game.sensors[0].link(pivo.game.controllers[0])

cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
scene.objects.link(cam)
scene.camera = cam
cam.location = (0.0, -9.0, 4.0)
cam.rotation_euler = (Vector((0.0, 0.0, 1.0)) - cam.location).to_track_quat('-Z', 'Y').to_euler()

if shot:
    base = os.path.join(shot, "sh9_sonda%s" % ("_estatica" if estatica else "_tempo_real"))
    t = bpy.data.texts.new("shot.py")
    t.write('''import bge
n = 0
def tick(cont):
    global n
    n += 1
    if n == 30:
        bge.render.makeScreenshot(%r)
    if n == 90:
        bge.render.makeScreenshot(%r)
    if n == 94:
        bge.logic.endGame()
''' % (base + "_f030.png", base + "_f090.png"))
    scene.objects.active = cam
    bpy.ops.logic.sensor_add(type='ALWAYS', object=cam.name)
    bpy.ops.logic.controller_add(type='PYTHON', object=cam.name)
    sen = cam.game.sensors[0]
    sen.use_pulse_true_level = True
    con = cam.game.controllers[0]
    con.mode = 'MODULE'
    con.module = 'shot.tick'
    sen.link(con)

bpy.ops.wm.save_as_mainfile(filepath=saida)
