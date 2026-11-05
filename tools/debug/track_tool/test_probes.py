# Testes headless do plano de Light Probe Volumes do Track Tool (range_track/probes.py).
#
# Uso:
#   AnastacioEngine.exe -b --factory-startup --python tools/debug/track_tool/test_probes.py
#   AnastacioEngine.exe -b <copia RolimaRacer.range> --python tools/debug/track_tool/test_probes.py -- Pista_4
# Nunca salva o arquivo aberto.
import math
import os
import sys

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..",
                   "source", "release", "scripts", "modules")
sys.path.insert(0, os.path.normpath(SRC))

import bpy  # noqa: E402

for m in [k for k in sys.modules if k == "range_track" or k.startswith("range_track.")]:
    del sys.modules[m]
from range_track import props, frames as frames_mod, layout, probes  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
FAILS = []


def check(cond, msg):
    print(("OK   " if cond else "FAIL ") + msg)
    if not cond:
        FAILS.append(msg)


def make_curve(scene, name, pts, cyclic=False):
    cd = bpy.data.curves.new(name, 'CURVE')
    cd.dimensions = '3D'
    sp = cd.splines.new('BEZIER')
    sp.bezier_points.add(len(pts) - 1)
    for bp, p in zip(sp.bezier_points, pts):
        bp.co = p
        bp.handle_left_type = bp.handle_right_type = 'AUTO'
    sp.use_cyclic_u = cyclic
    ob = bpy.data.objects.new(name, cd)
    scene.objects.link(ob)
    ob.range_track.enabled = True
    ob.range_track.profile = "Rua de bairro"
    return ob


def frames_of(ob):
    prof = props.find_profile(ob.range_track.profile, bpy.context.scene)
    fr = frames_mod.sample(ob, ob.range_track, prof)
    return fr, layout.band_edges(fr, prof, ob.range_track)


def report(name, fr, res):
    print("%s: len %.0f m, %s" % (name, fr.length, res.text()))
    for b in res.boxes:
        print("   s %6.1f-%6.1f  size %5.1f x %5.1f x %4.1f  dims %s  %d" %
              (b.s0, b.s1, b.size[0], b.size[1], b.size[2], b.dims, b.probes))
    for w in res.warnings:
        print("   aviso:", w)


def common_checks(name, fr, ed, res, cfg):
    miss = probes.uncovered(fr, ed, res)
    check(not miss, "%s: cobertura total (%d amostras fora)" % (name, len(miss)))
    check(all(not b.grown for b in res.boxes), "%s: nenhuma caixa passa do limite da qualidade" % name)
    # Grade alinhada: as sondas caem em múltiplos do espaçamento no mundo.
    worst = 0.0
    for b in res.boxes:
        for k in range(3):
            step = b.size[k] / (b.dims[k] - 1)
            worst = max(worst, abs(step - cfg.spacing))
            off = b.bmin[k] / cfg.spacing
            worst = max(worst, abs(off - round(off)) * cfg.spacing)
    check(worst < 0.01, "%s: sondas no múltiplo do espaçamento (erro %.4f m)" % (name, worst))
    # Vizinhas se sobrepõem (sem fresta entre caixas).
    gaps = 0
    for a, b in zip(res.boxes, res.boxes[1:]):
        inter = [min(a.bmax[k], b.bmax[k]) - max(a.bmin[k], b.bmin[k]) for k in range(3)]
        if min(inter) <= 0.0:
            gaps += 1
    check(gaps == 0, "%s: caixas vizinhas se sobrepõem (%d frestas)" % (name, gaps))


