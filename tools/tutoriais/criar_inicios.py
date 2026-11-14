"""Cenas iniciais dos tutoriais Smart Wizard, Logic Tree, Text Boxes e World Sound.

    AnastacioEngine.exe -b --factory-startup --python tools/tutoriais/criar_inicios.py -- <tutorial> saida.range

<tutorial>: smart_wizard_girador, logic_tree_andar, text_box_dialogo, world_sound_musica.
Todas partem da cena padrão (cubo sem componentes, câmera, luz), com a 3D View olhando pela
câmera para o P mostrar o jogo como ele vai ficar.  smart_wizard_girador ainda precisa do painel
Component Manager aberto: abrir a cena no editor, abrir o painel na aba Game, voltar à aba World
e salvar.
"""
import sys

import bpy
from mathutils import Vector

nome, saida = sys.argv[sys.argv.index("--") + 1:][:2]
cena = bpy.context.scene
cena.render.engine = 'BLENDER_GAME'

for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        area.spaces.active.region_3d.view_perspective = 'CAMERA'

# O sol automático da cena padrão fica ativo: o tutorial parte do cubo selecionado.
cubo = bpy.data.objects.get("Cube")
for ob in cena.objects:
    ob.select = ob is cubo
cena.objects.active = cubo
# O cubo padrão já anda com WASD (componente JogadorCelular): o tutorial parte de um cubo sem lógica.
if cubo is not None:
    while len(cubo.game.components):
        bpy.ops.logic.python_component_remove(index=0)
    texto_jogador = bpy.data.texts.get("03_jogador_celular.py")
    if texto_jogador is not None:
        bpy.data.texts.remove(texto_jogador)

if nome == "text_box_dialogo":
    bpy.data.objects.remove(bpy.data.objects["Cube"], do_unlink=True)
    camera = bpy.data.objects["Camera"]
    bpy.ops.object.text_add(location=(0.0, 0.0, 0.0))
    texto = bpy.context.object
    texto.name = "Fala"
    # De frente para a câmera, 6 unidades à frente dela (a rotação vem da matriz: a câmera pode
    # estar girada por constraint).
    texto.rotation_euler = camera.matrix_world.to_euler()
    frente = camera.matrix_world.to_quaternion() * Vector((0.0, 0.0, -1.0))
    texto.location = camera.matrix_world.translation + frente * 6.0
    texto.data.align_x = 'CENTER'
    texto.data.size = 0.3
    texto.data.text_boxes[0].width = 3.6  # já quebra a linha; Setup Dialogue põe a altura (páginas)
    texto.data.text_boxes[0].x = -1.8  # caixa centrada no objeto
    texto.data.body = ("Olá, viajante! Bem-vindo à vila. Faz tempo que ninguém passa por aqui. "
                       "A ponte do rio caiu na última tempestade, então o caminho para o castelo "
                       "agora é pela floresta. Leve esta lanterna: lá dentro é escuro. Boa sorte!")
    # Começa sem nada selecionado: o 1º passo é clicar no texto.
    for ob in cena.objects:
        ob.select = False
    cena.objects.active = None

bpy.ops.wm.save_as_mainfile(filepath=saida)
