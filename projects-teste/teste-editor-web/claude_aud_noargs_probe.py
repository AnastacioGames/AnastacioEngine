# Controle: metodos METH_NOARGS do modulo aud com som VALIDO. Se "function signature mismatch", o bug e geral
# (assinatura (X* self) chamada com 2 argumentos no Wasm) e nao tem relacao com audio invalido.
import aud
from bge import logic
_n = [0]
def rodar(cont):
    _n[0] += 1
    if _n[0] != 3:
        return
    casos = [
        ("seno .cache()", lambda: aud.Sound.sine(440).limit(0, 1).cache()),
        ("seno .reverse()", lambda: aud.Sound.sine(440).limit(0, 1).reverse()),
        ("handle.pause()", lambda: aud.Device().play(aud.Sound.sine(440)).pause()),
        ("handle.stop()", lambda: aud.Device().play(aud.Sound.sine(440)).stop()),
    ]
    for nome, f in casos:
        print("[r3] INICIO", nome, flush=True)
        try:
            print("[r3] FIM", nome, "->", f(), flush=True)
        except BaseException as e:
            print("[r3] EXC", nome, type(e).__name__, e, flush=True)
    print("[r3] TODOS", flush=True)
    logic.endGame()
