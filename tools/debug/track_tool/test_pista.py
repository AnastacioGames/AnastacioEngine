# Parte do test_core.py: Convert + Generate na Pista_4/Pista_5 (cópia do RolimaRacer).
# Mede largura/borda contra a malha original (sem inclinação), lado de dentro mais baixo,
# emendas idênticas entre blocos, tempo, e renderiza prints sem fog (Blender Internal).
import math
import os
import time

import bpy
from mathutils import Vector, kdtree

from range_track import convert, generate, layout, props


def _delete_prefix(sc, pref):
    n = 0
    for o in list(sc.objects):
        if o.name.startswith(pref):
            data, typ = o.data, o.type
            sc.objects.unlink(o)
            bpy.data.objects.remove(o, do_unlink=True)
            if data is not None and typ == 'MESH' and data.users == 0:
                bpy.data.meshes.remove(data)
            n += 1
    return n


def _deformed_points(sc, ob):
    """(pontos, arestas) da malha deformada (mundo)."""
    sc.update()
    me = ob.to_mesh(sc, True, 'PREVIEW')
    pts = [ob.matrix_world * v.co for v in me.vertices]
    eds = [tuple(e.vertices) for e in me.edges]
    bpy.data.meshes.remove(me)
    return pts, eds


def _gen_points(names, kind="_Road_"):
    pts, eds = [], []
    for n in names:
        if kind in n:
            o = bpy.data.objects[n]
            b = len(pts)
            pts.extend(o.matrix_world * v.co for v in o.data.vertices)
            eds.extend((b + e.vertices[0], b + e.vertices[1]) for e in o.data.edges)
    return pts, eds


def _slice(mesh, fr, sample_idx, rmax=16.0):
    """Corta a malha (arestas) pelo plano vertical perpendicular à pista em cada amostra:
    {i: (lateral máx, z dele, -lateral mín, z dele)}."""
    pts, eds = mesh
    mids = kdtree.KDTree(len(eds))
    half = 0.0
    for n, (a, b) in enumerate(eds):
        m = (pts[a] + pts[b]) * 0.5
        half = max(half, (pts[a] - pts[b]).length * 0.5)
        mids.insert(Vector((m.x, m.y, 0)), n)
    mids.balance()
    out = {}
    for i in sample_idx:
        P, T, L = fr.pos[i], fr.tan[i], fr.lat[i]
        th = Vector((T.x, T.y, 0)).normalized()
        hits = []
        for _, n, _ in mids.find_range(Vector((P.x, P.y, 0)), rmax + half):
            a, b = pts[eds[n][0]], pts[eds[n][1]]
            da = (a.x - P.x) * th.x + (a.y - P.y) * th.y
            db = (b.x - P.x) * th.x + (b.y - P.y) * th.y
            if (da > 0) == (db > 0) or abs(da - db) < 1e-9:
                continue
            q = a.lerp(b, da / (da - db))
            sl = (q.x - P.x) * L.x + (q.y - P.y) * L.y
            if abs(sl) <= rmax:
                hits.append((sl, q.z))
        if hits:
            mx = max(hits, key=lambda h: (round(h[0], 2), h[1]))
            mn = min(hits, key=lambda h: (round(h[0], 2), -h[1]))
            out[i] = (mx[0], mx[1], -mn[0], mn[1])
    return out


def _seam_verts(me, P, th):
    """Vértices no plano da emenda, sem os das faixas pintadas (tracejado é decalque solto:
    o traço pode começar exatamente na emenda)."""
    deco = set()
    for k, m in enumerate(me.materials):
        if m is not None and m.name == "Track_Faixa":
            deco.add(k)
    only_deco = set()
    if deco:
        used = {}
        for pl in me.polygons:
            for v in pl.vertices:
                used.setdefault(v, set()).add(pl.material_index in deco)
        only_deco = {v for v, f in used.items() if f == {True}}
    return [v.co.copy() for v in me.vertices
            if v.index not in only_deco and abs((v.co - P).dot(th)) < 1e-3
            and (v.co - P).length < 25.0]


