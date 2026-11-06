# Tira prints da janela de um processo enquanto ele vive, para conferir depois um teste com janela.
# So captura com a janela em foco: a area da tela nunca mostra outro programa.
#   python prints_rec.py <pid> <pasta> [segundos entre prints]
import ctypes
import hashlib
import os
import sys
import time
from ctypes import wintypes
from PIL import ImageGrab

user32 = ctypes.windll.user32
user32.SetProcessDPIAware()
kernel32 = ctypes.windll.kernel32


def vivo(pid):
    h = kernel32.OpenProcess(0x1000, False, pid)
    if not h:
        return False
    codigo = wintypes.DWORD()
    kernel32.GetExitCodeProcess(h, ctypes.byref(codigo))
    kernel32.CloseHandle(h)
    return codigo.value == 259


def janela_em_foco(pid):
    janela = user32.GetForegroundWindow()
    dono = wintypes.DWORD()
    user32.GetWindowThreadProcessId(janela, ctypes.byref(dono))
    return janela if dono.value == pid else None


def main():
    pid, pasta = int(sys.argv[1]), sys.argv[2]
    passo = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
    os.makedirs(pasta, exist_ok=True)
    inicio, anterior, n = time.time(), None, 0
    while vivo(pid):
        janela = janela_em_foco(pid)
        if janela:
            r = wintypes.RECT()
            user32.GetWindowRect(janela, ctypes.byref(r))
            if r.right > r.left and r.bottom > r.top:
                img = ImageGrab.grab(bbox=(max(r.left, 0), max(r.top, 0), r.right, r.bottom), all_screens=True)
                marca = hashlib.md5(img.tobytes()).digest()
                if marca != anterior:
                    anterior = marca
                    n += 1
                    img.save(os.path.join(pasta, '%03d_%05.1fs.png' % (n, time.time() - inicio)))
        time.sleep(passo)


main()
