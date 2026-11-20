"""Prévia na 3D View, Fase 5 (docs/plano-previa-viewport.md): partículas do jogo na viewport
(Game Preview > Particles). Emissor com look de fumaça e de fogo: o jogo e a prévia devem mostrar a coluna
no mesmo lugar e com cobertura parecida; com o toggle desligado a prévia não mostra nada."""
import os
import sys
import time
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rodar import py
from editor_previa_impostor import recorte
from jogo_particulas_setup import CENA

PREPARAR = '''
import bpy
for a in bpy.context.screen.areas:
    if a.type == 'VIEW_3D':
        sp = a.spaces.active
        sp.region_3d.view_perspective = 'CAMERA'
        sp.viewport_shade = 'MATERIAL'
        sp.show_only_render = True
        sp.fx_settings.use_game_particles = LIGADO
        r = [r for r in a.regions if r.type == 'WINDOW'][0]
        caixa = (r.x, bpy.context.window.height - r.y - r.height, r.x + r.width, bpy.context.window.height - r.y)
bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=3)
resultado = list(caixa)
'''


def medir(im):
    w, h = im.size
    px = im.load()
    n = sx = sy = 0
    for y in range(h):
        for x in range(w):
            if max(px[x, y]) > 40:
                n += 1
                sx += x
                sy += y
    if n == 0:
        return 0.0, 0.5, 0.5
    return n / (w * h), sx / n / w, sy / n / h


def testar(t):
    for nome, look in (('fumaca', "gp.particle_look = 'SMOKE'"), ('fogo', "gp.particle_look = 'FIRE'")):
        cena = t.gerar(CENA.replace('LOOK_LINHAS', look), nome=nome)
        j = t.jogo(cena, largura=960, altura=540)
        j.esperar(frames=90)
        arq = str(t.pasta / (nome + '_jogo.png'))
        j.tela(arquivo=arq)
        j.fechar()
        jc, jx, jy = medir(Image.open(arq).convert('RGB').crop((96, 54, 864, 486)))

        e = t.editor(cena)
        caixa = py(e, PREPARAR.replace('LIGADO', 'False'))
        im = recorte(e, str(t.pasta / (nome + '_previa_off.png')), caixa)
        off = medir(im)[0]
        caixa = py(e, PREPARAR.replace('LIGADO', 'True'))
        for _ in range(8):
            time.sleep(0.4)
            py(e, "import bpy\nbpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)\nresultado = 1")
        im = recorte(e, str(t.pasta / (nome + '_previa.png')), caixa)
        pc, px_, py_ = medir(im)
        t.nota('%s: jogo cob %.3f c(%.2f,%.2f); prévia cob %.3f c(%.2f,%.2f); desligada %.4f' % (nome, jc, jx, jy, pc, px_, py_, off))
        assert jc > 0.003, nome + ': o jogo não mostrou partículas'
        assert off < jc * 0.2, nome + ': a prévia mostrou partículas com o toggle desligado'
        assert pc > jc * 0.25, nome + ': a prévia quase não mostrou partículas'
        assert abs(px_ - jx) < 0.15 and abs(py_ - jy) < 0.15, nome + ': a coluna está em outro lugar'