def _seam_check(rep, fr, kind, chunk_length):
    """Na amostra da emenda entre blocos consecutivos, os vértices dos dois blocos no plano da
    emenda são os mesmos (tuplas float32 idênticas)."""
    from range_track import sweep
    ch = sweep.chunk_ranges(fr, chunk_length)
    names = sorted(n for n in rep['objects_by_part']['ROAD'] if kind in n)
    pairs = list(zip(range(len(ch) - 1), range(1, len(ch))))
    if fr.cyclic:
        pairs.append((len(ch) - 1, 0))
    total = matched = 0
    worst = 0.0
    base = names[0].rsplit("_", 1)[0]
    for a, b in pairs:
        k = ch[a][1] % fr.count
        P = fr.pos[k]
        th = Vector((fr.tan[k].x, fr.tan[k].y, 0)).normalized()
        A = bpy.data.objects["%s_%02d" % (base, a)].data
        B = bpy.data.objects["%s_%02d" % (base, b)].data
        va = _seam_verts(A, P, th)
        vb = _seam_verts(B, P, th)
        sa = set(tuple(v) for v in va)
        sb = set(tuple(v) for v in vb)
        total += len(sb)
        matched += len(sb & sa)
        if sa != sb:
            for v in sb - sa:
                worst = max(worst, min((Vector(q) - Vector(v)).length for q in sa) if sa else 1e9)
    return total, matched, worst


