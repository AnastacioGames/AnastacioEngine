"""M3 Web: liga Bloom, redimensiona duas vezes e deixa o runtime emitir o trace WebGL.

O verificador deve injetar ``window.RAS_2DFILTER_DEBUG = true`` antes de clicar
em Jogar.  O log [web-filter] precisa conter os passes Bloom depois de cada
resize, sem ``glError`` diferente de 0.
"""
from bge import logic, render


SIZES = ((320, 240), (960, 540))


def rodar(cont):
    own = cont.owner
    step = own.get("m3_step", 0)
    try:
        fm = logic.getCurrentScene().filterManager
        if step == 0:
            fm.changeBloomValues(1, 1.5, 0.60)
            print("[m3-bloom] Bloom ligado")
        elif 1 <= step <= len(SIZES):
            width, height = SIZES[step - 1]
            render.setWindowSize(width, height)
            print("[m3-bloom] setWindowSize(%d, %d)" % (width, height))
        elif step == len(SIZES) + 20:
            print("[m3-bloom] RESULTADO OK; confira [web-filter] Bloom e glError=0x0")
            logic.endGame()
        own["m3_step"] = step + 1
    except Exception:
        import traceback
        print("[m3-bloom] EXCECAO " + traceback.format_exc())
        logic.endGame()
