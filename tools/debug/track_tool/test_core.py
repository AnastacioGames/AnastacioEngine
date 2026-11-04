# Testes headless do núcleo do Track Tool (props, frames, layout, sweep, generate, convert).
#
# Uso:
#   AnastacioEngine.exe -b --factory-startup --python tools/debug/track_tool/test_core.py -- simple
#   AnastacioEngine.exe -b <copia RolimaRacer.range> --python tools/debug/track_tool/test_core.py -- pista4 [out_dir]
# Nunca salva o arquivo aberto.
import math
import os
import sys
import time

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..",
                   "source", "release", "scripts", "modules")
sys.path.insert(0, os.path.normpath(SRC))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

for m in [k for k in sys.modules if k == "range_track" or k.startswith("range_track.")]:
    del sys.modules[m]
import range_track  # noqa: E402
from range_track import props, frames as frames_mod, layout  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
MODE = argv[0] if argv else "simple"
OUT = argv[1] if len(argv) > 1 else os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "artifacts", "track_tool", "core"))

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
    return ob


def inner_lower(fr, ed, upto='ASPHALT'):
    """Na amostra de curva mais fechada: z da borda interna < externa?"""
    i = max(range(fr.count), key=lambda j: abs(fr.turn_deg[j]))
    left_in = fr.turn_deg[i] > 0
    zl = ed.outer(i, 1, upto)[1]
    zr = ed.outer(i, -1, upto)[1]
    ok = (zl < zr) if left_in else (zr < zl)
    return ok, i, fr.turn_deg[i], zl - zr, math.degrees(fr.bank[i])


def test_simple():
    props.register()
    props.register()          # idempotente
    sc = bpy.context.scene
    names = props.default_profiles(sc)
    names2 = props.default_profiles(sc)
    check(len(sc.range_track_profiles) == 3 and names == names2, "default_profiles cria 3 perfis uma vez")
    # S aberto
    ob = make_curve(sc, "S_Curve", [(0, 0, 0), (60, 0, 0), (100, 40, 2), (100, 100, 4), (60, 140, 4),
                                    (0, 140, 6)])
    st = ob.range_track
    st.enabled = True
    st.profile = "Rua de bairro"
    fr = frames_mod.sample(ob, st)
    print("S: len %.2f count %d step %.4f" % (fr.length, fr.count, fr.step))
    check(abs(fr.s[-1] - fr.length) < 1e-6, "S: última amostra no fim")
    steps = [(fr.pos[i + 1] - fr.pos[i]).length for i in range(fr.count - 1)]
    check(max(steps) - min(steps) < 0.02, "S: passo uniforme (%.4f..%.4f)" % (min(steps), max(steps)))
    check(all(abs(l.z) < 1e-9 for l in fr.lat), "S: lateral horizontal")
    prof = props.find_profile("Rua de bairro", sc)
    ed = layout.band_edges(fr, prof, st)
    ok, i, t, dz, b = inner_lower(fr, ed)
    check(ok, "S: borda interna mais baixa (i=%d turn %.1f bank %.2f dz %.3f)" % (i, t, b, dz))
    print("S bank por ponto:", [round(x, 2) for x in fr.point_bank_deg])
    # Bandas
    print("S bandas em 0:", [(be.name, be.kind, round(be.off_in, 2), round(be.off_out, 2),
                              round(be.z_in, 3), round(be.z_out, 3)) for be in ed.bands(0, 1)])
    a = ed.band(0, 1, 'ASPHALT')
    check(abs(a[1] - 4.94) < 1e-6, "S: asfalto meia largura 4.94")
    c = ed.band(0, 1, 'CURB')
    check(abs(c[2] - a[3] - 0.17) < 1e-6, "S: guia +0.17")
    # largura por ponto
    p = st.points.add()
    p.index = 2
    p.width_left = 8.0
    fr2 = frames_mod.sample(ob, st)
    j = min(range(fr2.count), key=lambda k: abs(fr2.u[k] - 2.0))
    check(abs(fr2.wl[j] - 8.0) < 0.1 and abs(fr2.wr[j] - 4.94) < 1e-6, "S: width_left por ponto (%.2f)" % fr2.wl[j])
    # manual
    p.bank_mode = 'MANUAL'
    p.bank_deg = 10.0
    fr3 = frames_mod.sample(ob, st)
    check(abs(math.degrees(fr3.bank[j]) - 10.0) < 0.2, "S: bank manual 10 (%.2f)" % math.degrees(fr3.bank[j]))
    st.points.clear()
    # nearest / at / dist_to_edge
    q = fr.pos[200] + fr.lat[200] * 3.0
    i, s, side, d = fr.nearest(q.x, q.y)
    check(abs(s - fr.s[200]) < 0.6 and side == 1 and abs(d - 3.0) < 0.05,
          "S: nearest (s %.2f/%.2f side %d d %.3f)" % (s, fr.s[200], side, d))
    pos, tan, lat, up, bank = fr.at(fr.s[200] + 0.5 * fr.step)
    check((pos - fr.pos[200].lerp(fr.pos[201], 0.5)).length < 1e-6, "S: at() interpola")
    eo = ed.outer(200, 1)[0]
    d_in = ed.dist_to_edge(q.x, q.y)
    q2 = fr.pos[200] + fr.lat[200] * (ed.outer(200, 1, 'BORDER')[0] + 5.0)
    d_out = ed.dist_to_edge(q2.x, q2.y)
    check(d_in < 0 and abs(d_out - 5.0) < 0.1, "S: dist_to_edge (dentro %.2f, fora %.2f)" % (d_in, d_out))
    # trecho: calçada some à esquerda de 50 a 80 m
    sg = st.segments.add()
    sg.s_start, sg.s_end, sg.side, sg.band, sg.width, sg.blend = 50, 80, 'LEFT', "Calcada", 0.0, 10.0
    ed2 = layout.band_edges(fr, prof, st)
    k60 = int(60 / fr.step)
    k45 = int(45 / fr.step)
    wc60 = ed2.band(k60, 1, 'Calcada')
    wc45 = ed2.band(k45, 1, 'Calcada')
    wr60 = ed2.band(k60, -1, 'Calcada')
    check(abs(wc60[1] - wc60[0]) < 1e-6 and abs((wc45[1] - wc45[0]) - 2.65 * (1.0 - (fr.s[k45] - 40.0) / 10.0)) < 0.01 and
          abs(wr60[1] - wr60[0] - 2.65) < 1e-6, "S: trecho com transição (%.2f, %.2f)" % (
              wc60[1] - wc60[0], wc45[1] - wc45[0]))
    st.segments.clear()

    # oval cíclico (curva à direita = sentido horário)
    ov = make_curve(sc, "Oval_Curve", [(300, -150, 0), (400, -150, 0), (440, -190, 0), (400, -230, 0),
                                       (300, -230, 0), (260, -190, 0)], cyclic=True)
    ov.range_track.profile = "Autodromo"
    fo = frames_mod.sample(ov, ov.range_track)
    print("Oval: len %.2f count %d step %.4f" % (fo.length, fo.count, fo.step))
    check(fo.cyclic and abs(fo.count * fo.step - fo.length) < 1e-6, "Oval: cíclico fecha")
    check((fo.pos[-1] - fo.pos[0]).length < fo.step * 1.01, "Oval: última amostra perto da primeira")
    eo_ = layout.band_edges(fo, props.find_profile("Autodromo", sc), ov.range_track)
    ok, i, t, dz, b = inner_lower(fo, eo_)
    check(ok and t < 0, "Oval: borda interna (direita) mais baixa (turn %.1f bank %.2f dz %.3f)" % (t, b, dz))
    s_wrap = fo.at(fo.length + 1.0)[0]
    check((s_wrap - fo.at(1.0)[0]).length < 1e-6, "Oval: at() dá a volta")
    return sc


