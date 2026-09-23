# Teste M3: filtro customizado de indice 0 com o Lens Flare nativo ligado (slot interno 17 antes do fix)
# e removeFilter negativo. Controller Python (modo Module) "m3_filtros.rodar", Sensor Always (pulse off).
# Gere o .range com criar_m3.py (RangeEngine.exe -b --python criar_m3.py).
from bge import logic

FRAG = "uniform sampler2D bgl_RenderedTexture;\nvoid main() { gl_FragColor = texture2D(bgl_RenderedTexture, gl_TexCoord[0].st); }\n"


def rodar(cont):
    try:
        _rodar(cont)
    except Exception:
        import traceback
        print("[m3] EXCECAO", traceback.format_exc())
    logic.endGame()


def _rodar(cont):
    fm = logic.getCurrentScene().filterManager
    r = []
    try:
        f0 = fm.addFilter(0, logic.RAS_2DFILTER_CUSTOMFILTER, FRAG)
        r.append(("addFilter(0) com Lens Flare ligado", f0 is not None))
    except Exception as e:
        f0 = None
        r.append(("addFilter(0) com Lens Flare ligado", "EXC %s" % e))
    r.append(("getFilter(0) e o filtro criado", f0 is not None and fm.getFilter(0) is f0))
    try:
        fm.removeFilter(-1)
        r.append(("removeFilter(-1) rejeitado", False))
    except ValueError:
        r.append(("removeFilter(-1) rejeitado", True))
    fm.removeFilter(0)
    r.append(("getFilter(0) vazio apos removeFilter(0)", fm.getFilter(0) is None))
    ok = all(v is True for _, v in r)
    for k, v in r:
        print("[m3] %-45s %s" % (k, v))
    print("[m3] RESULTADO", "OK" if ok else "FALHOU")
