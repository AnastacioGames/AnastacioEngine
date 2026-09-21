# Teste M3 (Claude): bloom ligado + redimensionar a janela + resolucao dinamica sem timer de GPU.
# Controller Python (modo Module) "claude_m3_resize.rodar", Sensor Always com pulso ligado.
# Marcadores "[m3r] FASE ..." no console; as linhas "[web-filter] ... offScreenSize=WxH glError=..." vem do C++
# (exige window.RAS_2DFILTER_DEBUG = true, feito pelo claude_m3_resize.cjs).
from bge import logic, render

FASES = {
    5: ("bloom_on", None),
    25: ("resize_640x360", (640, 360)),
    45: ("resize_1024x600", (1024, 600)),
    65: ("resize_400x300", (400, 300)),
    85: ("resize_960x540", (960, 540)),
}
_frame = [0]


def rodar(cont):
    _frame[0] += 1
    f = _frame[0]
    try:
        if f == 1:
            print("[m3r] FASE inicio window=%dx%d" % (render.getWindowWidth(), render.getWindowHeight()))
        if f == 5:
            logic.getCurrentScene().filterManager.changeBloomValues(1, 1.0, 0.5)
            print("[m3r] FASE bloom_on")
        elif f in FASES and FASES[f][1]:
            w, h = FASES[f][1]
            render.setWindowSize(w, h)
            print("[m3r] FASE %s" % FASES[f][0])
        elif f % 10 == 9 and f < 100:
            print("[m3r] FASE frame=%d window=%dx%d" % (f, render.getWindowWidth(), render.getWindowHeight()))
        elif f == 100:
            print("[m3r] FASE FIM")
            logic.endGame()
    except Exception:
        import traceback
        print("[m3r] EXCECAO", traceback.format_exc())
        logic.endGame()
