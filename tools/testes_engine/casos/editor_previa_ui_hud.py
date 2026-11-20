"""Prévia na 3D View, Fase 6 (docs/plano-previa-viewport.md): HUD da UI Tree na viewport (Game Preview > UI Tree
HUD). Com o toggle desligado a visão de câmera fica escura; ligado, a barra de vida e o velocímetro do template
HUD aparecem."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rodar import py
from editor_previa_impostor import recorte
from editor_previa_particulas import medir

CENA = '''
import range_ui_tree as ui
sc = bpy.context.scene
sc.render.engine = 'BLENDER_GAME'
for ob in list(sc.objects):
    if ob.type != 'CAMERA':
        sc.objects.unlink(ob)
w = bpy.data.worlds.new('W'); w.horizon_color = (0, 0, 0); sc.world = w
if sc.camera is None:
    cd = bpy.data.cameras.new('Camera'); co = bpy.data.objects.new('Camera', cd); sc.objects.link(co); sc.camera = co
tree = bpy.data.node_groups.new('HUD UI', ui.UITree.bl_idname)
tree.use_fake_user = True
ui.add_template(tree, 'HUD', (0.0, 0.0))
ui.write_bake(tree, sc)
ui.setup_game_logic(sc.camera, tree)
'''

PREPARAR = '''
import bpy
for a in bpy.context.screen.areas:
    if a.type == 'VIEW_3D':
        sp = a.spaces.active
        sp.region_3d.view_perspective = 'CAMERA'
        sp.viewport_shade = 'MATERIAL'
        sp.show_only_render = True
        r = [r for r in a.regions if r.type == 'WINDOW'][0]
        caixa = (r.x, bpy.context.window.height - r.y - r.height, r.x + r.width, bpy.context.window.height - r.y)
bpy.context.scene.range_ui_preview = LIGADO
bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=3)
resultado = list(caixa)
'''


def testar(t):
    cena = t.gerar(CENA, nome='ui_hud')
    e = t.editor(cena)
    caixa = py(e, PREPARAR.replace('LIGADO', 'False'))
    off = medir(recorte(e, str(t.pasta / 'off.png'), caixa))[0]
    caixa = py(e, PREPARAR.replace('LIGADO', 'True'))
    on = medir(recorte(e, str(t.pasta / 'on.png'), caixa))[0]
    t.nota('cobertura off %.4f, on %.4f' % (off, on))
    assert on > off + 0.005, 'o HUD não apareceu na viewport'
