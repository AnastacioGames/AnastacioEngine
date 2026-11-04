# Track Tool: sweep da estrada (faixas ASPHALT, CURB, SIDEWALK, BORDER e MESH).
#
# Contrato em docs/plano-track-tool.md (sweep.py). Decisões desta implementação:
#   - Visual em blocos de chunk_length metros ("<traçado>_Road_##", sem física). Cada faixa é
#     uma tira própria (vértices não são divididos entre faixas: sombreado suave ao longo da
#     pista e quina viva entre faixas).
#   - Colisão em blocos separados ("<traçado>_RoadCol_##", STATIC + Triangle Mesh, invisíveis no
#     jogo/render): mesmas faixas com collision ligada, amostradas a cada ~2 m (sem faixas pintadas
#     nem zebra), sempre incluindo as amostras da emenda.
#   - Todos os objetos ficam na origem, com vértices em coordenadas de mundo: a amostra da emenda
#     é calculada uma vez só, então os vértices da emenda são bit a bit idênticos entre blocos.
#   - MESH: a seção é a malha mesh_object (Y = lateral, Z = altura, X achatado). Mantém materiais,
#     imagem por face e a UV original: a UV de cada tira é ajustada como uv = A + B*x + C*t (x ao
#     longo, t na seção) e varrida com x = s + xmin, igual ao Array+Curve, mas sem emenda a cada
#     cópia. Tira sem UV na malha: u = lateral/uv_repeat, v = s/uv_repeat.
import math

import bpy
from mathutils import Vector

from . import props
from .layout import ROAD_KINDS

COL_STEP = 2.0          # metros entre amostras da colisão
KERB_MIN_DEG = 10.0     # |turn_deg| a partir do qual a guia vira zebra (kerb_on_curves)
KERB_GROW = 6.0         # metros de zebra antes/depois da curva
LINE_WIDTH = 0.12
LINE_DASH = 3.0
LINE_LIFT = 0.015
WALL_FOOT = 0.6         # quanto a mureta desce abaixo do chão (encosta no terreno)


class MeshBuilder(object):
    def __init__(self):
        self.v = []
        self.f = []
        self.uv = []
        self.mi = []
        self.sm = []
        self.img = []
        self.mats = []
        self._mat_index = {}

    def mat(self, m):
        key = m.name if m is not None else None
        k = self._mat_index.get(key)
        if k is None:
            k = len(self.mats)
            self.mats.append(m)
            self._mat_index[key] = k
        return k

    def vert(self, co):
        self.v.append(co)
        return len(self.v) - 1

    def face(self, idx, uvs, mi, smooth=False, img=None):
        self.f.append(idx)
        self.uv.append(uvs)
        self.mi.append(mi)
        self.sm.append(smooth)
        self.img.append(img)

    def build(self, name):
        me = bpy.data.meshes.new(name)
        if not self.f:
            return me
        me.from_pydata(self.v, [], self.f)
        for m in self.mats:
            me.materials.append(m)
        me.uv_textures.new("UVMap")
        flat = []
        for uvs in self.uv:
            for u, v in uvs:
                flat.append(u)
                flat.append(v)
        me.uv_layers[0].data.foreach_set("uv", flat)
        me.polygons.foreach_set("material_index", self.mi)
        me.polygons.foreach_set("use_smooth", self.sm)
        if any(im is not None for im in self.img):
            tex = me.uv_textures[0].data
            for k, im in enumerate(self.img):
                if im is not None:
                    tex[k].image = im
        me.update(calc_edges=True)
        return me


def _default_material(kind, border_type='NONE'):
    if kind == 'ASPHALT':
        return props.ensure_material('asphalt')
    if kind == 'CURB':
        return props.ensure_material('curb')
    if kind == 'SIDEWALK':
        return props.ensure_material('sidewalk')
    if kind == 'BORDER':
        return props.ensure_material({'GUARDRAIL': 'guardrail', 'FENCE': 'fence',
                                      'HOUSE_WALL': 'house_wall'}.get(border_type, 'wall'))
    return props.ensure_material('slope')


