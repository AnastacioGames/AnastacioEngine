"""Cena de teste da etapa 2 do TAA (vetores de movimento por objeto, docs/plano-taa.md).

    AnastacioEngine -b --factory-startup --python tools/debug/cenas/criar_cena_taa_movimento.py -- saida.range

Um "carro" listrado (preto e branco, bordas finas) anda rápido de lado (+X) com a câmera presa
atrás dele: na tela ele fica parado e o chão corre, o caso do carro seguido pela câmera. O chão listrado fica parado. Com TAA só pela câmera o carro
borra/deixa rastro; com o vetor de movimento deve ficar nítido como sem TAA.
Medição: tools/debug/medir_taa_movimento.py.
"""

import sys

import bmesh
import bpy

out = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "taa_movimento.range"

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


def material(nome, cor):
    mat = bpy.data.materials.new(nome)
    mat.diffuse_color = cor
    mat.use_shadeless = True
    return mat


branco = material("Branco", (1.0, 1.0, 1.0))
preto = material("Preto", (0.0, 0.0, 0.0))


def listrado(nome, largura, comprimento, altura, faixas, z):
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
        faces = {f for v in verts for f in v.link_faces}
        for f in faces:
            f.material_index = i % 2
    bm.to_mesh(me)
    bm.free()
    me.materials.append(branco)
    me.materials.append(preto)
    ob = bpy.data.objects.new(nome, me)
    scene.objects.link(ob)
    return ob


chao = listrado("Chao", 40.0, 400.0, 0.1, 80, -0.1)
chao.location.y = 180.0
carro = listrado("Carro", 2.0, 4.0, 1.5, 9, 0.2)
carro.game.physics_type = 'NO_COLLISION'
chao.game.physics_type = 'NO_COLLISION'

cam_data = bpy.data.cameras.new("Camera")
cam = bpy.data.objects.new("Camera", cam_data)
scene.objects.link(cam)
cam.location = (0.0, -9.0, 3.5)
cam.rotation_euler = (1.30, 0.0, 0.0)
cam.parent = carro
scene.camera = cam

# O carro anda 0,25 m por frame (15 m/s a 60 FPS) quando a propriedade "andar" é verdadeira.
texto = bpy.data.texts.new("andar.py")
texto.write(
    "from Range import logic\n"
    "own = logic.getCurrentController().owner\n"
    "if own['andar']:\n"
    "    own.worldPosition.x += own['vel']\n"
)
bpy.context.scene.objects.active = carro
bpy.ops.object.game_property_new(type='BOOL', name="andar")
carro.game.properties["andar"].value = False
bpy.ops.object.game_property_new(type='FLOAT', name="vel")
carro.game.properties["vel"].value = 0.25
bpy.ops.logic.sensor_add(type='ALWAYS', object=carro.name)
bpy.ops.logic.controller_add(type='PYTHON', object=carro.name)
sens = carro.game.sensors[-1]
sens.use_pulse_true_level = True
ctrl = carro.game.controllers[-1]
ctrl.text = texto
sens.link(ctrl)

bpy.ops.wm.save_as_mainfile(filepath=out)
print("CENA", out)
