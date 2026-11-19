"""Camera HUD na 3D View: barra com Lens/Focus/Effects/Display no topo da vista de câmera, ligada por
View3D.show_camera_hud (padrão ligado). Confere os painéis dos popovers, o toggle e que só a faixa
do topo muda na tela."""
from PIL import Image, ImageChops
from rodar import py

CENA = '''
bpy.ops.object.camera_add(location=(0, -8, 3), rotation=(1.2, 0, 0))
bpy.context.scene.camera = bpy.context.object
'''

CAMERA = '''
for a in bpy.context.screen.areas:
    if a.type == 'VIEW_3D':
        sp = a.spaces.active
        sp.region_3d.view_perspective = 'CAMERA'
        sp.show_camera_hud = %s
resultado = [bpy.types.VIEW3D_PT_camera_hud_lens.bl_label, sp.show_camera_hud, sp.camera is not None]
'''


def tela(e, arquivo):
    r = e.pedir('tela', arquivo=arquivo, editor='VIEW_3D')
    assert r['ok'], r.get('traceback') or r['erro']


def evento(e, tipo, valor, x, y):
    r = e.pedir('evento', tipo=tipo, valor=valor, x=x, y=y)
    assert r['ok'], r.get('traceback') or r['erro']


def testar(t):
    cena = t.gerar(CENA)
    e = t.editor(cena)
    on_png, off_png, pop_png = (str(t.pasta / n) for n in ('on.png', 'off.png', 'popover.png'))

    r = py(e, CAMERA % 'True')
    assert r == ['Lens', True, True], r
    tela(e, on_png)
    py(e, CAMERA % 'False')
    tela(e, off_png)

    a, b = Image.open(on_png).convert('RGB'), Image.open(off_png).convert('RGB')
    caixa = ImageChops.difference(a, b).getbbox()
    assert caixa, 'o HUD não aparece: telas iguais com ele ligado e desligado'
    t.nota('area do HUD %s de %s' % (caixa, a.size))
    assert caixa[1] < a.size[1] * 0.35, 'HUD fora do topo: %s' % (caixa,)

    # esconder um botão estreita a barra; esconder todos deixa só o nome da câmera
    largura = caixa[2] - caixa[0]
    py(e, CAMERA % 'True' + "sp.show_camera_hud_effects = False")
    tela(e, str(t.pasta / 'sem_effects.png'))
    c2 = ImageChops.difference(Image.open(str(t.pasta / 'sem_effects.png')).convert('RGB'), b).getbbox()
    assert c2 and (c2[2] - c2[0]) < largura, 'esconder Effects não estreitou a barra: %s' % (c2,)
    t.nota('largura %d -> %d sem Effects' % (largura, c2[2] - c2[0]))
    py(e, CAMERA % 'True' + "sp.show_camera_hud_effects = True")

    # clica no botão Lens (primeiro depois do nome) e guarda o popover para conferência visual
    py(e, CAMERA % 'True')
    x = (caixa[0] + caixa[2]) // 2
    y = (caixa[1] + caixa[3]) // 2
    evento(e, 'MOUSEMOVE', 'NOTHING', x, y)
    evento(e, 'LEFTMOUSE', 'PRESS', x, y)
    evento(e, 'LEFTMOUSE', 'RELEASE', x, y)
    tela(e, pop_png)
    t.nota('prints em %s' % t.pasta)
