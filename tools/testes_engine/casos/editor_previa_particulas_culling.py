"""Prévia na 3D View, Fase 5: emissor de malha fora do campo de visão não é simulado nem desenhado (como no
jogo), mesmo que as partículas, grandes, invadissem a imagem. Câmera girada: dentro da vista aparece, logo
fora da vista não; o jogo e a prévia concordam."""
import os
import sys
import time
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rodar import py
from editor_previa_impostor import recorte
from editor_previa_particulas import PREPARAR, medir
from jogo_particulas_setup import CENA

LOOK = "gp.particle_look = 'SMOKE'\ngp.size = 3.0\n"
ANGULO = 'cam.rotation_euler = (1.4, 0, ANG)'


def amostrar(t, e, caixa, nome):
    for _ in range(6):
        time.sleep(0.4)
        py(e, "import bpy\nbpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)\nresultado = 1")
    return medir(recorte(e, str(t.pasta / (nome + '.png')), caixa))[0]


def testar(t):
    res = {}
    for nome, ang in (('dentro', '0.2'), ('fora', '0.62')):
        base = CENA.replace('LOOK_LINHAS', LOOK).replace('cam.rotation_euler = (1.4, 0, 0)', ANGULO.replace('ANG', ang))
        cena = t.gerar(base, nome='culling_' + nome)
        j = t.jogo(cena, largura=960, altura=540)
        j.esperar(frames=90)
        arq = str(t.pasta / (nome + '_jogo.png'))
        j.tela(arquivo=arq)
        j.fechar()
        jc = medir(Image.open(arq).convert('RGB'))[0]
        e = t.editor(cena)
        caixa = py(e, PREPARAR.replace('LIGADO', 'True'))
        pc = amostrar(t, e, caixa, nome + '_previa')
        res[nome] = (jc, pc)
        t.nota('%s: jogo %.4f, prévia %.4f' % (nome, jc, pc))
    assert res['dentro'][1] > 0.02, 'emissor na vista sem partículas'
    assert res['fora'][1] < 0.005, 'emissor fora da vista foi desenhado'
    assert res['fora'][0] < 0.005, 'o jogo mostrou o emissor fora da vista: premissa do teste falhou'
