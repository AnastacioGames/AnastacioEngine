# Aperta teclas no jogo do Rec Play, de fora do processo, porque na contagem a logica do jogo esta parada.
# So aperta com a janela do editor em foco, para nao digitar em outro programa.
#   python teclas_rec.py <pid> <arquivo de log> <tecla:segundos, espera:segundos, foco:segundos, clique_X_Y:segundos ou arrasta_X1_Y1_X2_Y2:segundos> ...
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


def area(janela):
    r = wintypes.RECT()
    user32.GetWindowRect(ctypes.c_void_p(janela), ctypes.byref(r))
    return (r.right - r.left) * (r.bottom - r.top)


def trazer_para_frente(pid):
    # Uma janela nova do processo pode nascer sem foco; EnumWindows vem na ordem de empilhamento.
    achadas = []

    def ver(janela, _):
        dono = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(janela, ctypes.byref(dono))
        if dono.value == pid and user32.IsWindowVisible(janela) and user32.GetWindowTextLengthW(janela):
            achadas.append(janela)
        return True

    tipo = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    user32.EnumWindows(tipo(ver), 0)
    if achadas:
        # A menor e o Rec Studio, quando ele ja abriu ao lado da janela principal.
        achadas.sort(key=area)
        user32.keybd_event(0x87, 0, 0, 0)  # F24: o Windows so libera o foco depois de uma tecla; ALT abriria o menu
        if len(achadas) > 1:
            # Os cliques usam pixels fixos, entao o Rec Studio precisa ter sempre o mesmo tamanho.
            user32.MoveWindow(ctypes.c_void_p(achadas[0]), 0, 0, 1668, 1092, True)
        user32.SetForegroundWindow(ctypes.c_void_p(achadas[0]))
        user32.keybd_event(0x87, 0, 2, 0)


def clicar(x, y):
    r = wintypes.RECT()
    user32.GetWindowRect(user32.GetForegroundWindow(), ctypes.byref(r))
    user32.SetCursorPos(r.left + x, r.top + y)
    time.sleep(0.3)
    user32.mouse_event(2, 0, 0, 0, 0)
    time.sleep(0.05)
    user32.mouse_event(4, 0, 0, 0, 0)


def arrastar(x1, y1, x2, y2):
    r = wintypes.RECT()
    user32.GetWindowRect(user32.GetForegroundWindow(), ctypes.byref(r))
    user32.SetCursorPos(r.left + x1, r.top + y1)
    time.sleep(0.4)
    user32.mouse_event(2, 0, 0, 0, 0)
    time.sleep(0.2)
    # Comeca devagar como a mao: um salto grande no primeiro evento vira selecao por caixa em vez de arraste.
    passos = 120
    for i in range(1, passos + 1):
        user32.SetCursorPos(r.left + x1 + (x2 - x1) * i // passos, r.top + y1 + (y2 - y1) * i // passos)
        time.sleep(0.015)
    time.sleep(0.3)
    user32.mouse_event(4, 0, 0, 0, 0)


def main():
    pid, log = int(sys.argv[1]), sys.argv[2]
    with open(log, 'a') as f:
        for passo in sys.argv[3:]:
            nome, segundos = passo.split(':')
            if nome == 'espera':
                time.sleep(float(segundos))
                continue
            if nome == 'foco':
                trazer_para_frente(pid)
                time.sleep(float(segundos))
                continue
            for tentativa in range(40):
                if em_foco(pid):
                    break
                if tentativa % 10 == 0:
                    trazer_para_frente(pid)
                time.sleep(0.1)
            if not em_foco(pid):
                f.write('sem foco, parei em %s\n' % passo)
                return
            if nome.startswith('arrasta_'):
                arrastar(*[int(v) for v in nome.split('_')[1:]])
                time.sleep(float(segundos))
                f.write('arrastei %s\n' % passo)
                continue
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
