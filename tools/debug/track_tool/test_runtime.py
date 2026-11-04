# Testes do dado de jogo do Track Tool (range_track.runtime / racing / bake.build_data).
#
# Roda com o Python do sistema (sem bpy) ou dentro da engine:
#   python tools/debug/track_tool/test_runtime.py                      # pistas sintéticas
#   python tools/debug/track_tool/test_runtime.py --write-ref          # + grava ref/track_ref.json e ref/ref_queries.json
#   python tools/debug/track_tool/test_runtime.py --track X.json --write-ref --prefix pista4
#                                                                      # testa uma pista cozida e grava ref/pista4_*.json
#
# Vetores de referência (para o Range.track em C++ comparar, tolerância 1 mm):
#   ref/track_ref.json    pista cozida (formato v1), sintética cíclica (morro, grampo, inclinação)
#   ref/ref_queries.json  {"track": "track_ref.json", "pos_queries": [...], "s_queries": [...]}
#     pos_queries[k] = {"pos": [x,y,z], "project": [s, side, dist], "isOnRoad": bool}
#     s_queries[k]   = {"s": s, "pointAt": [..], "tangentAt": [..], "bankAt": b, "widthAt": [l, r],
#                       "racingLine": [..], "surfaceAt": "nome"}
#   Em pista cíclica, compare s de project() pela diferença com volta (s ~ 0 e s ~ length são vizinhos).
import argparse
import json
import math
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
MODULES = os.path.join(ROOT, "source", "release", "scripts", "modules")
if MODULES not in sys.path:
    sys.path.insert(0, MODULES)

from range_track import bake, racing, runtime  # noqa: E402

FAILS = []


def check(cond, msg):
    if not cond:
        FAILS.append(msg)
        print("FALHA:", msg)


# ------------------------------------------------------------------ pistas sintéticas

def _resample(dense, step, cyclic):
    """Polilinha densa -> amostras a cada ~step metros (passo ajustado para dividir o total)."""
    pts = list(dense)
    if cyclic:
        pts.append(pts[0])
    cum = [0.0]
    for a, b in zip(pts[:-1], pts[1:]):
        cum.append(cum[-1] + math.dist(a, b))
    total = cum[-1]
    nseg = max(1, int(round(total / step)))
    st = total / nseg
    count = nseg if cyclic else nseg + 1
    out = []
    ss = []
    j = 0
    for k in range(count):
        s = k * st
        while j < len(pts) - 2 and cum[j + 1] < s:
            j += 1
        seg = cum[j + 1] - cum[j]
        t = (s - cum[j]) / seg if seg > 0 else 0.0
        t = min(max(t, 0.0), 1.0)
        a, b = pts[j], pts[j + 1]
        out.append(tuple(a[c] + (b[c] - a[c]) * t for c in range(3)))
        ss.append(s)
    return ss, out, total, st


def _frames_like(ss, pos, total, st, cyclic, width_fn, surf_fn):
    n = len(pos)
    tan, lat, turn = [], [], []
    for i in range(n):
        if cyclic:
            a, b = pos[(i - 1) % n], pos[(i + 1) % n]
        else:
            a, b = pos[max(0, i - 1)], pos[min(n - 1, i + 1)]
        d = [b[c] - a[c] for c in range(3)]
        ll = math.sqrt(sum(v * v for v in d))
        d = [v / ll for v in d]
        tan.append(tuple(d))
        h = math.hypot(d[0], d[1])
        lat.append((-d[1] / h, d[0] / h, 0.0))
    w = 12
    for i in range(n):
        ia = (i - w) % n if cyclic else max(0, i - w)
        ib = (i + w) % n if cyclic else min(n - 1, i + w)
        ta, tb = lat[ia], lat[ib]
        turn.append(math.degrees(math.atan2(ta[0] * tb[1] - ta[1] * tb[0], ta[0] * tb[0] + ta[1] * tb[1])))
    bank = [math.radians(max(-6.0, min(6.0, 0.08 * t))) for t in turn]
    wl, wr, el, er, surf = [], [], [], [], []
    for s in ss:
        a, b = width_fn(s)
        wl.append(a)
        wr.append(b)
        el.append(a + 1.8)
        er.append(b + 1.8)
        surf.append(surf_fn(s))
    return tan, lat, bank, wl, wr, el, er, surf