def test_synthetic():
    props.register()
    sc = bpy.context.scene
    props.default_profiles(sc)
    cfg = probes.Config(spacing=4.0, quality='HIGH')

    # Reta no eixo X x reta diagonal do mesmo comprimento.
    rx = make_curve(sc, "RetaX", [(0, 0, 0), (100, 0, 0), (200, 0, 0)])
    rd = make_curve(sc, "RetaD", [(0, 0, 0), (70.71, 70.71, 0), (141.42, 141.42, 0)])
    fx, ex = frames_of(rx)
    fd, edd = frames_of(rd)
    px, pd = probes.plan(fx, ex, cfg), probes.plan(fd, edd, cfg)
    report("RetaX", fx, px)
    report("RetaD", fd, pd)
    common_checks("RetaX", fx, ex, px, cfg)
    common_checks("RetaD", fd, edd, pd, cfg)
    long_x = max(b.s1 - b.s0 for b in px.boxes)
    long_d = max(b.s1 - b.s0 for b in pd.boxes)
    check(long_x > long_d, "reta em X dá caixas mais longas que a diagonal (%.0f x %.0f m)" % (long_x, long_d))
    check(pd.total > px.total, "diagonal gasta mais sondas (%d x %d)" % (pd.total, px.total))

    # Reta curta em X cabe numa caixa só.
    rc = make_curve(sc, "RetaCurta", [(0, 0, 0), (10, 0, 0), (20, 0, 0)])
    fc, ec = frames_of(rc)
    pc = probes.plan(fc, ec, probes.Config(spacing=4.0, quality='HIGH'))
    report("RetaCurta", fc, pc)
    check(len(pc.boxes) == 1, "reta curta em X: 1 caixa (%d)" % len(pc.boxes))

    # Circuito fechado com curvas fechadas e rampa.
    loop = make_curve(sc, "Circuito", [(0, 0, 0), (120, 0, 0), (160, 40, 3), (120, 90, 6), (40, 70, 4),
                                       (-20, 40, 2)], cyclic=True)
    fl, el = frames_of(loop)
    pm = probes.plan(fl, el, probes.Config(spacing=4.0, quality='MEDIUM'))
    print("Circuito Medium:", pm.text(), pm.warnings)
    check(pm.grown > 0 and any("too wide" in w for w in pm.warnings),
          "circuito Medium 4 m: avisa que a seção não cabe (%d caixas)" % pm.grown)
    check(len(pm.boxes) < 120, "circuito Medium: sem picotar em caixas de 1 amostra (%d)" % len(pm.boxes))
    pl = probes.plan(fl, el, probes.Config(spacing=4.0, quality='HIGH'))
    report("Circuito", fl, pl)
    common_checks("Circuito", fl, el, pl, pl.cfg)
    check(abs(pl.boxes[-1].s1 - fl.length) < 1e-3, "circuito: última caixa fecha a volta")
    shorts = [b.s1 - b.s0 for b in pl.boxes]
    print("   trechos: min %.1f, máx %.1f m" % (min(shorts), max(shorts)))

    # Limite total e espaçamento sugerido.
    tight = probes.Config(spacing=2.0, quality='MEDIUM', max_total=300)
    pt = probes.plan(fl, el, tight)
    check(pt.over_limit, "limite 300 com 2 m estoura (%d)" % pt.total)
    sug = probes.suggest_spacing(fl, el, tight)
    ok = sug is not None and not probes.plan(fl, el, probes.Config(sug, quality='MEDIUM', max_total=300)).over_limit
    check(ok, "espaçamento sugerido cabe no limite (%s m)" % sug)


def test_track(name):
    props.register()
    ob = bpy.data.objects.get(name)
    check(ob is not None and ob.range_track.enabled, "%s existe e é traçado" % name)
    if ob is None:
        return
    fr, ed = frames_of(ob)
    cfg = probes.Config.from_settings(ob.range_track)
    res = probes.plan(fr, ed, cfg)
    report(name, fr, res)
    common_checks(name, fr, ed, res, cfg)


