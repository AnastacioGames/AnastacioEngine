"""Cena inicial com o cubo padrão sem lógica (tutoriais que dão lógica ao cubo).

    AnastacioEngine.exe -b --factory-startup --python tools/tutoriais/criar_inicio_cubo_limpo.py -- saida.range

O cubo da cena padrão já anda com WASD (componente JogadorCelular): aqui ele sai sem componentes, ativo e
selecionado, e a 3D View olha pela câmera para o P mostrar o jogo como ele vai ficar.
"""
import sys

import bpy

saida = sys.argv[sys.argv.index("--") + 1]
cena = bpy.context.scene
cubo = bpy.data.objects["Cube"]
for ob in cena.objects:
    ob.select = ob is cubo
cena.objects.active = cubo
while len(cubo.game.components):
    bpy.ops.logic.python_component_remove(index=0)
texto = bpy.data.texts.get("03_jogador_celular.py")
if texto is not None:
    bpy.data.texts.remove(texto)
for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        area.spaces.active.region_3d.view_perspective = 'CAMERA'
bpy.ops.wm.save_as_mainfile(filepath=saida)
