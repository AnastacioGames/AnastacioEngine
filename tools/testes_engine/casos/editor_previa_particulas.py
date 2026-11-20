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
        return 0.0, 0.5, 0.5, (0, 0, 0)
    cor = [0, 0, 0]
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            p = px[x, y]
            if max(p) > 40:
                for k in range(3):
                    cor[k] += p[k]
    m = max(1, sum(1 for y in range(0, h, 2) for x in range(0, w, 2) if max(px[x, y]) > 40))
    return n / (w * h), sx / n / w, sy / n / h, tuple(c / m for c in cor)


def atlas(caminho):
    """2x2: quatro quadros de cores bem diferentes (vermelho, verde, azul, amarelo), disco macio."""
    im = Image.new('RGBA', (128, 128), (0, 0, 0, 0))
    cores = ((255, 40, 40), (40, 255, 40), (60, 60, 255), (255, 255, 40))
    px = im.load()
    for q, c in enumerate(cores):
        ox, oy = (q % 2) * 64, (q // 2) * 64
        for y in range(64):
            for x in range(64):
                d = ((x - 31.5) ** 2 + (y - 31.5) ** 2) ** 0.5 / 30.0
                if d < 1:
                    px[ox + x, oy + y] = c + (int(255 * (1 - d * d)),)
    im.save(caminho)
    return caminho.replace(chr(92), '/')


NL = chr(10)
MIX = NL.join((
    "em.use_gpu_particles_mix = True", "mx = em.gpu_particles_mix", "mx.particle_count = 200",
    "mx.size = 0.5", "mx.lifetime = 2.0", "mx.color = (0.1, 0.4, 1.0, 1.0)", "mx.particle_look = 'FIRE'"))
FLIP = NL.join(("gp.size = 1.6", 
    "gp.texture = r'ATLAS'", "gp.flipbook_columns = 2", "gp.flipbook_rows = 2", "gp.flipbook_cycles = 1.0"))
CHAO = NL.join((
    "gp.particle_look = 'SMOKE'", "gp.size = 1.2",
    "bpy.ops.mesh.primitive_plane_add(radius=6, location=(0, 0, 0.4))",
    "pl = bpy.context.scene.objects.active",
    "mt = bpy.data.materials.new('chao'); mt.use_shadeless = True; mt.diffuse_color = (0.03, 0.03, 0.03)",
    "pl.data.materials.append(mt)"))
CASOS = (('fumaca', "gp.particle_look = 'SMOKE'"), ('fogo', "gp.particle_look = 'FIRE'"),
         ('flipbook', FLIP), ('mix', "gp.particle_look = 'SMOKE'" + NL + MIX), ('chao', CHAO))


def testar(t):
    for nome, look in CASOS:
        look = look.replace('ATLAS', atlas(str(t.pasta / 'atlas.png')))
        cena = t.gerar(CENA.replace('LOOK_LINHAS', look), nome=nome)
        j = t.jogo(cena, largura=960, altura=540)
        j.esperar(frames=90)
        arq = str(t.pasta / (nome + '_jogo.png'))
        j.tela(arquivo=arq)
        j.fechar()
        jc, jx, jy, jcor = medir(Image.open(arq).convert('RGB').crop((96, 54, 864, 486)))

        e = t.editor(cena)
        caixa = py(e, PREPARAR.replace('LIGADO', 'False'))
        im = recorte(e, str(t.pasta / (nome + '_previa_off.png')), caixa)
        off = medir(im)[0]
        caixa = py(e, PREPARAR.replace('LIGADO', 'True'))
        for _ in range(8):
            time.sleep(0.4)
            py(e, "import bpy\nbpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)\nresultado = 1")
        im = recorte(e, str(t.pasta / (nome + '_previa.png')), caixa)
        pc, px_, py_, pcor = medir(im)
        t.nota('%s: jogo cob %.3f c(%.2f,%.2f) cor %s; prévia cob %.3f c(%.2f,%.2f) cor %s; desligada %.4f' % (nome, jc, jx, jy, tuple(int(v) for v in jcor), pc, px_, py_, tuple(int(v) for v in pcor), off))
        assert jc > 0.003, nome + ': o jogo não mostrou partículas'
        if nome == 'chao':  # o plano cobre boa parte da tela: a prévia ligada tem de ter mais que desligada
            assert pc > off + 0.03, nome + ': o toggle não acrescentou partículas'
            assert abs(pc - jc) < 0.15, nome + ': a cobertura difere do jogo'
            continue
        assert off < max(jc * 0.2, 0.004), nome + ': a prévia mostrou partículas com o toggle desligado'
        assert pc > jc * 0.25, nome + ': a prévia quase não mostrou partículas'
        assert abs(px_ - jx) < 0.15 and abs(py_ - jy) < 0.15, nome + ': a coluna está em outro lugar'
        assert max(abs(a - b) for a, b in zip(jcor, pcor)) < 50, nome + ': a cor média difere'