def synthetic_cyclic():
    """Laço fechado ~1,8 km em forma de estrela (r(θ) > 0: sem cruzar), curvas fechadas e
    morro de ±12 m."""
    dense = []
    m = 6000
    for k in range(m):
        th = 2.0 * math.pi * k / m
        r = 270.0 + 70.0 * math.cos(3.0 * th) + 25.0 * math.sin(5.0 * th)
        z = 12.0 * math.sin(th) + 3.0 * math.sin(4.0 * th)
        dense.append((r * math.cos(th), r * math.sin(th), z))
    ss, pos, total, st = _resample(dense, 1.0, True)
    tan, lat, bank, wl, wr, el, er, surf = _frames_like(
        ss, pos, total, st, True,
        lambda s: (4.0 + 1.0 * math.sin(s / 60.0), 4.0 - 0.8 * math.sin(s / 45.0)),
        lambda s: "dirt" if 400.0 <= s < 520.0 else ("RoadAgua" if 900.0 <= s < 930.0 else "asphalt"))
    data = bake.build_data("SynthLoop", True, total, st, ss, pos, tan, lat, bank, wl, wr, el, er, surf)
    return data


def synthetic_bridge():
    """Oito fechado com ponte: os dois ramos se cruzam na origem com 16 m de diferença de altura."""
    dense = []
    m = 6000
    for k in range(m):
        th = 2.0 * math.pi * k / m
        dense.append((200.0 * math.sin(th), 120.0 * math.sin(th) * math.cos(th), 8.0 * math.cos(th)))
    ss, pos, total, st = _resample(dense, 1.0, True)
    tan, lat, bank, wl, wr, el, er, surf = _frames_like(
        ss, pos, total, st, True, lambda s: (4.0, 4.0), lambda s: "asphalt")
    return bake.build_data("SynthPonte", True, total, st, ss, pos, tan, lat, bank, wl, wr, el, er, surf)


def synthetic_open():
    """Descida aberta ~900 m com grampo de raio 12 m e S."""
    pieces = [(120.0, 0.0), (math.pi * 12.0, 1.0 / 12.0), (80.0, 0.0), (math.pi / 2 * 30.0, -1.0 / 30.0),
              (60.0, 0.0), (math.pi / 2 * 25.0, 1.0 / 25.0), (math.pi / 2 * 25.0, -1.0 / 25.0), (150.0, 0.0)]
    x = y = 0.0
    hd = 0.3
    dense = [(x, y, 0.0)]
    s = 0.0
    for length, k in pieces:
        nn = max(2, int(length / 0.1))
        ds = length / nn
        for _ in range(nn):
            hd += k * ds * 0.5
            x += math.cos(hd) * ds
            y += math.sin(hd) * ds
            hd += k * ds * 0.5
            s += ds
            dense.append((x, y, -0.06 * s + 2.0 * math.sin(s / 40.0)))
    ss, pos, total, st = _resample(dense, 1.0, False)
    tan, lat, bank, wl, wr, el, er, surf = _frames_like(
        ss, pos, total, st, False, lambda s: (3.5, 3.5), lambda s: "asphalt")
    return bake.build_data("SynthDescida", False, total, st, ss, pos, tan, lat, bank, wl, wr, el, er, surf)


# ------------------------------------------------------------------ testes

def sdiff(track, a, b):
    d = a - b
    if track.cyclic:
        d = (d + 0.5 * track.length) % track.length - 0.5 * track.length
    return abs(d)


def surface_point(track, s, u, h=0.0):
    p = track.pointAt(s)
    i, j, t = track._locate(s)
    lx, ly = track._lateral(i, j, t)
    b = track.bankAt(s)
    return (p[0] + u * lx, p[1] + u * ly, p[2] - u * math.tan(b) + h)


