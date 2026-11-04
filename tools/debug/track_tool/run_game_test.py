# Prepara o teste de range_track.runtime no jogo de verdade (player sem janela, --server).
#
#   build\bin\AnastacioEngine.exe -b artifacts\track_tool\runtime\RolimaRacer_track.range ^
#       --python tools\debug\track_tool\run_game_test.py
#   build\bin\AnastacioRuntime.exe --server artifacts\track_tool\runtime\RolimaRacer_tracktest.range
#   -> artifacts\track_tool\runtime\game_test.log
#
# Usa a cópia já cozida por bake_pista4.py (Texts TRACK_Pista4_Curve.json/.py). Cria a cena
# "TrackTest" (câmera + empty com Always -> Python Module track_game_test.tick), deixa ela como
# cena inicial e salva como RolimaRacer_tracktest.range. No jogo o script importa
# range_track.runtime (scripts/modules do player), chama get("Pista4_Curve"), confere os vetores
# de tools/debug/track_tool/ref/pista4_queries.json, mede project() e, se existir, compara com
# Range.track (C++). Grava o log e chama Range.logic.endGame().
import os

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
OUT = os.path.join(ROOT, "artifacts", "track_tool", "runtime")
LOG = os.path.join(OUT, "game_test.log")
REF = os.path.join(OUT, "pista4_queries_novo.json")  # do bake atual da cópia

if "projetorolimaracer" in os.path.normcase(os.path.abspath(bpy.data.filepath)):
    raise SystemExit("ERRO: abra a cópia em artifacts, não o original")
assert "TRACK_Pista4_Curve.py" in bpy.data.texts, "rode bake_pista4.py antes"

