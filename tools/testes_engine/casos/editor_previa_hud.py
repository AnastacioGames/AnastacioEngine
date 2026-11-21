"""Prévia na 3D View, Fase 6 (docs/plano-previa-viewport.md): HUD da UI Tree. Uma tela HUD com um Panel vermelho
e outro azul; o jogo desenha por cima da janela e a viewport, na vista da câmera com Scene.range_ui_preview
ligado, desenha dentro do quadro da câmera com o mesmo módulo (range_ui_draw). Compara a geometria relativa
(posição do azul em relação ao vermelho, proporção do vermelho), que não depende do enquadramento, e confere que
desligar o toggle tira o HUD da prévia."""
from PIL import Image
import controle
from rodar import py

CENA = '''
import range_ui_tree as ui
sc = bpy.context.scene
sc.render.engine = 'BLENDER_GAME'
sc.render.resolution_x, sc.render.resolution_y = 1920, 1080
for ob in list(sc.objects):
    sc.objects.unlink(ob)
cam = bpy.data.objects.new('Camera', bpy.data.cameras.new('Camera'))
sc.objects.link(cam)
cam.location = (0, -6, 0)
cam.rotation_euler = (1.5708, 0, 0)
sc.camera = cam

tree = bpy.data.node_groups.new('HUD UI', ui.UITree.bl_idname)
tree.use_fake_user = True
f = tree.nodes.new('NodeFrame')
f.name = f.label = 'HUD'
f.ui_screen = f.ui_hud = True
f.shrink = False
f.location = (0, 0)
f.width, f.height = 640, 360
f.ui_scale_mode = 'STRETCH'


def painel(x, y, w, h, cor):
    n = tree.nodes.new('RangeUIPanel')
    n.parent = f
    n.location = (x, y)
    n.width, n.button_height = w, h
    n.color = cor
    n.radius = 0.0
    n.border = 0.0


painel(40, -40, 160, 80, (1, 0, 0, 1))
painel(400, -250, 200, 60, (0, 0, 1, 1))
ui.write_bake(tree, sc)
ui.setup_game_logic(cam, tree)
sc.range_ui_preview = True
'''

PREPARAR = '''
import bpy
bpy.context.scene.range_ui_preview = %s
for a in bpy.context.screen.areas:
    if a.type == 'VIEW_3D':
        sp = a.spaces.active
        sp.region_3d.view_perspective = 'CAMERA'
        sp.viewport_shade = 'MATERIAL'
        sp.show_only_render = True
        r = [r for r in a.regions if r.type == 'WINDOW'][0]
        caixa = (r.x, bpy.context.window.height - r.y - r.height, r.x + r.width, bpy.context.window.height - r.y)
bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=3)
resultado = list(caixa)
'''


def caixas(im, rodape=0):
    """Bounding box e centro de cada cor pura (vermelho, azul): {nome: (x0, y0, x1, y1, n)}."""
    w, h = im.size
    px = im.load()
    achados = {'vermelho': [w, h, -1, -1, 0], 'azul': [w, h, -1, -1, 0]}
    for y in range(h - rodape):  # rodape: faixa do header da viewport (botão Rec Play vermelho)
        for x in range(w):
            r, g, b = px[x, y]
            nome = 'vermelho' if (r > 150 and g < 60 and b < 60) else 'azul' if (b > 150 and r < 60 and g < 60) else None
            if nome:
                a = achados[nome]
                a[0], a[1], a[2], a[3], a[4] = min(a[0], x), min(a[1], y), max(a[2], x), max(a[3], y), a[4] + 1
    return achados


def geometria(c):
    """Escala-invariante: proporção do vermelho e onde o azul cai em relação a ele (em larguras do vermelho)."""
    v, a = c['vermelho'], c['azul']
    vw, vh = v[2] - v[0] + 1, v[3] - v[1] + 1
    return {'aspecto': vw / float(vh), 'dx': ((a[0] + a[2]) / 2.0 - (v[0] + v[2]) / 2.0) / vw,
            'dy': ((a[1] + a[3]) / 2.0 - (v[1] + v[3]) / 2.0) / vw}


def recorte(e, png, caixa):
    e.pedir("tela", arquivo=png)
    im = Image.open(png).convert('RGB').crop(caixa)
    im.save(png)
    return im


def testar(t):
    cena = t.gerar(CENA)

    j = t.jogo(cena, largura=960, altura=540)
    j.esperar(frames=40)
    j.tela(arquivo=str(t.pasta / 'jogo.png'))
    j.fechar()

    e = t.editor(cena)
    caixa = py(e, PREPARAR % 'True')
    com = recorte(e, str(t.pasta / 'com.png'), caixa)
    caixa = py(e, PREPARAR % 'False')
    sem = recorte(e, str(t.pasta / 'sem.png'), caixa)

    cj, cc, cs = caixas(Image.open(str(t.pasta / 'jogo.png')).convert('RGB')), caixas(com, 60), caixas(sem, 60)
    t.nota('jogo %s; prévia com %s; sem %s' % (cj, cc, cs))
    assert cj['vermelho'][4] > 200 and cj['azul'][4] > 200, 'o jogo não desenhou o HUD'
    assert cc['vermelho'][4] > 200 and cc['azul'][4] > 200, 'a prévia não desenhou o HUD'
    assert cs['vermelho'][4] < 20 and cs['azul'][4] < 20, 'com o toggle desligado o HUD ainda aparece na prévia'
    gj, gc = geometria(cj), geometria(cc)
    for chave in ('aspecto', 'dx', 'dy'):
        assert abs(gj[chave] - gc[chave]) < 0.08 * max(1.0, abs(gj[chave])), \
            'geometria do HUD difere do jogo em %s: jogo %.3f, prévia %.3f' % (chave, gj[chave], gc[chave])
