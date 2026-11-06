# Aperta teclas no jogo do Rec Play, de fora do processo, porque na contagem a logica do jogo esta parada.
# So aperta com a janela do editor em foco, para nao digitar em outro programa.
#   python teclas_rec.py <pid> <arquivo de log> <tecla:segundos ou espera:segundos> ...
import ctypes
import sys
import time

user32 = ctypes.windll.user32
TECLAS = {'W': 0x57, 'A': 0x41, 'ESC': 0x1B, 'F10': 0x79}


def em_foco(pid):
    janela = user32.GetForegroundWindow()
    dono = ctypes.c_ulong()
    user32.GetWindowThreadProcessId(janela, ctypes.byref(dono))
    return dono.value == pid


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
            tecla = TECLAS[nome]
            user32.keybd_event(tecla, user32.MapVirtualKeyW(tecla, 0), 0, 0)
            time.sleep(float(segundos))
            user32.keybd_event(tecla, user32.MapVirtualKeyW(tecla, 0), 2, 0)
            f.write('apertei %s\n' % passo)


main()
