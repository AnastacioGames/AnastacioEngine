"""Empty HUD na 3D View: barra Empty/Reverb/Lightning no topo quando o objeto ativo é uma empty, ligada por
View3D.show_empty_hud (padrão ligado). Confere painéis, toggle, toggle por botão e que só o topo muda."""
from PIL import Image, ImageChops
from rodar import py

CENA = '''
bpy.ops.object.empty_add(type='CUBE', location=(0, 0, 1))
bpy.context.scene.objects.active = bpy.context.object
'''

EMPTY = '''
for a in bpy.context.screen.areas:
    if a.type == 'VIEW_3D':
        sp = a.spaces.active
        sp.show_empty_hud = %s
for n in ('empty', 'reverb', 'lightning'):
    getattr(bpy.types, 'VIEW3D_PT_empty_hud_' + n)
resultado = [sp.show_empty_hud, bpy.context.active_object.type]
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
    d = lambda n: str(t.pasta / n)

    assert py(e, EMPTY % 'True') == [True, 'EMPTY']
    tela(e, d('on.png'))
    py(e, EMPTY % 'False')
    tela(e, d('off.png'))
    a, b = Image.open(d('on.png')).convert('RGB'), Image.open(d('off.png')).convert('RGB')
    caixa = ImageChops.difference(a, b).getbbox()
    assert caixa, 'o Empty HUD não aparece: telas iguais ligado e desligado'
    t.nota('area do HUD %s de %s' % (caixa, a.size))
    assert caixa[1] < a.size[1] * 0.35, 'HUD fora do topo: %s' % (caixa,)

    largura = caixa[2] - caixa[0]
    py(e, EMPTY % 'True' + "sp.show_empty_hud_lightning = False")
    tela(e, d('sem_lightning.png'))
    c2 = ImageChops.difference(Image.open(d('sem_lightning.png')).convert('RGB'), b).getbbox()
    assert c2 and (c2[2] - c2[0]) < largura, 'esconder Lightning não estreitou a barra: %s' % (c2,)
    py(e, EMPTY % 'True' + "sp.show_empty_hud_lightning = True")

    # clica no botão do meio (Shadow) e guarda o popover para conferência visual
    x, y = (caixa[0] + caixa[2]) // 2, (caixa[1] + caixa[3]) // 2
    evento(e, 'MOUSEMOVE', 'NOTHING', x, y)
    evento(e, 'LEFTMOUSE', 'PRESS', x, y)
    evento(e, 'LEFTMOUSE', 'RELEASE', x, y)
    tela(e, d('popover.png'))
    t.nota('prints em %s' % t.pasta)
