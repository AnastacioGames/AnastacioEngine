"""Prova curta: o Screencast grava o cursor e os cliques injetados pelo controle?

    python tools/tutoriais/prova_gravacao.py cena.range saida.mp4
"""
import sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'testes_engine'))
import controle

cena, saida = sys.argv[1], str(Path(sys.argv[2]).resolve())
controle.abrir(cena, visivel=True, args_extra=('--window-fullscreen',))
ed = controle.Editor()


def pedir(cmd, **dados):
    r = ed.pedir(cmd, **dados)
    if not r['ok']:
        raise RuntimeError(r.get('traceback') or r.get('erro'))
    return r


# O Screencast desenha o cursor REAL do sistema (wm_get_cursor_position), não o dos eventos
# simulados: por isso o vídeo usa o mouse de verdade.  Janela em tela cheia = pixel da tela.
import ctypes
ctypes.windll.user32.SetProcessDPIAware()
U = ctypes.windll.user32
BOTOES = {'LEFTMOUSE': (0x0002, 0x0004), 'RIGHTMOUSE': (0x0008, 0x0010)}


def mover(x0, y0, x1, y1, segundos=1.0, passos=40):
    for i in range(1, passos + 1):
        t = i / passos
        t = t * t * (3 - 2 * t)  # sai e chega devagar, como a mão
        U.SetCursorPos(int(x0 + (x1 - x0) * t), int(y0 + (y1 - y0) * t))
        time.sleep(segundos / passos)


def clicar(x, y, botao='LEFTMOUSE'):
    U.SetCursorPos(x, y)
    U.mouse_event(BOTOES[botao][0], 0, 0, 0, 0)
    time.sleep(0.25)
    U.mouse_event(BOTOES[botao][1], 0, 0, 0, 0)


try:
    time.sleep(1.0)
    pedir('op', nome='screen.screencast', args={'filepath': saida, 'full': True, 'audio': False})
    time.sleep(1.0)
    mover(300, 300, 1100, 550, 1.5)
    clicar(1100, 550, 'RIGHTMOUSE')
    time.sleep(0.8)
    mover(1100, 550, 600, 700, 1.2)
    clicar(600, 700)
    time.sleep(0.8)
    mover(600, 700, 950, 400, 1.2)
    time.sleep(1.0)
    pedir('op', nome='screen.screencast')
    time.sleep(1.0)
finally:
    ed.canal.write('{"cmd": "fechar", "token": "%s"}\n' % ed.sessao['token'])
    ed.canal.flush()
print('gravado:', saida)
