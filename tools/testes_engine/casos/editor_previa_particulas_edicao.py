"""Prévia na 3D View, Fase 5: editar a curva de tamanho com a prévia ligada reconstrói o buffer (a coluna muda
sem religar o toggle)."""
import os
import sys
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rodar import py
from editor_previa_impostor import recorte
from editor_previa_particulas import PREPARAR, medir
from jogo_particulas_setup import CENA

LOOK = ("gp.particle_look = 'SMOKE'\ngp.use_size_curve = True\n"
        "gp.size_curve.curves[0].points[0].location = (0.0, 1.0)\n"
        "gp.size_curve.curves[0].points[1].location = (1.0, 0.1)\n")
EDITAR = '''
import bpy
for ob in bpy.context.scene.objects:
    if ob.use_gpu_particles:
        ob.gpu_particles.size_curve.curves[0].points[1].location = (1.0, 1.0)
        ob.gpu_particles.size_curve.update()
bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=2)
resultado = 1
'''


def amostrar(t, e, caixa, nome):
    for _ in range(8):
        time.sleep(0.4)
        py(e, "import bpy\nbpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)\nresultado = 1")
    return medir(recorte(e, str(t.pasta / (nome + '.png')), caixa))[0]


def testar(t):
    cena = t.gerar(CENA.replace('LOOK_LINHAS', LOOK), nome='edicao')
    e = t.editor(cena)
    caixa = py(e, PREPARAR.replace('LIGADO', 'True'))
    antes = amostrar(t, e, caixa, 'antes')
    py(e, EDITAR)
    depois = amostrar(t, e, caixa, 'depois')
    t.nota('cobertura antes %.3f, depois %.3f' % (antes, depois))
    assert antes > 0.01, 'sem partículas'
    assert depois > antes * 1.3, 'a edição da curva não refez a coluna'
