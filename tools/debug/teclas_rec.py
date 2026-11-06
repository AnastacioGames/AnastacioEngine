# Aperta teclas no jogo do Rec Play, de fora do processo, porque na contagem a logica do jogo esta parada.
# So aperta com a janela do editor em foco, para nao digitar em outro programa.
#   python teclas_rec.py <pid> <arquivo de log> <tecla:segundos, espera:segundos ou clique_X_Y:segundos> ...
# X e Y do clique sao pixels dentro da janela em foco, os mesmos dos prints de prints_rec.py.
import ctypes
import sys
import time
from ctypes import wintypes

user32 = ctypes.windll.user32
user32.SetProcessDPIAware()
TECLAS = {'W': 0x57, 'A': 0x41, 'ESC': 0x1B, 'F9': 0x78, 'F10': 0x79}


def em_foco(pid):
    janela = user32.GetForegroundWindow()
    dono = ctypes.c_ulong()
    user32.GetWindowThreadProcessId(janela, ctypes.byref(dono))
    return dono.value == pid


def clicar(x, y):
    r = wintypes.RECT()
    user32.GetWindowRect(user32.GetForegroundWindow(), ctypes.byref(r))
    user32.SetCursorPos(r.left + x, r.top + y)
    time.sleep(0.3)
    user32.mouse_event(2, 0, 0, 0, 0)
    time.sleep(0.05)
    user32.mouse_event(4, 0, 0, 0, 0)


def main():
    pid, log = int(sys.argv[1]), sys.argv[2]
    with open(log, 'a') as f:
        for passo in sys.argv[3:]:
            nome, segundos = passo.split(':')
            if nome == 'espera':
                time.sleep(float(segundos))
                continue
            for _ in range(40):
                if em_foco(pid):
                    break
                time.sleep(0.1)
            if not em_foco(pid):
                f.write('sem foco, parei em %s\n' % passo)
                return
            if nome.startswith('clique_'):
                clicar(*[int(v) for v in nome.split('_')[1:]])
                time.sleep(float(segundos))
                f.write('cliquei %s\n' % passo)
                continue
            tecla = TECLAS[nome]
            user32.keybd_event(tecla, user32.MapVirtualKeyW(tecla, 0), 0, 0)
            time.sleep(float(segundos))
            user32.keybd_event(tecla, user32.MapVirtualKeyW(tecla, 0), 2, 0)
            f.write('apertei %s\n' % passo)


main()