class _Ctx(object):
    """Dados compartilhados entre blocos."""

    def __init__(self, frames, edges, settings):
        self.fr = frames
        self.ed = edges
        self.uv_rep = max(0.01, float(getattr(settings, "uv_repeat", 8.0)))
        self.count = frames.count
        # zona de zebra por amostra
        n = frames.count
        grow = max(0, int(round(KERB_GROW / frames.step)))
        hot = [abs(t) >= KERB_MIN_DEG for t in frames.turn_deg]
        self.kerb = [False] * n
        for i in range(n):
            if hot[i]:
                for j in range(i - grow, i + grow + 1):
                    jj = frames.wrap(j)
                    self.kerb[jj] = True
        self.kerb_n = max(1, int(round(1.0 / frames.step)))

    def s_of(self, k):
        return k * self.fr.step if self.fr.cyclic else self.fr.s[k]

    def gi(self, k):
        return k % self.count if self.fr.cyclic else k


def _band_at(ed, i, sgn, bi):
    for be in ed.data[i][sgn]:
        if be.index == bi:
            return be
    return None


def _prev_z(ed, i, sgn, be):
    lst = ed.data[i][sgn]
    k = lst.index(be)
    if k == 0:
        return be.z_in
    return lst[k - 1].z_out


def _strip(mb, cx, ks, pts_fn, mat_fn, n_des, smooth, uv_fn=None, img=None, s0=0.0):
    """Varre uma tira. pts_fn(i, k) -> (ya, za, yb, zb) com lateral assinada e z absoluto, ou
    None. mat_fn(i, k) -> índice do material do quad que começa na amostra k.
    n_des = (ny, nz): normal desejada no plano da seção (lateral, z)."""
    fr = cx.fr
    rep = cx.uv_rep
    prev = None
    ny, nz = n_des
    for k in ks:
        i = cx.gi(k)
        r = pts_fn(i, k)
        if r is None:
            prev = None
            continue
        ya, za, yb, zb = r
        p = fr.pos[i]
        lat = fr.lat[i]
        A = Vector((p.x + lat.x * ya, p.y + lat.y * ya, za))
        B = Vector((p.x + lat.x * yb, p.y + lat.y * yb, zb))
        s = cx.s_of(k) - s0
        if uv_fn is not None:
            ua, ub = uv_fn(i, k, s)
        else:
            ua = ((abs(ya) + abs(za - p.z)) / rep, s / rep)
            ub = ((abs(yb) + abs(zb - p.z)) / rep, s / rep)
        ia = mb.vert(A)
        ib = mb.vert(B)
        cur = (k, ia, ib, ua, ub, yb - ya, zb - za)
        if prev is not None:
            dy, dz = cur[5], cur[6]
            if abs(dy) + abs(dz) < 1e-6:
                dy, dz = prev[5], prev[6]
            if abs(dy) + abs(dz) >= 1e-6:
                mi = mat_fn(i, prev[0])
                if mi is not None:
                    idx = [prev[1], prev[2], cur[2], cur[1]]
                    uvs = [prev[3], prev[4], cur[4], cur[3]]
                    if dz * ny - dy * nz < 0.0:
                        idx.reverse()
                        uvs.reverse()
                    mb.face(idx, uvs, mi, smooth, img)
        prev = cur


