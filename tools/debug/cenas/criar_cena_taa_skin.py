"""Cena de teste do TAA com GPU Skinning (vetor de movimento pela paleta de ossos anterior).

    AnastacioEngine -b --factory-startup --python tools/debug/cenas/criar_cena_taa_skin.py -- saida.range

Uma barra listrada presa por GPU Skinning a um osso; o objeto fica parado e só a pose muda: com
"andar" ligado o osso vai e volta de lado (x = 1,5 sen(0,15 t), até 0,22 m por quadro). Câmera
parada, chão listrado parado. Sem o vetor do skinning a barra deixa rastro cinza.
O armature se chama "Carro" e tem a propriedade "andar", então serve o mesmo medidor, no modo cinza:
    python tools/debug/medir_taa_movimento.py saida.range --cinza
(Câmera andando junto com o osso não serve: a pose entra no desenho em outro momento que a câmera
e a barra treme na tela de verdade.)
"""

import sys

import bmesh
import bpy

out = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "taa_skin.range"

for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)

scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
gs = scene.game_settings
gs.use_auto_static_batch = False
gs.fps = 60
fx = scene.scenefx_settings
fx.use_fxaa = False
fx.use_taa = True


def material(nome, cor, skin):
    mat = bpy.data.materials.new(nome)
    mat.diffuse_color = cor
    mat.use_shadeless = True
    mat.use_gpu_skinning = skin
    return mat


def listrado(nome, largura, comprimento, altura, faixas, z, mats):
    """Caixa feita de faixas alternadas (material 0/1) ao longo de X."""
    me = bpy.data.meshes.new(nome)
    bm = bmesh.new()
    passo = largura / faixas
    for i in range(faixas):
        x0 = -largura / 2 + i * passo
        geo = bmesh.ops.create_cube(bm, size=1.0)
        verts = geo["verts"]
        for v in verts:
            v.co.x = x0 + (v.co.x + 0.5) * passo
            v.co.y *= comprimento
            v.co.z = z + (v.co.z + 0.5) * altura
        for f in {f for v in verts for f in v.link_faces}:
            f.material_index = i % 2
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    ob = bpy.data.objects.new(nome, me)
    scene.objects.link(ob)
    ob.game.physics_type = 'NO_COLLISION'
    return ob


chao = listrado("Chao", 40.0, 400.0, 0.1, 80, -0.1,
                [material("Branco", (1, 1, 1), False), material("Preto", (0, 0, 0), False)])
chao.location.y = 180.0
barra = listrado("Barra", 2.0, 4.0, 1.5, 9, 0.2,
                 [material("BrancoSkin", (1, 1, 1), True), material("PretoSkin", (0, 0, 0), True)])

arm_data = bpy.data.armatures.new("Carro")
arm_data.deform_method = 'BGE_GPU'
arm = bpy.data.objects.new("Carro", arm_data)
scene.objects.link(arm)
arm.game.physics_type = 'NO_COLLISION'
scene.objects.active = arm
bpy.ops.object.mode_set(mode='EDIT')
osso = arm_data.edit_bones.new("Osso")
osso.head = (0.0, 0.0, 0.0)
osso.tail = (0.0, 1.0, 0.0)
bpy.ops.object.mode_set(mode='OBJECT')

grupo = barra.vertex_groups.new("Osso")
grupo.add(list(range(len(barra.data.vertices))), 1.0, 'REPLACE')
mod = barra.modifiers.new("Armature", 'ARMATURE')
mod.object = arm
barra.parent = arm

cam_data = bpy.data.cameras.new("Camera")
cam = bpy.data.objects.new("Camera", cam_data)
scene.objects.link(cam)
cam.location = (0.0, -9.0, 3.5)
cam.rotation_euler = (1.30, 0.0, 0.0)
scene.camera = cam

NL = chr(10)
texto = bpy.data.texts.new("andar_osso.py")
texto.write(NL.join([
    "import math",
    "from Range import logic",
    "own = logic.getCurrentController().owner",
    "if own['andar']:",
    "    own['t'] += 1.0",
    "    ch = own.channels['Osso']",
    "    loc = ch.location",
    "    loc[0] = 1.5 * math.sin(own['t'] * own['vel'])",
    "    ch.location = loc",
    "    own.update()",
    "",
]))
scene.objects.active = arm
bpy.ops.object.game_property_new(type='BOOL', name="andar")
arm.game.properties["andar"].value = False
bpy.ops.object.game_property_new(type='FLOAT', name="vel")
arm.game.properties["vel"].value = 0.15
bpy.ops.object.game_property_new(type='FLOAT', name="t")
bpy.ops.logic.sensor_add(type='ALWAYS', object=arm.name)
bpy.ops.logic.controller_add(type='PYTHON', object=arm.name)
sens = arm.game.sensors[-1]
sens.use_pulse_true_level = True
ctrl = arm.game.controllers[-1]
ctrl.text = texto
sens.link(ctrl)

bpy.ops.wm.save_as_mainfile(filepath=out)
print("CENA", out)