def run(mode, out, check):
    os.makedirs(out, exist_ok=True)
    props.register()
    scn = "Pista_5" if mode == "pista5" else "Pista_4"
    sc = bpy.data.scenes[scn]
    bpy.context.screen.scene = sc
    pref = "P" + scn[-1] + "_"
    print("apagou prefixo", pref, _delete_prefix(sc, pref))
    track = next(o for o in sc.objects if o.type == 'MESH' and o.name.endswith("_Track"))
    curve0 = next(o for o in sc.objects if o.type == 'CURVE' and o.name.endswith("_Curve"))

    # malha original SEM inclinação (tilt zerado só para medir)
    sp = curve0.data.splines[0]
    tilts = [p.tilt for p in sp.bezier_points]
    for p in sp.bezier_points:
        p.tilt = 0.0
    curve0.data.twist_mode = 'Z_UP'
    # resolução alta só na medição: o Curve modifier segue a polilinha avaliada (resolution_u=12
    # dá cordas de ~8 m e desloca o centro até ~0.3 m nas curvas fechadas)
    res0 = curve0.data.resolution_u
    curve0.data.resolution_u = 64
    orig_flat = _deformed_points(sc, track)
    curve0.data.resolution_u = res0
    for p, t in zip(sp.bezier_points, tilts):
        p.tilt = t
    orig_tilt = _deformed_points(sc, track)

    t0 = time.perf_counter()
    curve = convert.convert_curve_array(track)
    t_conv = time.perf_counter() - t0
    check(curve == curve0 and track.hide_render and track.game.physics_type == 'NO_COLLISION',
          "convert: curva %s, original escondida e sem colisão (%.3f s)" % (curve.name, t_conv))
    st = curve.range_track
    prof = props.find_profile(st.profile, sc)
    print("perfil", prof.name, [(b.name, b.kind, round(b.width, 3)) for b in prof.bands])
    print("larguras por ponto", [round(p.width_left, 2) for p in st.points])

    # ---- sem inclinação: compara com a malha original sem tilt
    st.bank_auto = False
    rep = generate.generate(curve, {'ROAD'})
    print("ROAD sem bank:", {k: rep[k] for k in ('objects', 'faces', 'length', 'samples', 'warnings')},
          {k: round(v, 3) for k, v in rep['times'].items()})
    _, _, _, fr, ed, _ = generate.prepare(curve)
    idx = list(range(8, fr.count - 8, 5))
    eo = _slice(orig_flat, fr, idx)
    eg = _slice(_gen_points(rep['objects_by_part']['ROAD']), fr, idx)
    dw = dz = dt = 0.0
    worst = None
    diffs = []
    for i in idx:
        if i in eo and i in eg:
            a, b = eo[i], eg[i]
            d = max(abs(a[0] - b[0]), abs(a[2] - b[2]))
            diffs.append(d)
            if d > dw:
                dw, worst = d, i
            dz = max(dz, abs(a[1] - b[1]), abs(a[3] - b[3]))
            dt = max(dt, abs((a[0] + a[2]) - (b[0] + b[2])))
    diffs.sort()
    print("pior borda na amostra", worst, eo.get(worst), eg.get(worst))
    check(len(diffs) > 300 and dw <= 0.3 and dz <= 0.3 and dt <= 0.3,
          "largura/borda x original sem bank (%d cortes): borda dif máx %.3f m (mediana %.3f), "
          "largura total dif máx %.3f m, z dif máx %.3f m" % (len(diffs), dw, diffs[len(diffs) // 2], dt, dz))
    # asfalto: meia largura do asfalto (borda interna da guia) pela layout x original
    # ---- com inclinação Auto
    st.bank_auto = True
    t0 = time.perf_counter()
    rep = generate.generate(curve, {'ROAD'})
    t_road = time.perf_counter() - t0
    print("ROAD com bank:", {k: rep[k] for k in ('objects', 'faces', 'removed', 'warnings')},
          {k: round(v, 3) for k, v in rep['times'].items()})
    check(t_road < 10.0, "tempo generate(ROAD) %.2f s (%.0f m)" % (t_road, rep['length']))
    _, _, _, fr, ed, _ = generate.prepare(curve)
    i = max(range(fr.count), key=lambda j: abs(fr.turn_deg[j]))
    gp = _slice(_gen_points(rep['objects_by_part']['ROAD']), fr, [i])[i]
    left_in = fr.turn_deg[i] > 0
    ok = (gp[1] < gp[3]) if left_in else (gp[3] < gp[1])
    check(ok, "malha gerada: borda de dentro mais baixa (amostra %d, turn %.1f, bank %.2f, zE %.2f zD %.2f)"
          % (i, fr.turn_deg[i], math.degrees(fr.bank[i]), gp[1], gp[3]))
    # mesma regra que o protótipo: compara o desnível com o da malha original com tilt
    ot = _slice(orig_tilt, fr, [i]).get(i)
    if ot:
        print("original com tilt na mesma amostra: zE %.2f zD %.2f (desnível %.2f) | nosso %.2f" % (
            ot[1], ot[3], ot[1] - ot[3], gp[1] - gp[3]))
        check((ot[1] - ot[3]) * (gp[1] - gp[3]) > 0, "sinal da inclinação igual ao do protótipo")
    print("bank por ponto (graus):", [round(b, 2) for b in fr.point_bank_deg])
    print("tilt protótipo (graus):", [round(-math.degrees(t), 2) for t in tilts])
    db = max(abs(a + math.degrees(t)) for a, t in zip(fr.point_bank_deg, tilts))
    check(db < 0.05, "bank Auto por ponto = -tilt do protótipo (dif máx %.3f graus)" % db)

    for kind in ("_Road_", "_RoadCol_"):
        tot, mat, worst = _seam_check(rep, fr, kind, st.chunk_length)
        check(tot > 0 and tot == mat, "emendas %s: %d/%d vértices idênticos (pior dist %.2e)" % (
            kind.strip('_'), mat, tot, worst))
    col = [bpy.data.objects[n] for n in rep['objects_by_part']['ROAD'] if "_RoadCol_" in n]
    check(all(o.game.physics_type == 'STATIC' and o.game.collision_bounds_type == 'TRIANGLE_MESH'
              for o in col), "colisão: %d blocos STATIC Triangle Mesh" % len(col))
    vis = [bpy.data.objects[n] for n in rep['objects_by_part']['ROAD'] if "_Road_" in n]
    check(all(o.game.physics_type == 'NO_COLLISION' for o in vis), "visual: %d blocos sem colisão" % len(vis))
    mats = set()
    for o in vis:
        mats.update(m.name for m in o.data.materials)
    used = {track.data.materials[pl.material_index].name for pl in track.data.polygons}
    check(used <= mats, "materiais da seção mantidos: %s" % sorted(mats))

    # regerar não duplica
    n_before = len([o for o in bpy.data.objects if o.range_track_owner == curve.name])
    rep2 = generate.generate(curve, {'ROAD'})
    n_after = len([o for o in bpy.data.objects if o.range_track_owner == curve.name])
    check(n_before == n_after and rep2['removed'] == n_before, "regerar: %d -> %d objetos (apagou %d)"
          % (n_before, n_after, rep2['removed']))

    # tudo (módulos dos outros agentes; avisos não reprovam)
    t0 = time.perf_counter()
    try:
        repall = generate.generate(curve, {'ROAD', 'TERRAIN', 'DECOR', 'BAKE'})
        print("ALL:", {k: repall[k] for k in ('objects', 'faces', 'removed', 'warnings', 'baked')},
              {k: round(v, 3) for k, v in repall['times'].items()}, "%.2f s" % (time.perf_counter() - t0))
    except Exception as ex:
        print("ALL falhou (fora do núcleo):", ex)

    if "--noprint" not in os.environ.get("TRACK_TEST_FLAGS", ""):
        render_prints(sc, fr, out, scn)


def render_prints(sc, fr, out, tag):
    sc.render.engine = 'BLENDER_RENDER'
    w = sc.world
    w.mist_settings.use_mist = False
    w.horizon_color = (0.62, 0.75, 0.9)
    w.zenith_color = (0.3, 0.5, 0.85)
    w.use_sky_blend = True
    w.light_settings.use_environment_light = True
    w.light_settings.environment_energy = 0.6
    w.light_settings.gather_method = "APPROXIMATE"
    for o in sc.objects:
        if o.type == 'LAMP':
            o.data.energy = 1.2
    if not any(o.type == 'LAMP' and o.data.type == 'SUN' for o in sc.objects):
        kd_ = bpy.data.lamps.new('key', 'SUN')
        kd_.energy = 1.0
        ko = bpy.data.objects.new('key', kd_)
        sc.objects.link(ko)
        ko.rotation_euler = (math.radians(50), 0, math.radians(35))
    bd = bpy.data.lamps.new('back', 'SUN')
    bd.energy = 0.35
    bo = bpy.data.objects.new('back', bd)
    sc.objects.link(bo)
    bo.rotation_euler = (math.radians(55), 0, math.radians(215))
    fd = bpy.data.lamps.new('fill', 'SUN')
    fd.energy = 0.45
    fo = bpy.data.objects.new('fill', fd)
    sc.objects.link(fo)
    fo.rotation_euler = (math.radians(60), 0, math.radians(200))
    sc.render.resolution_x, sc.render.resolution_y = 960, 540
    sc.render.resolution_percentage = 100
    sc.render.use_antialiasing = True
    sc.render.use_shadows = False
    sc.render.use_raytrace = True
    cd = bpy.data.cameras.new("shot")
    cd.clip_end = 4000
    cd.lens = 24
    cam = bpy.data.objects.new("shot", cd)
    sc.objects.link(cam)
    sc.camera = cam
    for k in range(20):
        sc.layers[k] = True

    def shot(name, pos, alvo):
        cam.location = pos
        cam.rotation_euler = (alvo - pos).to_track_quat('-Z', 'Y').to_euler()
        sc.render.filepath = os.path.join(out, tag + "_" + name + ".png")
        bpy.ops.render.render(write_still=True)
        print("print", sc.render.filepath)

    P, T, L = fr.pos, fr.tan, fr.lat
    N = fr.count
    i = max(range(N), key=lambda j: abs(fr.turn_deg[j]))
    side_in = 1 if fr.turn_deg[i] > 0 else -1
    # 1) curva mais fechada vista de trás/de cima
    shot("01_curva", P[i] - T[i] * 22 + Vector((0, 0, 8)), P[min(N - 1, i + 10)])
    # 2) perseguição numa reta
    j = int(N * 0.12)
    shot("02_chase", P[j] - T[j] * 14 + Vector((0, 0, 4)), P[min(N - 1, j + 14)] + Vector((0, 0, 1)))
    # 3) guia e calçada de perto, olhando a emenda de bloco
    ch = int(round(75.0 / fr.step))
    k = ch * 2
    shot("03_emenda_guia", P[k] + L[k] * (side_in * 3.0) - T[k] * 5 + Vector((0, 0, 1.6)),
         P[k] + L[k] * (side_in * 6.0) + T[k] * 4)
    # 4) visão geral
    xs = [p.x for p in P]
    ys = [p.y for p in P]
    c = Vector(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, sum(p.z for p in P) / N))
    shot("04_geral", c + Vector((0, -700, 550)), c)