def test_parametric():
    """Perfis paramétricos (bairro/serra/autódromo), aberto e cíclico: gera ROAD, confere
    normais, emendas (inclusive a da volta no cíclico), colisão e renderiza prints."""
    import test_pista
    from range_track import generate
    sc = test_simple()
    for o in list(sc.objects):
        if o.type == 'MESH':
            sc.objects.unlink(o)
    reps = {}
    for cname, prof in (("S_Curve", "Rua de bairro"), ("Oval_Curve", "Autodromo")):
        ob = bpy.data.objects[cname]
        ob.range_track.enabled = True
        ob.range_track.profile = prof
        t0 = time.perf_counter()
        rep = generate.generate(ob, {'ROAD'})
        reps[cname] = rep
        print(cname, prof, {k: rep[k] for k in ('objects', 'faces', 'warnings')}, "%.2f s" % (time.perf_counter() - t0))
        _, st, _, fr, ed, _ = generate.prepare(ob)
        for kind in ("_Road_", "_RoadCol_"):
            tot, mat, worst = test_pista._seam_check(rep, fr, kind, st.chunk_length)
            check(tot > 0 and tot == mat, "%s emendas %s: %d/%d idênticos%s" % (
                cname, kind.strip('_'), mat, tot, " (inclui a da volta)" if fr.cyclic else ""))
        bad = tot_f = 0
        for n in rep['objects_by_part']['ROAD']:
            o = bpy.data.objects[n]
            if "_RoadCol_" in n:
                continue
            for pl in o.data.polygons:
                m = o.data.materials[pl.material_index].name
                if m in ("Track_Asfalto", "Track_Calcada", "Track_Grama", "Track_Faixa") and abs(pl.normal.z) > 0.5:
                    tot_f += 1                  # (degraus verticais ficam de fora)
                    bad += pl.normal.z < 0.0
        check(tot_f > 0 and bad == 0, "%s: %d faces de piso com normal para cima (%d para baixo)" % (cname, tot_f, bad))
        mats = set()
        for n in rep['objects_by_part']['ROAD']:
            mats.update(m.name for m in bpy.data.objects[n].data.materials)
        print(cname, "materiais", sorted(mats))
        # paredes: face interna da borda virada para a pista, externa para fora
        wall_ok = wall_bad = 0
        for n in rep['objects_by_part']['ROAD']:
            o = bpy.data.objects[n]
            if "_RoadCol_" in n:
                continue
            for pl in o.data.polygons:
                m = o.data.materials[pl.material_index].name
                if m not in ("Track_Mureta", "Track_Grade") or abs(pl.normal.z) > 0.5:
                    continue
                c = pl.center
                i, s, side, d = fr.nearest(c.x, c.y)
                be = ed.find(i, side, 'BORDER')
                lat = fr.at(s)[2] * side
                if be is None or not (be.off_in - 0.05 < d < be.off_out + 0.05):
                    continue
                if m == "Track_Grade":
                    continue        # painel com duas faces (uma para cada lado)
                if abs(d - be.off_in) < 0.05:
                    good = pl.normal.dot(lat) < 0
                elif abs(d - be.off_out) < 0.05:
                    good = pl.normal.dot(lat) > 0
                else:
                    continue
                wall_ok += good
                wall_bad += not good
        if prof == "Rua de bairro":
            check(wall_ok > 0 and wall_bad == 0, "%s: faces da mureta viradas certo (%d ok, %d erradas)" % (cname, wall_ok, wall_bad))
        if prof == "Autodromo":
            check({"Track_ZebraVermelha", "Track_ZebraBranca", "Track_Grade"} <= mats, "Oval: zebra e grade")
        else:
            check({"Track_Mureta", "Track_Faixa", "Track_Guia"} <= mats, "S: mureta, faixa pintada e guia")
    # serra no S (guard-rail)
    ob = bpy.data.objects["S_Curve"]
    ob.range_track.profile = "Estrada de serra"
    rep = generate.generate(ob, {'ROAD'})
    mats = set()
    for n in rep['objects_by_part']['ROAD']:
        mats.update(m.name for m in bpy.data.objects[n].data.materials)
    check("Track_GuardRail" in mats and "Track_Terra" in mats, "S serra: guard-rail e acostamento de terra")
    # prints
    if "--noprint" not in os.environ.get("TRACK_TEST_FLAGS", ""):
        ob.range_track.profile = "Rua de bairro"
        generate.generate(ob, {'ROAD'})
        for o in sc.objects:
            if o.type == 'MESH' and "Oval" in o.name:
                o.location.x += 0.0
        _, _, _, fr, _, _ = generate.prepare(bpy.data.objects["Oval_Curve"])
        _, _, _, frs, _, _ = generate.prepare(ob)
        # chão simples para os prints
        me = bpy.data.meshes.new("chao")
        me.from_pydata([(-200, -300, -1), (400, -300, -1), (400, 300, -1), (-200, 300, -1)], [], [(0, 1, 2, 3)])
        g = bpy.data.objects.new("chao", me)
        sc.objects.link(g)
        me.materials.append(props.ensure_material('grass'))
        test_pista.render_prints(sc, fr, OUT, "Oval_Autodromo")
        cam = sc.camera
        P, T, L = frs.pos, frs.tan, frs.lat
        i = max(range(frs.count), key=lambda j: abs(frs.turn_deg[j]))
        for nome, pos, alvo in (("S_bairro_curva", P[i] - T[i] * 18 + Vector((0, 0, 6)), P[min(frs.count - 1, i + 8)]),
                                ("S_bairro_mureta", P[60] + L[60] * 3 - T[60] * 6 + Vector((0, 0, 1.5)), P[60] + L[60] * 8 + T[60] * 6)):
            cam.location = pos
            cam.rotation_euler = (alvo - pos).to_track_quat('-Z', 'Y').to_euler()
            sc.render.filepath = os.path.join(OUT, nome + ".png")
            bpy.ops.render.render(write_still=True)
            print("print", sc.render.filepath)


def run():
    t0 = time.time()
    if MODE == "simple":
        test_simple()
    elif MODE == "parametric":
        test_parametric()
    else:
        import test_pista
        test_pista.run(MODE, OUT, check)
    print("TEMPO %.2f s" % (time.time() - t0))
    print("RESULTADO:", "FALHOU %d" % len(FAILS) if FAILS else "TUDO OK")
    for f in FAILS:
        print("  -", f)


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    run()
