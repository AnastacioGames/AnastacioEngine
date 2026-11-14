"""Cena inicial do tutorial "Seu primeiro menu de jogo com a UI Tree".

    AnastacioEngine.exe -b --factory-startup --python tools/tutoriais/criar_inicio_ui_tree_menu.py -- saida.range

A cena padrão (cubo, câmera, luz), com a 3D View olhando pela câmera para o P mostrar o jogo
como ele vai ficar.  O tutorial e o vídeo partem deste arquivo.
"""
import sys

import bpy

saida = sys.argv[sys.argv.index("--") + 1]
for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        area.spaces.active.region_3d.view_perspective = 'CAMERA'
bpy.ops.wm.save_as_mainfile(filepath=saida)
