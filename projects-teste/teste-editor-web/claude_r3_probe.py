# Sonda R3 (Claude): arquivo de audio invalido no Web. Espera-se nenhum abort; hoje "corrompido + volume + play" da segmentation fault.
import aud
from bge import logic
_n = [0]
def rodar(cont):
    _n[0] += 1
    if _n[0] != 3:
        return
    open('/lixo.wav', 'wb').write(b'not a real audio file at all')
    casos = [
        ("arquivo inexistente + play", lambda: aud.Device().play(aud.Sound.file('/nao_existe.wav'))),
        ("arquivo corrompido + play", lambda: aud.Device().play(aud.Sound.file('/lixo.wav'))),
        ("corrompido + volume + play", lambda: aud.Device().play(aud.Sound.file('/lixo.wav').volume(0.5))),
        ("corrompido .length", lambda: aud.Sound.file('/lixo.wav').length),
        ("corrompido .specs", lambda: aud.Sound.file('/lixo.wav').specs),
    ]
    for nome, f in casos:
        print("[r3] INICIO", nome, flush=True)
        try:
            print("[r3] FIM", nome, "->", f(), flush=True)
        except BaseException as e:
            print("[r3] EXC", nome, type(e).__name__, e, flush=True)
    print("[r3] TODOS", flush=True)
    logic.endGame()
