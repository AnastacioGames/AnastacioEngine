"""Ações do vídeo do tutorial "Seu primeiro menu de jogo com a UI Tree".

Coordenadas em pixels da tela cheia 2560x1440 com a interface em escala 1.5
(tools/tutoriais/gravar_video.py).  `mao` = mouse/teclado; ver a classe Mao.
"""
import time

ENQUADRAR = """
t = bpy.data.node_groups[-1]
menu = t.nodes['Menu']
alvo = {n for n in t.nodes if n.parent == menu}
alvo |= {l.to_node for l in t.links if l.from_node in alvo}
for n in t.nodes:
    n.select = n in alvo
bpy.ops.node.view_selected(contexto('NODE_EDITOR'))
for n in t.nodes:
    n.select = False
t.nodes.active = None
"""

ROLAR_TEXT = 23            # giros da roda até o campo Text aparecer no painel
TEXT = (1770, 1312)        # campo Text depois de rolar
START_NO_JOGO = (1140, 330)  # botão Start dentro do jogo


def preparar(mao, ed):
    """Fora do vídeo: aumenta a área de baixo para o Node Editor caber bem."""
    def ev(tipo, valor, x, y):
        ed.pedir('evento', tipo=tipo, valor=valor, x=x, y=y)
        time.sleep(0.15)
    ev('MOUSEMOVE', 'NOTHING', 900, 1008)
    ev('LEFTMOUSE', 'PRESS', 900, 1008)
    for i in range(1, 9):
        ev('MOUSEMOVE', 'NOTHING', 900, 1008 - 31 * i)
    ev('LEFTMOUSE', 'RELEASE', 900, 760)


def passo_1(mao):  # Node Editor + tipo UI
    mao.clicar(36, 788)
    mao.clicar(120, 970)
    mao.esperar(0.6)
    mao.clicar(1225, 792)


def passo_2(mao):  # New
    mao.clicar(1543, 792)


def passo_3(mao):  # + Menu
    mao.clicar(1660, 1150)
    mao.esperar(0.5)
    mao.py(ENQUADRAR)
    mao.mover(1200, 1250)


def passo_4(mao):  # botão Jogar -> Start
    mao.clicar(556, 1082)
    mao.mover(1750, 1200)
    mao.rolar(ROLAR_TEXT)
    mao.clicar(*TEXT)
    mao.digitar('Start')
    mao.tecla('RET')
    mao.mover(420, 1088)


def passo_5(mao):  # Setup Game Logic
    mao.mover(1750, 1200)
    mao.rolar(-30)
    mao.clicar(1750, 1196)


def passo_6(mao):  # P e clicar em Start
    mao.mover(1140, 400)
    if not mao.real:  # no ensaio o jogo travaria o servidor de controle
        return
    mao.tecla('P')
    mao.esperar(3.0)
    mao.clicar(*START_NO_JOGO)
    mao.esperar(2.5)
    mao.tecla('ESC')
    mao.esperar(1.0)
