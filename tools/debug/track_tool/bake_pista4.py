# Cozinha o dado de jogo da Pista_4 numa CÓPIA do RolimaRacer (nunca no original).
#
#   copy D:\ProjetoRolimaRacer\RolimaRacer.range artifacts\track_tool\runtime\RolimaRacer.range
#   build\bin\AnastacioEngine.exe -b artifacts\track_tool\runtime\RolimaRacer.range ^
#       --python tools\debug\track_tool\bake_pista4.py
#
# Converte Pista4_Track (Curve + Array) em traçado se ainda não for, roda bake(), confere a leitura
# (bpy.data e import do Text .py), grava o JSON em artifacts\track_tool\runtime\pista4_track.json
# e salva a cópia como RolimaRacer_track.range (para o teste no jogo: run_game_test.py).
import os
import sys
import time

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
MODULES = os.path.join(ROOT, "source", "release", "scripts", "modules")
OUT = os.path.join(ROOT, "artifacts", "track_tool", "runtime")

src = os.path.normcase(os.path.abspath(bpy.data.filepath))
if "projetorolimaracer" in src:
    raise SystemExit("ERRO: abra a cópia em artifacts, não o original")

sys.path.insert(0, MODULES)
for m in [m for m in sys.modules if m == "range_track" or m.startswith("range_track.")]:
    del sys.modules[m]
import range_track  # noqa: E402
from range_track import bake, props, runtime  # noqa: E402

print("range_track de", os.path.dirname(range_track.__file__))
props.register()
curve = bpy.data.objects["Pista4_Curve"]
mesh = bpy.data.objects["Pista4_Track"]
if not curve.range_track.enabled:
    from range_track import convert
    t0 = time.perf_counter()
    curve = convert.convert_curve_array(mesh)
    print("convert: %.2f s -> %s" % (time.perf_counter() - t0, curve.name))

t0 = time.perf_counter()
name = bake.bake(curve)
dt = time.perf_counter() - t0
txt = bpy.data.texts[name]
text = txt.as_string()
print("BAKE %s em %.2f s, %d bytes" % (name, dt, len(text)))
print("Texts:", [t.name for t in bpy.data.texts if t.name.startswith("TRACK_")])

tr = runtime.get("Pista4_Curve")
print("GET (bpy.data):", tr)
import builtins  # noqa: E402
mod = builtins.__import__(runtime.module_name("Pista4_Curve"))
print("IMPORT do Text .py:", mod.__name__, "DATA == JSON:", mod.DATA == text)

# tempo da linha ideal sozinha
from range_track import racing  # noqa: E402
t0 = time.perf_counter()
racing.racing_line(tr._px, tr._py, tr._lx, tr._ly, tr._wl, tr._wr, tr.cyclic)
print("racing_line %d amostras (%.0f m): %.2f s" % (tr.count, tr.length, time.perf_counter() - t0))

os.makedirs(OUT, exist_ok=True)
with open(os.path.join(OUT, "pista4_track.json"), "w", encoding="utf-8", newline="\n") as f:
    f.write(text)

# testes do runtime com mathutils (Python da engine)
sys.argv = [sys.argv[0], "--", "--track", os.path.join(OUT, "pista4_track.json"), "--prefix", "pista4"]
sys.path.insert(0, HERE)
import test_runtime  # noqa: E402
rc = test_runtime.main()

dst = os.path.join(OUT, "RolimaRacer_track.range")
bpy.ops.wm.save_as_mainfile(filepath=dst, copy=True)
print("SALVO", dst, "rc", rc)