def test_generate():
    """P2: Generate/Clear na cena (regerar dá os mesmos Empties; volume manual intocado)."""
    sys.modules.pop("range_track.generate", None)
    from range_track import generate as gen
    try:
        from bl_ui import properties_probe_volume as ppv
    except Exception:
        ppv = None
    sc = bpy.context.scene
    ob = make_curve(sc, "PistaGen", [(0, 0, 0), (120, 0, 0), (160, 40, 3), (120, 90, 6), (40, 70, 4),
                                     (-20, 40, 2)], cyclic=True)
    manual = bpy.data.objects.new("VolumeManual", None)
    manual.empty_draw_type = 'CUBE'
    sc.objects.link(manual)
    sc.objects.active = manual
    bpy.ops.object.game_property_new(type='FLOAT', name="probe_volume")

    def snapshot():
        return sorted((o.name, tuple(round(v, 4) for v in o.location), tuple(round(v, 4) for v in o.scale))
                      for o in probes.owned_volumes(ob.name))

    r1 = gen.generate(ob, {'PROBES'})
    s1 = snapshot()
    r2 = gen.generate(ob, {'PROBES'})
    s2 = snapshot()
    fr, ed = frames_of(ob)
    pl = probes.plan(fr, ed, probes.Config.from_settings(ob.range_track))
    print("PistaGen:", pl.text(), "criados", len(s1), "avisos", r1['warnings'] + r2['warnings'])
    check(len(s1) == len(pl.boxes) > 0, "gera um Empty por caixa (%d de %d)" % (len(s1), len(pl.boxes)))
    check(s1 == s2, "regerar 2x dá os mesmos Empties (nome, posição, escala)")
    check(r2['removed'] == len(s1), "regerar apaga os anteriores (%d)" % r2['removed'])
    check(len([o for o in bpy.data.objects if o.name.startswith("PV_PistaGen")]) == len(s1),
          "sem sobra de Empties antigos")
    grp = bpy.data.groups.get("PistaGen_ProbeVolumes")
    check(grp is not None and len(grp.objects) == len(s1), "todos no grupo PistaGen_ProbeVolumes")
    vols = probes.owned_volumes(ob.name)
    v0 = vols[0]
    gp = v0.game.properties
    check(abs(gp["probe_volume"].value - 6.0) < 1e-6 and gp["probe_volume_quality"].value == "medium",
          "propriedades de jogo: espaçamento 6 e qualidade medium")
    check(all(o.empty_draw_type == 'CUBE' for o in vols), "Display Cube")
    if ppv is not None:
        bad = 0
        byname = {"PV_PistaGen_%03d" % n: b for n, b in enumerate(pl.boxes)}
        for o in vols:
            dims, _sp, used, _lim = ppv._grid(o)
            b = byname[o.name]
            if list(dims) != list(b.dims) or abs(used - b.used_spacing) > 1e-3:
                bad += 1
                if bad == 1:
                    print("   dif", o.name, dims, b.dims, used, b.used_spacing, tuple(o.scale), b.half)
        check(bad == 0, "grade do painel Light Probe Volume = grade do plano (%d diferentes)" % bad)
    # Gerar outra parte não toca nos volumes.
    gen.clear_generated(ob, {'ROAD'})
    check(len(probes.owned_volumes(ob.name)) == len(s1), "limpar ROAD não apaga os volumes")
    n = probes.clear_volumes(ob.name)
    check(n == len(s1) and not probes.owned_volumes(ob.name), "Clear apaga os %d volumes" % n)
    check(bpy.data.groups.get("PistaGen_ProbeVolumes") is None, "Clear apaga o grupo vazio")
    check("VolumeManual" in bpy.data.objects and "probe_volume" in manual.game.properties,
          "volume feito à mão intocado")
    # Acima do limite: recusa sem criar nada.
    ob.range_track.probe_max_total = 50
    r3 = gen.generate(ob, {'PROBES'})
    check(not probes.owned_volumes(ob.name) and any("PROBES" in w for w in r3['warnings']),
          "acima do limite: não cria e avisa (%s)" % r3['warnings'][:1])


if argv:
    test_track(argv[0])
else:
    test_synthetic()
    test_generate()
print("FALHAS: %d" % len(FAILS))
for f in FAILS:
    print("  -", f)
sys.stdout.flush()
os._exit(1 if FAILS else 0)
