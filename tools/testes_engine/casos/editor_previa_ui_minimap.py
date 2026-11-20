"""Prévia na 3D View, Fase 6: Minimap do HUD com marcadores reais (objetos com a propriedade `minimap`, cor
`minimap_color`): mover o objeto muda onde o ponto aparece."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rodar import py
from editor_previa_impostor import recorte
from editor_previa_particulas import medir
from editor_previa_ui_hud import PREPARAR

CENA = '''
import range_ui_tree as ui
sc = bpy.context.scene
for ob in list(sc.objects):
    if ob.type != 'CAMERA':
        sc.objects.unlink(ob)
w = bpy.data.worlds.new('W'); w.horizon_color = (0, 0, 0); sc.world = w
cam = [o for o in sc.objects if o.type == 'CAMERA'][0]
sc.camera = cam
tree = bpy.data.node_groups.new('HUD UI', ui.UITree.bl_idname)
tree.use_fake_user = True
f = tree.nodes.new('NodeFrame'); f.name = f.label = 'HUD'
f.ui_screen, f.ui_hud, f.shrink = True, True, False
f.location = (0, 0); f.width, f.height = 640, 360
m = tree.nodes.new(ui.UIMinimapNode.bl_idname)
m.parent, m.location, m.width, m.button_height = f, (220, -80), 200, 200
m.world_min, m.world_max = (-10.0, -10.0), (10.0, 10.0)
bpy.ops.object.empty_add(location=(0, 0, 0))
alvo = bpy.context.scene.objects.active
alvo.name = 'Alvo'
bpy.ops.object.game_property_new(type='BOOL', name='minimap')
alvo.game.properties['minimap'].value = True
bpy.ops.object.game_property_new(type='STRING', name='minimap_color')
alvo.game.properties['minimap_color'].value = '#ff0000'
'''

MOVER = '''
import bpy
bpy.data.objects['Alvo'].location = (X, 0, 0)
bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=3)
resultado = 1
'''


def testar(t):
    e = t.editor(t.gerar(CENA, nome='ui_minimap'))
    caixa = py(e, PREPARAR.replace('LIGADO', 'True'))
    py(e, MOVER.replace('X', '-6'))
    a = medir(recorte(e, str(t.pasta / 'a.png'), caixa))
    py(e, MOVER.replace('X', '6'))
    b = medir(recorte(e, str(t.pasta / 'b.png'), caixa))
    t.nota('cobertura %.4f/%.4f; centro x %.3f -> %.3f; cor %s' % (a[0], b[0], a[1], b[1], tuple(int(c) for c in b[3])))
    assert a[0] > 0.001, 'o minimapa não apareceu'
    assert b[1] > a[1] + 0.005, 'o marcador não acompanhou o objeto'