def run_tests(track, label):
    print("== %s: %r" % (label, track))
    L = track.length
    # 1. project(pointAt(s)) == s em toda a pista (passo 0,05 m)
    worst = 0.0
    n = int(L / 0.05)
    for k in range(n + 1):
        s = min(k * 0.05, L)
        r = track.project(track.pointAt(s))
        e = sdiff(track, r[0], s)
        worst = max(worst, e)
        if r[2] > 1e-6:
            worst = max(worst, r[2])
    check(worst <= 0.05, "%s: project(pointAt(s)) erro máx %.6f m" % (label, worst))
    print("  project(pointAt(s)): %d pontos, erro máx %.2e m" % (n + 1, worst))

    # 2. pontos deslocados (lateral até a borda + 2 m, altura 0..1,5 m sobre a superfície)
    rng = random.Random(7)
    worst_s = worst_d = 0.0
    bad_side = 0
    onroad_bad = 0
    m = 4000
    for _ in range(m):
        s = rng.uniform(0.0, L)
        wl, wr = track.widthAt(s)
        u = rng.uniform(-(wr + 2.0), wl + 2.0)
        h = rng.uniform(0.0, 1.5)
        p = surface_point(track, s, u, h)
        ps, side, dist = track.project(p)
        worst_s = max(worst_s, sdiff(track, ps, s))
        worst_d = max(worst_d, abs(dist - abs(u)))
        if abs(u) > 1e-6 and side != (1 if u > 0 else -1):
            bad_side += 1
        expect_on = (u >= 0 and u <= wl) or (u < 0 and -u <= wr)
        if abs(abs(u) - (wl if u >= 0 else wr)) > 1e-3 and track.isOnRoad(p) != expect_on:
            onroad_bad += 1
    check(worst_s <= 0.05, "%s: s em pontos deslocados erro máx %.4f" % (label, worst_s))
    check(worst_d <= 0.01, "%s: dist em pontos deslocados erro máx %.4f" % (label, worst_d))
    check(bad_side == 0, "%s: lado errado em %d pontos" % (label, bad_side))
    check(onroad_bad == 0, "%s: isOnRoad errado em %d pontos" % (label, onroad_bad))
    print("  deslocados: %d pontos, erro s %.2e m, erro dist %.2e m, lado errado %d, isOnRoad errado %d"
          % (m, worst_s, worst_d, bad_side, onroad_bad))

    # 3. altura: 5 m acima da superfície não está na pista
    above = sum(1 for k in range(200) if track.isOnRoad(surface_point(track, k * L / 200.0, 0.0, 5.0)))
    check(above == 0, "%s: isOnRoad com 5 m de altura em %d pontos" % (label, above))

    # 4. continuidade: s ao andar pela linha central, sem saltos (cíclica: volta suave)
    jumps = 0
    prev = None
    k = 0
    while k * 0.25 <= L + 3.0:
        s = k * 0.25
        r = track.project(surface_point(track, s, 2.5, 0.5))
        if prev is not None and sdiff(track, r[0], prev) > 0.3:
            jumps += 1
        prev = r[0]
        k += 1
    check(jumps == 0, "%s: %d saltos de s ao longo da pista" % (label, jumps))
    if track.cyclic:
        a = track.project(track.pointAt(L - 0.01))[0]
        b = track.project(track.pointAt(L + 0.01))[0]
        check(sdiff(track, a, b) < 0.03, "%s: salto no fechamento %.4f" % (label, sdiff(track, a, b)))
        print("  fechamento: s(L-0,01)=%.4f s(L+0,01)=%.4f" % (a, b))

    # 5. linha ideal dentro da pista
    out = 0
    for k in range(int(L)):
        s = float(k)
        p = track.racingLine(s)
        ps, side, dist = track.project(p)
        wl, wr = track.widthAt(ps)
        if dist > (wl if side > 0 else wr) + 1e-3 or not track.isOnRoad(p):
            out += 1
    check(out == 0, "%s: linha ideal fora da pista em %d amostras" % (label, out))
    race = track._race
    print("  linha ideal: min %.2f max %.2f, fora da pista %d" % (min(race), max(race), out))

    # 6. desempenho: 20 carros x 1000 chamadas
    rng = random.Random(3)
    cars = []
    for _ in range(20):
        s = rng.uniform(0.0, L)
        cars.append([s, rng.uniform(-2.0, 2.0)])
    pts = []
    for it in range(1000):
        for c in cars:
            c[0] = (c[0] + 0.45) % L if track.cyclic else min(c[0] + 0.45, L)
            pts.append(surface_point(track, c[0], c[1], 0.6))
    t0 = time.perf_counter()
    for p in pts:
        track.project(p)
    dt = time.perf_counter() - t0
    per = dt / len(pts) * 1000.0
    check(per < 0.05, "%s: project %.4f ms por chamada (meta < 0,05)" % (label, per))
    print("  project: %.4f ms por chamada (%d chamadas, %.1f ms)" % (per, len(pts), dt * 1000))
    t0 = time.perf_counter()
    for p in pts[:5000]:
        track.isOnRoad(p)
    print("  isOnRoad: %.4f ms por chamada" % ((time.perf_counter() - t0) / 5000 * 1000))
    # pontos longe da pista (fora da grade)
    t0 = time.perf_counter()
    for k in range(200):
        track.project((5000.0 + k, -3000.0, 0.0))
    print("  project longe (5 km): %.3f ms por chamada" % ((time.perf_counter() - t0) / 200 * 1000))


