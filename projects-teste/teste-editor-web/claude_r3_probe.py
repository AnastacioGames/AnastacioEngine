# Sonda R3 (Claude): arquivo de audio invalido no Web. Espera-se nenhum abort; hoje "corrompido + volume + play" da segmentation fault.
import aud
from bge import logic
_n = [0]
def rodar(cont):
    _n[0] += 1
    if _n[0] != 3:
        return
    open('/lixo.wav', 'wb').write(b'not a real audio file at all')
    open('/riff_ruim.wav', 'wb').write(b'RIFF' + bytes(4) + b'WAVEjunkjunkjunk')
    casos = [
        ("arquivo inexistente + play", lambda: aud.Device().play(aud.Sound.file('/nao_existe.wav'))),
        ("arquivo corrompido + play", lambda: aud.Device().play(aud.Sound.file('/lixo.wav'))),
        ("corrompido + volume + play", lambda: aud.Device().play(aud.Sound.file('/lixo.wav').volume(0.5))),
        ("corrompido .length", lambda: aud.Sound.file('/lixo.wav').length),
        ("corrompido .specs", lambda: aud.Sound.file('/lixo.wav').specs),
        ("corrompido + limit + play", lambda: aud.Device().play(aud.Sound.file('/lixo.wav').limit(0, 1))),
        ("corrompido + pitch + length", lambda: aud.Sound.file('/lixo.wav').pitch(2.0).length),
        ("inexistente + volume + specs", lambda: aud.Sound.file('/nao_existe.wav').volume(0.5).specs),
        ("RIFF/WAVE quebrado + play", lambda: aud.Device().play(aud.Sound.file('/riff_ruim.wav'))),
        ("RIFF/WAVE quebrado + volume + length", lambda: aud.Sound.file('/riff_ruim.wav').volume(0.5).length),
    ]
    for nome, f in casos:
        print("[r3] INICIO", nome, flush=True)
        try:
            print("[r3] FIM", nome, "->", f(), flush=True)
        except BaseException as e:
            print("[r3] EXC", nome, type(e).__name__, e, flush=True)
    print("[r3] TODOS", flush=True)
    logic.endGame()