def _sweep_parametric(mb, cx, ks, bi, sgn, collision_only):
    """Uma faixa paramétrica (índice bi no perfil) num lado."""
    ed = cx.ed
    fr = cx.fr
    first = None
    for k in ks:
        first = _band_at(ed, cx.gi(k), sgn, bi)
        if first is not None:
            break
    if first is None:
        return
    band = first.band

    def get(i):
        be = _band_at(ed, i, sgn, bi)
        if be is None or be.kind not in ROAD_KINDS or be.kind == 'MESH':
            return None
        return be

    def kind_is(i, kinds):
        be = get(i)
        return be is not None and be.kind in kinds

    kinds_seen = set()
    for k in ks:
        be = get(cx.gi(k))
        if be is not None:
            kinds_seen.add((be.kind, be.border_type if be.kind == 'BORDER' else 'NONE'))
    if collision_only and not band.collision:
        return

    for kind, btype in sorted(kinds_seen):
        mat = band.material if band.material is not None else _default_material(kind, btype)
        mi = mb.mat(mat)
        mi_red = mi_white = None
        if kind == 'CURB' and band.kerb_on_curves and not collision_only:
            mi_red = mb.mat(props.ensure_material('kerb_red'))
            mi_white = mb.mat(props.ensure_material('kerb_white'))

        def sel(i):
            be = get(i)
            if be is None or be.kind != kind:
                return None
            if kind == 'BORDER' and be.border_type != btype:
                return None
            return be

        def mat_top(i, k, _mi=mi, _r=mi_red, _w=mi_white):
            if _r is not None:
                ii = cx.gi(k)
                if cx.kerb[ii] and cx.kerb[cx.gi(k + 1) if fr.cyclic or k + 1 < cx.count else ii]:
                    return _r if (k // cx.kerb_n) % 2 == 0 else _w
            return _mi

        def mat_plain(i, k, _mi=mi):
            return _mi

        # ---- degrau (riser) na borda interna, virado para o centro
        def riser(i, k):
            be = sel(i)
            if be is None:
                return None
            zp = _prev_z(ed, i, sgn, be)
            y = sgn * be.off_in
            return (y, zp, y, be.z_in)

        def has_riser():
            for k in ks:
                i = cx.gi(k)
                be = sel(i)
                if be is not None and abs(be.z_in - _prev_z(ed, i, sgn, be)) > 1e-4:
                    return True
            return False

        if kind != 'BORDER' or btype == 'NONE':
            if has_riser():
                _strip(mb, cx, ks, riser, mat_top, (-sgn, 0.0), False)

            def top(i, k):
                be = sel(i)
                if be is None:
                    return None
                return (sgn * be.off_in, be.z_in, sgn * be.off_out, be.z_out)
            _strip(mb, cx, ks, top, mat_top, (0.0, 1.0), True)
            continue

        # ---- bordas com geometria
        if btype in ('WALL', 'HOUSE_WALL'):
            def inner(i, k):
                be = sel(i)
                if be is None:
                    return None
                y = sgn * be.off_in
                return (y, be.z_in - WALL_FOOT, y, be.z_in + be.border_height)

            def cap(i, k):
                be = sel(i)
                if be is None:
                    return None
                zt = max(be.z_in, be.z_out) + be.border_height
                return (sgn * be.off_in, zt, sgn * be.off_out, zt)

            def outer(i, k):
                be = sel(i)
                if be is None:
                    return None
                y = sgn * be.off_out
                return (y, max(be.z_in, be.z_out) + be.border_height, y, be.z_out - WALL_FOOT)
            _strip(mb, cx, ks, inner, mat_plain, (-sgn, 0.0), False)
            _strip(mb, cx, ks, cap, mat_plain, (0.0, 1.0), False)
            _strip(mb, cx, ks, outer, mat_plain, (sgn, 0.0), False)
            continue

        # chão sob guard-rail/grade (não deixa buraco entre a calçada e o talude)
        def ground(i, k):
            be = sel(i)
            if be is None:
                return None
            return (sgn * be.off_in, be.z_in, sgn * be.off_out, be.z_out)
        gmat = None
        lst0 = ed.data[cx.gi(ks[0])][sgn]
        pos0 = [b.index for b in lst0]
        if bi in pos0 and pos0.index(bi) > 0:
            pb = lst0[pos0.index(bi) - 1]
            gmat = pb.material if pb.material is not None else _default_material(pb.kind)
        gmi = mb.mat(gmat if gmat is not None else props.ensure_material('sidewalk'))
        _strip(mb, cx, ks, ground, lambda i, k: gmi, (0.0, 1.0), True)

        if btype == 'GUARDRAIL':
            def rail(i, k, frac=0.25):
                be = sel(i)
                if be is None:
                    return None
                y = sgn * (be.off_in + (be.off_out - be.off_in) * frac)
                z = be.z_in
                return (y, z + be.border_height * 0.55, y, z + be.border_height)
            _strip(mb, cx, ks, rail, mat_plain, (-sgn, 0.0), False)
            if not collision_only:
                _strip(mb, cx, ks, rail, mat_plain, (sgn, 0.0), False)
                _posts(mb, cx, ks, sel, sgn, 0.25, 4.0, 0.08, mi, below=0.5)
        else:  # FENCE
            def panel(i, k):
                be = sel(i)
                if be is None:
                    return None
                y = sgn * (be.off_in + be.off_out) * 0.5
                return (y, be.z_in, y, be.z_in + be.border_height)
            _strip(mb, cx, ks, panel, mat_plain, (-sgn, 0.0), False)
            if not collision_only:
                _strip(mb, cx, ks, panel, mat_plain, (sgn, 0.0), False)
                _posts(mb, cx, ks, sel, sgn, 0.5, 3.0, 0.06, mi, below=0.3)


def _posts(mb, cx, ks, sel, sgn, frac, spacing, half, mi, below):
    """Postes (caixas) a cada `spacing` metros ao longo de s."""
    fr = cx.fr
    every = max(1, int(round(spacing / fr.step)))
    rep = cx.uv_rep
    for k in ks:
        if k % every:
            continue
        i = cx.gi(k)
        be = sel(i)
        if be is None:
            continue
        y = sgn * (be.off_in + (be.off_out - be.off_in) * frac)
        p = fr.pos[i]
        lat, t = fr.lat[i], fr.tan[i]
        th = Vector((t.x, t.y, 0.0))
        if th.length < 1e-9:
            continue
        th.normalize()
        c = Vector((p.x + lat.x * y, p.y + lat.y * y, 0.0))
        z0 = be.z_in - below
        z1 = be.z_in + be.border_height + 0.02
        corners = []
        for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            corners.append(c + th * (a * half) + lat * (b * half))
        vb = [mb.vert(Vector((q.x, q.y, z0))) for q in corners]
        vt = [mb.vert(Vector((q.x, q.y, z1))) for q in corners]
        uvq = [(0, 0), (half * 2 / rep, 0), (half * 2 / rep, (z1 - z0) / rep), (0, (z1 - z0) / rep)]
        for a in range(4):
            b = (a + 1) % 4
            mb.face([vb[a], vb[b], vt[b], vt[a]], uvq, mi, False)
        mb.face([vt[0], vt[1], vt[2], vt[3]], uvq, mi, False)


def _sweep_mesh(mb, cx, ks, bi, sgn_filter, collision_only, s0):
    """Faixa MESH: cada tira da seção varrida ao longo de s (os dois lados de uma vez)."""
    ed = cx.ed
    fr = cx.fr
    first = None
    for k in ks:
        for sgn in (1, -1):
            first = _band_at(ed, cx.gi(k), sgn, bi)
            if first is not None and first.kind == 'MESH':
                break
            first = None
        if first is not None:
            break
    if first is None or first.section is None:
        return
    band = first.band
    if collision_only and not band.collision:
        return
    sec = first.section
    rep = cx.uv_rep
    for st in sec.strips:
        ya_l, za_l = sec.points[st['a']]
        yb_l, zb_l = sec.points[st['b']]
        if sgn_filter == 1 and min(ya_l, yb_l) < -1e-4:
            continue
        if sgn_filter == -1 and max(ya_l, yb_l) > 1e-4:
            continue
        mat = None
        if st['mat'] < len(sec.materials):
            mat = sec.materials[st['mat']]
        if mat is None:
            mat = band.material if band.material is not None else _default_material('ASPHALT')
        mi = mb.mat(mat)
        sga = 1 if ya_l >= 0 else -1
        sgb = 1 if yb_l >= 0 else -1

        def pts(i, k, ya_l=ya_l, za_l=za_l, yb_l=yb_l, zb_l=zb_l, sga=sga, sgb=sgb):
            ba = _band_at(ed, i, sga, bi)
            bb = _band_at(ed, i, sgb, bi)
            if ba is None or bb is None or ba.kind != 'MESH' or bb.kind != 'MESH':
                return None
            ya = ed.mesh_lateral(ba, ya_l)
            yb = ed.mesh_lateral(bb, yb_l)
            return (ya, ed.mesh_point_z(i, ba, ya_l, za_l), yb, ed.mesh_point_z(i, bb, yb_l, zb_l))

        uvc = st['uv']
        if uvc is not None:
            A, B, C = uvc
            x0 = s0 + sec.xmin
            base = A + B * x0
            off = (math.floor(base.x), math.floor(base.y))

            def uv_fn(i, k, s, A=A, B=B, C=C, x0=x0, off=off):
                x = s + x0
                ua = A + B * x
                ub = ua + C
                return (ua.x - off[0], ua.y - off[1]), (ub.x - off[0], ub.y - off[1])
        else:
            def uv_fn(i, k, s, ya_l=ya_l, yb_l=yb_l):
                return (abs(ya_l) / rep, s / rep), (abs(yb_l) / rep, s / rep)

        def mat_fn(i, k, _mi=mi):
            return _mi
        # orientação: a da face original (MeshSection.flip já compara com a varredura)
        _strip_fixed(mb, cx, ks, pts, mat_fn, st['flip'], True, uv_fn, st.get('image'), s0)


def _strip_fixed(mb, cx, ks, pts_fn, mat_fn, flip, smooth, uv_fn, img, s0):
    """Como _strip, mas com a orientação já decidida (seção por malha)."""
    fr = cx.fr
    prev = None
    for k in ks:
        i = cx.gi(k)
        r = pts_fn(i, k)
        if r is None:
            prev = None
            continue
        ya, za, yb, zb = r
        p = fr.pos[i]
        lat = fr.lat[i]
        ia = mb.vert(Vector((p.x + lat.x * ya, p.y + lat.y * ya, za)))
        ib = mb.vert(Vector((p.x + lat.x * yb, p.y + lat.y * yb, zb)))
        ua, ub = uv_fn(i, k, cx.s_of(k) - s0) if uv_fn is not None else ((0, 0), (1, 0))
        cur = (k, ia, ib, ua, ub)
        if prev is not None:
            mi = mat_fn(i, prev[0])
            idx = [prev[1], prev[2], cur[2], cur[1]]
            uvs = [prev[3], prev[4], cur[4], cur[3]]
            if flip:
                idx.reverse()
                uvs.reverse()
            mb.face(idx, uvs, mi, smooth, img)
        prev = cur


def _lane_lines(mb, cx, ks, s0):
    """Linhas tracejadas entre as faixas de rolamento (lane_count da primeira ASPHALT)."""
    ed = cx.ed
    fr = cx.fr
    be0 = None
    for sgn in (1, -1):
        for be in ed.data[cx.gi(ks[0])][sgn]:
            if be.kind == 'ASPHALT':
                be0 = be
                break
        if be0 is not None:
            break
    if be0 is None or be0.lane_count < 2:
        return
    lanes = be0.lane_count
    mi = mb.mat(props.ensure_material('line'))
    for lane in range(1, lanes):
        frac = lane / float(lanes)
        prev = None
        for k in ks:
            i = cx.gi(k)
            s = cx.s_of(k)
            on = int(s / LINE_DASH) % 2 == 0
            y = -fr.wr[i] + (fr.wl[i] + fr.wr[i]) * frac
            p = fr.pos[i]
            lat = fr.lat[i]
            pts = []
            for dy in (-LINE_WIDTH * 0.5, LINE_WIDTH * 0.5):
                yy = y + dy
                z = ed.surface_z(i, 1 if yy >= 0 else -1, abs(yy)) + LINE_LIFT
                pts.append(Vector((p.x + lat.x * yy, p.y + lat.y * yy, z)))
            if prev is not None and prev[2]:
                a = [mb.vert(prev[0]), mb.vert(prev[1]), mb.vert(pts[1]), mb.vert(pts[0])]
                # (direita, esquerda) na amostra i e i+1: normal para cima
                a = [a[1], a[0], a[3], a[2]]
                mb.face(a, [(0, 0), (1, 0), (1, 1), (0, 1)], mi, False)
            prev = (pts[0], pts[1], on)


def chunk_ranges(frames, chunk_length):
    """[(k0, k1)] índices virtuais (k1 pode ser == count no cíclico = amostra 0)."""
    n = max(2, int(round(chunk_length / frames.step)))
    nseg = frames.count if frames.cyclic else frames.count - 1
    out = []
    k = 0
    while k < nseg:
        k1 = min(k + n, nseg)
        out.append((k, k1))
        k = k1
    if len(out) > 1 and out[-1][1] - out[-1][0] < n // 3:
        a = out.pop()
        out[-1] = (out[-1][0], a[1])
    return out


def _new_object(scene, name, me, physics):
    ob = bpy.data.objects.new(name, me)
    scene.objects.link(ob)
    ob.layers = [i == 0 for i in range(20)]
    if physics:
        ob.game.physics_type = 'STATIC'
        ob.game.use_collision_bounds = True
        ob.game.collision_bounds_type = 'TRIANGLE_MESH'
        ob.hide_render = True           # invisível no jogo e no render; colide
        ob.draw_type = 'WIRE'
    else:
        ob.game.physics_type = 'NO_COLLISION'
    return ob


def _build_chunk(cx, profile_bands, ks, collision_only):
    mb = MeshBuilder()
    s0 = math.floor(cx.s_of(ks[0]) / cx.uv_rep) * cx.uv_rep
    for bi, b in enumerate(profile_bands):
        kinds_here = set()
        for k in (ks[0], ks[len(ks) // 2], ks[-1]):
            for sgn in (1, -1):
                be = _band_at(cx.ed, cx.gi(k), sgn, bi)
                if be is not None:
                    kinds_here.add(be.kind)
        if not kinds_here:
            continue
        if 'MESH' in kinds_here:
            sf = 0 if b.side == 'BOTH' else (1 if b.side == 'LEFT' else -1)
            _sweep_mesh(mb, cx, ks, bi, sf, collision_only, s0)
        for sgn in (1, -1):
            for k in ks:
                be = _band_at(cx.ed, cx.gi(k), sgn, bi)
                if be is not None and be.kind in ROAD_KINDS and be.kind != 'MESH':
                    _sweep_parametric(mb, cx, ks, bi, sgn, collision_only)
                    break
    if not collision_only:
        _lane_lines(mb, cx, ks, s0)
    return mb


def generate_road(scene, track_obj, frames, edges):
    """Gera os blocos visuais e de colisão da estrada. Retorna a lista de objetos criados."""
    settings = track_obj.range_track
    profile = edges.profile
    bands = list(profile.bands) if profile is not None else []
    cx = _Ctx(frames, edges, settings)
    chunks = chunk_ranges(frames, getattr(settings, "chunk_length", 75.0))
    col_every = max(1, int(round(COL_STEP / frames.step)))
    objs = []
    base = track_obj.name
    for n, (k0, k1) in enumerate(chunks):
        ks = list(range(k0, k1 + 1))
        mb = _build_chunk(cx, bands, ks, False)
        if mb.f:
            ob = _new_object(scene, "%s_Road_%02d" % (base, n), mb.build("%s_Road_%02d" % (base, n)),
                             False)
            ob.range_track_owner = base
            objs.append(ob)
        kc = list(range(k0, k1 + 1, col_every))
        if kc[-1] != k1:
            kc.append(k1)
        mc = _build_chunk(cx, bands, kc, True)
        if mc.f:
            oc = _new_object(scene, "%s_RoadCol_%02d" % (base, n),
                             mc.build("%s_RoadCol_%02d" % (base, n)), True)
            oc.range_track_owner = base
            objs.append(oc)
    return objs