# ------------------------------------------------------------------ vetores de referência

def _rv(v):
    return [round(float(c), 9) for c in v]


def make_queries(track, seed=11, n_pos=600, n_s=300):
    rng = random.Random(seed)
    L = track.length
    pos_q = []

    def add_pos(p):
        s, side, dist = track.project(p)
        pos_q.append({"pos": _rv(p), "project": [round(s, 9), side, round(dist, 9)],
                      "isOnRoad": bool(track.isOnRoad(p))})

    for k in range(n_pos):
        s = rng.uniform(0.0, L)
        wl, wr = track.widthAt(s)
        el = track._el[track._locate(s)[0]]
        er = track._er[track._locate(s)[0]]
        u = rng.uniform(-(er + 3.0), el + 3.0)
        h = rng.choice((0.0, 0.5, 1.0, rng.uniform(-2.0, 5.0)))
        add_pos(surface_point(track, s, u, h))
    for k in range(40):  # sobre a linha central e nas amostras
        add_pos(track.pointAt(track._s[(k * 37) % track.count]))
    for k in range(20):  # longe da pista
        a = rng.uniform(0.0, 2.0 * math.pi)
        add_pos((track._px[0] + math.cos(a) * rng.uniform(50.0, 800.0),
                 track._py[0] + math.sin(a) * rng.uniform(50.0, 800.0), track._pz[0] + rng.uniform(-30.0, 30.0)))
    # posição 2D (sem z)
    p = track.pointAt(L * 0.3)
    add_pos((p[0] + 1.0, p[1] - 1.0))

    s_q = []
    svals = [rng.uniform(0.0, L) for _ in range(n_s)]
    svals += [0.0, L, -5.0, L + 5.0, L * 2.5, track._s[track.count - 1], track._s[track.count // 2],
              0.5 * (track._s[10] + track._s[11])]
    for s in svals:
        s_q.append({"s": round(s, 9), "pointAt": _rv(track.pointAt(s)), "tangentAt": _rv(track.tangentAt(s)),
                    "bankAt": round(track.bankAt(s), 9), "widthAt": _rv(track.widthAt(s)),
                    "racingLine": _rv(track.racingLine(s)), "surfaceAt": track.surfaceAt(s)})
    return {"note": "Gerado por tools/debug/track_tool/test_runtime.py com range_track.runtime "
                    "(referência). Tolerância 1 mm; em pista cíclica compare s com volta.",
            "length": track.length, "cyclic": track.cyclic,
            "pos_queries": pos_q, "s_queries": s_q}


def write_ref(track_text, track, prefix):
    out_dir = os.path.join(HERE, "ref")
    os.makedirs(out_dir, exist_ok=True)
    tname = "track_ref.json" if prefix == "synth" else "%s_track.json" % prefix
    qname = "ref_queries.json" if prefix == "synth" else "%s_queries.json" % prefix
    with open(os.path.join(out_dir, tname), "w", encoding="utf-8", newline="\n") as f:
        f.write(track_text)
    q = make_queries(track)
    q["track"] = tname
    with open(os.path.join(out_dir, qname), "w", encoding="utf-8", newline="\n") as f:
        json.dump(q, f, indent=1)
    print("  referência: %s, %s (%d posições, %d valores de s)"
          % (os.path.join(out_dir, tname), os.path.join(out_dir, qname), len(q["pos_queries"]), len(q["s_queries"])))


def check_ref_roundtrip(text, track):
    """Relê o JSON e confere os vetores (o que o C++ vai fazer)."""
    q = make_queries(track)
    t2 = runtime.Track.from_json(text)
    worst = 0.0
    for e in q["pos_queries"]:
        s, side, dist = t2.project(e["pos"])
        worst = max(worst, sdiff(t2, s, e["project"][0]), abs(dist - e["project"][2]))
        check(side == e["project"][1] and bool(t2.isOnRoad(e["pos"])) == e["isOnRoad"], "roundtrip lado/isOnRoad")
    check(worst < 1e-6, "roundtrip erro %.2e" % worst)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write-ref", action="store_true")
    ap.add_argument("--track", help="JSON v1 de uma pista cozida")
    ap.add_argument("--prefix", default="pista4")
    args = ap.parse_args([a for a in sys.argv[sys.argv.index("--") + 1:]] if "--" in sys.argv else sys.argv[1:])

    print("Python", sys.version.split()[0], "mathutils:", runtime._Vec is not tuple)
    if args.track:
        with open(args.track, encoding="utf-8") as f:
            text = f.read()
        track = runtime.Track.from_json(text)
        run_tests(track, args.prefix)
        if args.write_ref:
            write_ref(text, track, args.prefix)
    else:
        t0 = time.perf_counter()
        data = synthetic_cyclic()
        dt = time.perf_counter() - t0
        text = bake.to_json(data)
        print("bake sintético cíclico (%d amostras, inclui linha ideal): %.2f s" % (data["count"], dt))
        track = runtime.Track.from_json(text)
        t0 = time.perf_counter()
        runtime.Track.from_json(text)
        print("from_json: %.1f ms" % ((time.perf_counter() - t0) * 1000))
        run_tests(track, "SynthLoop")
        check_ref_roundtrip(text, track)
        if args.write_ref:
            write_ref(text, track, "synth")
        # linha ideal 2 km: tempo
        t0 = time.perf_counter()
        racing.racing_line(track._px, track._py, track._lx, track._ly, track._wl, track._wr, True)
        print("racing_line (%d amostras): %.2f s" % (track.count, time.perf_counter() - t0))

        data = synthetic_bridge()
        track = runtime.Track.from_json(bake.to_json(data))
        run_tests(track, "SynthPonte")

        data = synthetic_open()
        text = bake.to_json(data)
        track = runtime.Track.from_json(text)
        run_tests(track, "SynthDescida")
        # Text importável: o DATA tem que reproduzir o JSON
        ns = {}
        exec(bake.to_module(text), ns)
        check(ns["DATA"] == text, "to_module não reproduz o JSON")
        check(runtime.module_name("Pista 4.x") == "TRACK_Pista_4_x", "module_name")

    print("RESULTADO:", "OK" if not FAILS else "%d FALHA(S)" % len(FAILS))
    return 0 if not FAILS else 1


if __name__ == "__main__":
    rc = main()
    if "bpy" not in sys.modules:
        sys.exit(rc)