GAME_SCRIPT = r'''
import json
import math
import sys
import time
import traceback

import Range

LOG = %(log)r
REF = %(ref)r
NAME = "Pista4_Curve"


def _cmp(tr, ref, lines, label):
    worst = {}
    bad = []

    def w(key, v):
        worst[key] = max(worst.get(key, 0.0), v)

    for e in ref["pos_queries"]:
        s, side, dist = tr.project(e["pos"])
        es, eside, edist = e["project"]
        ds = abs(s - es)
        if ref["cyclic"]:
            ds = min(ds, ref["length"] - ds)
        w("project.s", ds)
        w("project.dist", abs(dist - edist))
        if side != eside and edist > 1e-3:
            bad.append(("side", e["pos"], side, eside))
        if bool(tr.isOnRoad(e["pos"])) != e["isOnRoad"]:
            bad.append(("isOnRoad", e["pos"]))
    for e in ref["s_queries"]:
        s = e["s"]
        for key in ("pointAt", "tangentAt", "racingLine", "widthAt"):
            got = getattr(tr, key)(s)
            w(key, max(abs(a - b) for a, b in zip(got, e[key])))
        w("bankAt", abs(tr.bankAt(s) - e["bankAt"]))
        if tr.surfaceAt(s) != e["surfaceAt"]:
            bad.append(("surfaceAt", s, tr.surfaceAt(s), e["surfaceAt"]))
    ok = all(v <= 1e-3 for v in worst.values()) and not bad
    lines.append("%%s: %%s" %% (label, "OK (tolerância 1 mm)" if ok else "DIFERENTE"))
    for k in sorted(worst):
        lines.append("  %%-16s erro máx %%.2e" %% (k, worst[k]))
    for b in bad[:10]:
        lines.append("  ruim: %%r" %% (b,))
    if len(bad) > 10:
        lines.append("  ... %%d itens ruins" %% len(bad))
    return ok


def _perf(tr, lines, label):
    pts = []
    for car in range(20):
        u = -2.0 + 0.2 * car
        for k in range(1000):
            s = (car * 90.0 + k * 0.45) %% tr.length
            p = tr.pointAt(s)
            pts.append((p[0], p[1] + 0.0, p[2] + 0.6))
    t0 = time.perf_counter()
    for p in pts:
        tr.project(p)
    dt = time.perf_counter() - t0
    lines.append("%%s: project %%.4f ms por chamada (20 carros x 1000)" %% (label, dt / len(pts) * 1000.0))


def tick(cont):
    own = cont.owner
    if own.get("done"):
        return
    own["done"] = True
    lines = ["Python %%s" %% sys.version.split()[0], "bpy importado: %%s" %% ("bpy" in sys.modules)]
    try:
        import builtins
        import range_track.runtime as rt
        lines.append("range_track.runtime de %%s" %% rt.__file__)
        mod = builtins.__import__(rt.module_name(NAME))
        lines.append("import do Text %%s.py: ok, DATA com %%d bytes" %% (mod.__name__, len(mod.DATA)))
        t0 = time.perf_counter()
        tr = rt.get(NAME)
        lines.append("get(%%r) = %%r em %%.1f ms" %% (NAME, tr, (time.perf_counter() - t0) * 1000.0))
        t0 = time.perf_counter()
        tr2 = rt.get(NAME)
        lines.append("get de novo (cache): %%s, %%.3f ms" %% (tr2 is tr, (time.perf_counter() - t0) * 1000.0))
        p = tr.pointAt(500.0)
        lines.append("pointAt(500) = %%r; project = %%r" %% (tuple(round(v, 3) for v in p), tr.project(p)))
        lines.append("tangentAt(500) = %%r bankAt = %%.4f widthAt = %%r surfaceAt = %%r" %% (
            tuple(round(v, 3) for v in tr.tangentAt(500.0)), tr.bankAt(500.0), tr.widthAt(500.0),
            tr.surfaceAt(500.0)))
        lines.append("racingLine(500) = %%r isOnRoad(racingLine) = %%s" %% (
            tuple(round(v, 3) for v in tr.racingLine(500.0)), tr.isOnRoad(tr.racingLine(500.0))))
        with open(REF, encoding="utf-8") as f:
            ref = json.load(f)
        _cmp(tr, ref, lines, "runtime.py x vetores")
        _perf(tr, lines, "runtime.py")
        rtrack = getattr(Range, "track", None)
        if rtrack is None:
            lines.append("Range.track: não existe neste build")
        else:
            tc = rtrack.get(NAME)
            lines.append("Range.track.get = %%r" %% (tc,))
            if tc is not None:
                _cmp(tc, ref, lines, "Range.track (C++) x vetores")
                _perf(tc, lines, "Range.track (C++)")
    except Exception:
        lines.append(traceback.format_exc())
    lines.append("# fim")
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join("[track test] " + l for l in lines))
    Range.logic.endGame()
''' % {"log": LOG, "ref": REF}

txt = bpy.data.texts.get("track_game_test.py") or bpy.data.texts.new("track_game_test.py")
txt.clear()
txt.write(GAME_SCRIPT)

sc = bpy.data.scenes.get("TrackTest") or bpy.data.scenes.new("TrackTest")
sc.render.engine = 'BLENDER_GAME'
for ob in list(sc.objects):
    sc.objects.unlink(ob)
cam = bpy.data.objects.new("TrackTestCam", bpy.data.cameras.new("TrackTestCam"))
sc.objects.link(cam)
sc.camera = cam
emp = bpy.data.objects.new("TrackTestRunner", None)
sc.objects.link(emp)
sc.objects.active = emp
bpy.context.screen.scene = sc
bpy.ops.logic.sensor_add(type='ALWAYS', name='Always', object=emp.name)
bpy.ops.logic.controller_add(type='PYTHON', name='Py', object=emp.name)
sens = emp.game.sensors['Always']
sens.use_pulse_true_level = True
cont = emp.game.controllers['Py']
cont.mode = 'MODULE'
cont.module = 'track_game_test.tick'
sens.link(cont)

dst = os.path.join(OUT, "RolimaRacer_tracktest.range")
bpy.ops.wm.save_as_mainfile(filepath=dst, copy=True)
print("SALVO", dst, "cena", bpy.context.screen.scene.name)
