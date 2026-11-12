"""Cena de teste do TAAU com um cubo transparente (Alpha Blend) atravessando a tela.

    AnastacioEngine -b <taau.range> --python tools/debug/cenas/criar_cena_taau_transparente.py -- saida.range

Parte da cena de tools/debug/cenas/criar_cena_taa_movimento.py (carro parado, chão listrado) e
acrescenta "Vidro": cubo vermelho com alpha 0,5, filho do carro, que anda 0,12 m por quadro de
um lado ao outro na frente do carro. Transparente não grava a velocidade do TAA, então o
histórico pode deixar rastro atrás dele. Medição: tools/debug/medir_taau_transparente.py.
"""

import sys

import bmesh
import bpy

out = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "taau_vidro.range"
scene = bpy.context.scene
scene.scenefx_settings.use_taa = True

mat = bpy.data.materials.new("Vidro")
mat.diffuse_color = (1.0, 0.0, 0.0)
mat.use_shadeless = True
mat.use_transparency = True
mat.alpha = 0.5
mat.game_settings.alpha_blend = 'ALPHA'

me = bpy.data.meshes.new("Vidro")
bm = bmesh.new()
bmesh.ops.create_cube(bm, size=1.2)
bm.to_mesh(me)
bm.free()
me.materials.append(mat)
vidro = bpy.data.objects.new("Vidro", me)
scene.objects.link(vidro)
vidro.location = (-3.0, -3.0, 1.0)
vidro.game.physics_type = 'NO_COLLISION'

texto = bpy.data.texts.new("vidro.py")
texto.write(
    "from Range import logic\n"
    "own = logic.getCurrentController().owner\n"
    "x = own.worldPosition.x + 0.12\n"
    "own.worldPosition.x = -3.0 if x > 3.0 else x\n"
)
scene.objects.active = vidro
bpy.ops.logic.sensor_add(type='ALWAYS', object=vidro.name)
bpy.ops.logic.controller_add(type='PYTHON', object=vidro.name)
sens = vidro.game.sensors[-1]
sens.use_pulse_true_level = True
ctrl = vidro.game.controllers[-1]
ctrl.text = texto
sens.link(ctrl)

bpy.ops.wm.save_as_mainfile(filepath=out)
print("CENA", out)
