# Track Tool: faixas do perfil no espaço (bordas por amostra, já com inclinação e trechos).
#
# Contrato em docs/plano-track-tool.md (layout.py). Convenções:
#   - side: +1 = esquerda (+lat), -1 = direita (também aceita 'LEFT'/'RIGHT');
#   - off: deslocamento lateral HORIZONTAL a partir do centro (>= 0); z: altura absoluta (mundo);
#   - a inclinação é um cisalhamento: z = pos.z + nível - (side*off)*tan(bank). Os degraus
#     (guia, mureta) continuam verticais e a largura em XY é exata;
#   - faixas "da pista" (ASPHALT, CURB, SIDEWALK, BORDER, MESH) seguem a inclinação; SLOPE e HILL
#     partem da borda externa da faixa anterior (sem inclinação própria);
#   - SLOPE: z_out = z_in + width*tan(slope_deg) (+ sobe/corte, - desce/aterro);
#   - HILL: z_out = z_in + height; BORDER: z_in/z_out = chão da mureta (topo = + border_height);
#   - trechos: efeito total em [s_start, s_end], transição linear de `blend` metros FORA do
#     intervalo; troca de tipo/borda acontece no meio da transição (peso >= 0.5).
import math

from mathutils import Vector

ROAD_KINDS = ('ASPHALT', 'CURB', 'SIDEWALK', 'BORDER', 'MESH')
SECTION_TOL = 0.005     # metros: pontos da seção mais perto que isso viram um só


def side_sign(side):
    if side in ('LEFT', 'L', 1, 1.0):
        return 1
    if side in ('RIGHT', 'R', -1, -1.0):
        return -1
    return 1 if side > 0 else -1


def _side_ok(band_side, sgn):
    return band_side == 'BOTH' or (band_side == 'LEFT' and sgn > 0) or (band_side == 'RIGHT' and sgn < 0)


# ---------------------------------------------------------------- seção por malha
class MeshSection:
    """Seção tirada de uma malha: Y local = lateral (+ esquerda), Z = altura, X = ao longo.

    points: [(y, z)]; strips: dicts {a, b, mat, uv (A, B, C) ou None, flip}. uv(x, t) = A + B*x
    + C*t, com t = 0 em a e 1 em b, x em metros ao longo (mantém a UV original da malha)."""

    def __init__(self, obj):
        self.name = obj.name
        me = obj.data
        sx, sy, sz = obj.scale
        verts = [Vector((v.co.x * sx, v.co.y * sy, v.co.z * sz)) for v in me.vertices]
        self.materials = [m for m in me.materials]
        self.xmin = min((v.x for v in verts), default=0.0)
        self.xmax = max((v.x for v in verts), default=0.0)
        self.points = []
        tol2 = SECTION_TOL * SECTION_TOL

        def key_of(v):
            # junta pontos da seção a menos de SECTION_TOL (malhas com 0.105/0.106 na mesma guia)
            for k, (y, z) in enumerate(self.points):
                if (y - v.y) ** 2 + (z - v.z) ** 2 <= tol2:
                    return k
            self.points.append((v.y, v.z))
            return len(self.points) - 1

        vkey = [key_of(v) for v in verts]
        uvl = me.uv_layers[0].data if len(me.uv_layers) else None
        self.strips = []
        seen = set()
        self.skipped = 0
        for poly in me.polygons:
            lis = list(poly.loop_indices)
            vis = [me.loops[li].vertex_index for li in lis]
            ks = sorted(set(vkey[v] for v in vis))
            xs = [verts[v].x for v in vis]
            if len(ks) != 2 or max(xs) - min(xs) < 1e-5:
                self.skipped += 1
                continue
            a, b = ks
            sk = (a, b, poly.material_index)
            if sk in seen:
                continue
            seen.add(sk)
            uv = None
            if uvl is not None:
                samples = {a: [], b: []}
                for li, v in zip(lis, vis):
                    samples[vkey[v]].append((verts[v].x, uvl[li].uv.copy()))
                B = None
                for k in (a, b):
                    sm = sorted(samples[k], key=lambda q: q[0])
                    if len(sm) >= 2 and sm[-1][0] - sm[0][0] > 1e-5:
                        B = (sm[-1][1] - sm[0][1]) / (sm[-1][0] - sm[0][0])
                        break
                if B is not None and samples[a] and samples[b]:
                    xa, uva = samples[a][0]
                    xb, uvb = samples[b][0]
                    A = uva - B * xa                    # uv em x = 0 no lado a
                    C = (uvb - B * xb) - A              # diferença entre os lados em x igual
                    uv = (A, B, C)
            ya, za = self.points[a]
            yb, zb = self.points[b]
            dy, dz = yb - ya, zb - za
            n = poly.normal
            flip = (dz * n.y - dy * n.z) < 0.0
            img = me.uv_textures[0].data[poly.index].image if len(me.uv_textures) else None
            self.strips.append({'a': a, 'b': b, 'mat': poly.material_index, 'uv': uv, 'flip': flip,
                                'image': img})
        if not self.strips:                          # perfil desenhado só com arestas
            for e in me.edges:
                a, b = vkey[e.vertices[0]], vkey[e.vertices[1]]
                if a == b:
                    continue
                a, b = min(a, b), max(a, b)
                if (a, b, 0) in seen:
                    continue
                seen.add((a, b, 0))
                ya, za = self.points[a]
                yb, zb = self.points[b]
                # normal para cima/para o centro
                flip = (zb - za) * 0.0 - (yb - ya) * 1.0 < 0.0
                self.strips.append({'a': a, 'b': b, 'mat': 0, 'uv': None, 'flip': flip})
        # envoltória de cima por lado: [(|y|, z)] crescente
        self.envelope = {}
        for sgn in (1, -1):
            best = {}
            for y, z in self.points:
                if y * sgn >= -1e-4:
                    k = round(abs(y), 4)
                    if k not in best or z > best[k]:
                        best[k] = z
            self.envelope[sgn] = sorted(best.items())
        self.extent = {sgn: (self.envelope[sgn][-1][0] if self.envelope[sgn] else 0.0)
                       for sgn in (1, -1)}

    def inner(self, sgn):
        env = self.envelope[sgn]
        return env[0][0] if env else 0.0

    def z_at(self, sgn, ay):
        """Altura (local) da envoltória de cima em |y| = ay."""
        env = self.envelope[sgn]
        if not env:
            return 0.0
        if ay <= env[0][0]:
            return env[0][1]
        for (y0, z0), (y1, z1) in zip(env[:-1], env[1:]):
            if ay <= y1:
                if y1 - y0 < 1e-9:
                    return max(z0, z1)
                return z0 + (z1 - z0) * (ay - y0) / (y1 - y0)
        return env[-1][1]

    def riser_offset(self, sgn):
        """Menor |y| de um degrau vertical (guia) no lado: meia largura do asfalto da seção."""
        best = None
        for st in self.strips:
            ya, za = self.points[st['a']]
            yb, zb = self.points[st['b']]
            if abs(zb - za) > 2.0 * abs(yb - ya) and abs(zb - za) > 0.02:
                y = (ya + yb) * 0.5
                if y * sgn > 0.05 and (best is None or abs(y) < best):
                    best = abs(y)
        return best if best is not None else self.extent[sgn]


_section_cache = {}


def mesh_section(obj):
    """MeshSection com cache (invalida quando a malha muda de tamanho/nome)."""
    me = obj.data
    key = (obj.name, me.name, len(me.vertices), len(me.polygons), tuple(obj.scale))
    sec = _section_cache.get(key)
    if sec is None:
        sec = MeshSection(obj)
        _section_cache.clear() if len(_section_cache) > 32 else None
        _section_cache[key] = sec
    return sec


# ---------------------------------------------------------------- bordas
class BandEdge(object):
    __slots__ = ('name', 'kind', 'side', 'off_in', 'off_out', 'z_in', 'z_out', 'band', 'width',
                 'height', 'slope_deg', 'border_type', 'border_height', 'material', 'mesh_object',
                 'collision', 'lane_count', 'kerb_on_curves', 'scale', 'shift', 'h_base', 'section',
                 'index')

    def tup(self):
        return (self.off_in, self.off_out, self.z_in, self.z_out)


class _Seg(object):
    __slots__ = ('s0', 's1', 'blend', 'side', 'band', 'kind', 'width', 'height', 'slope_deg',
                 'border_type')


def _seg_weight(seg, s, length, cyclic):
    def w1(x):
        if seg.s0 <= x <= seg.s1:
            return 1.0
        if seg.blend <= 0.0:
            return 0.0
        if seg.s0 - seg.blend < x < seg.s0:
            return (x - (seg.s0 - seg.blend)) / seg.blend
        if seg.s1 < x < seg.s1 + seg.blend:
            return 1.0 - (x - seg.s1) / seg.blend
        return 0.0
    w = w1(s)
    if cyclic and length > 0.0:
        w = max(w, w1(s + length), w1(s - length))
    return w


class Edges:
    """Bordas das faixas por amostra. data[i][side] = lista de BandEdge (centro -> fora)."""

    def __init__(self, frames, profile, settings):
        self.frames = frames
        self.profile = profile
        self.settings = settings
        self.data = []
        self._kd_cache = {}

    # ------------------------------------------------------------ consulta das faixas
    def bands(self, i, side):
        return self.data[self.frames.wrap(i)][side_sign(side)]

    def find(self, i, side, name_or_kind):
        """BandEdge pelo nome (primeiro) ou pelo tipo; None se não existe nesse lado."""
        lst = self.bands(i, side)
        for be in lst:
            if be.name == name_or_kind:
                return be
        for be in lst:
            if be.kind == name_or_kind:
                return be
        return None

    def band(self, i, side, name_or_kind):
        """(off_in, off_out, z_in, z_out) da faixa, ou None se não existe nesse lado."""
        be = self.find(i, side, name_or_kind)
        return be.tup() if be is not None else None

    def outer(self, i, side, upto=None):
        """(off, z) da borda externa até a faixa `upto` (None = última). Se `upto` não existe
        nesse lado, usa a última faixa da pista (antes de SLOPE/HILL)."""
        lst = self.bands(i, side)
        if not lst:
            return 0.0, self.frames.pos[self.frames.wrap(i)].z
        if upto is None:
            be = lst[-1]
        else:
            be = self.find(i, side, upto)
            if be is None:
                road = [b for b in lst if b.kind in ROAD_KINDS]
                be = road[-1] if road else lst[0]
        return be.off_out, be.z_out

    def surface_z(self, i, side, off):
        """Altura do chão/superfície na distância lateral off (>= 0) do lado."""
        i = self.frames.wrap(i)
        sgn = side_sign(side)
        lst = self.data[i][sgn]
        if not lst:
            return self.frames.pos[i].z
        if off <= lst[0].off_in:
            return lst[0].z_in
        for be in lst:
            if off <= be.off_out:
                if be.kind == 'MESH' and be.section is not None:
                    return self._mesh_z(i, sgn, be, off)
                w = be.off_out - be.off_in
                if w <= 1e-9:
                    return be.z_out
                return be.z_in + (be.z_out - be.z_in) * (off - be.off_in) / w
        return lst[-1].z_out

    def point(self, i, side, off, z_extra=0.0):
        """Vector no mundo: lateral off (>= 0) do lado, na altura da superfície + z_extra."""
        i = self.frames.wrap(i)
        sgn = side_sign(side)
        p = self.frames.pos[i]
        lat = self.frames.lat[i]
        z = self.surface_z(i, sgn, off) + z_extra
        return Vector((p.x + lat.x * sgn * off, p.y + lat.y * sgn * off, z))

    def world(self, i, y, z_abs):
        """Ponto com lateral assinada y (+ esquerda) e altura absoluta."""
        p = self.frames.pos[i]
        lat = self.frames.lat[i]
        return Vector((p.x + lat.x * y, p.y + lat.y * y, z_abs))

    # ------------------------------------------------------------ malha (MESH)
    def mesh_lateral(self, be, y_local):
        """Lateral assinada (mundo) de um y da seção, com a escala do lado."""
        sgn = 1 if y_local >= 0.0 else -1
        ay = abs(y_local)
        return sgn * (be.off_in + (ay - be.shift) * be.scale[sgn])

    def mesh_point_z(self, i, be, y_local, z_local):
        """Altura absoluta de um ponto (y, z) da seção na amostra i."""
        y = self.mesh_lateral(be, y_local)
        f = self.frames
        return f.pos[i].z + be.h_base + z_local - y * math.tan(f.bank[i])

    def _mesh_z(self, i, sgn, be, off):
        sc = be.scale[sgn] if be.scale[sgn] > 1e-9 else 1.0
        ay = (off - be.off_in) / sc + be.shift
        zl = be.section.z_at(sgn, ay)
        return self.frames.pos[i].z + be.h_base + zl - sgn * off * math.tan(self.frames.bank[i])

    # ------------------------------------------------------------ distância à borda
    def _edge_kd(self):
        return self.frames.kdtree()

    def dist_to_edge(self, x, y, upto='BORDER'):
        """Distância XY até a borda (externa da faixa `upto`) mais próxima, considerando os
        trechos vizinhos. Negativa dentro da pista."""
        f = self.frames
        kd = self._edge_kd()
        maxw = self._max_outer(upto)
        q = Vector((x, y, 0.0))
        best = None
        lim = f.step * 1.01
        for _, i, _ in kd.find_range(q, maxw + 2.0 * f.step + 1.0):
            p = f.pos[i]
            dx, dy = x - p.x, y - p.y
            t = f.tan[i]
            th = math.hypot(t.x, t.y)
            if th < 1e-9:
                continue
            along = (dx * t.x + dy * t.y) / th
            beyond = abs(along) > lim
            if beyond and not (not f.cyclic and ((i == 0 and along < 0) or
                                                 (i == f.count - 1 and along > 0))):
                continue
            lt = f.lat[i]
            sl = dx * lt.x + dy * lt.y
            eo, _ = self.outer(i, 1 if sl >= 0 else -1, upto)
            d = sl - eo if sl >= 0 else -sl - eo
            if beyond:                               # além das pontas da pista aberta
                d = math.hypot(max(d, 0.0), abs(along) - lim)
            if best is None or d < best:
                best = d
        if best is None:
            _, i, dist = kd.find(q)
            eo = max(self.outer(i, 1, upto)[0], self.outer(i, -1, upto)[0])
            best = dist - eo
        return best

    def _max_outer(self, upto):
        key = upto
        v = self._kd_cache.get(key)
        if v is None:
            v = 0.0
            for i in range(self.frames.count):
                for sgn in (1, -1):
                    v = max(v, self.outer(i, sgn, upto)[0])
            self._kd_cache[key] = v
        return v


def _segments(settings):
    out = []
    if settings is None:
        return out
    for sg in settings.segments:
        g = _Seg()
        g.s0, g.s1 = min(sg.s_start, sg.s_end), max(sg.s_start, sg.s_end)
        g.blend = max(0.0, sg.blend)
        g.side = sg.side
        g.band = sg.band
        g.kind = sg.kind.strip().upper()
        g.width = sg.width
        g.height = sg.height
        g.slope_deg = sg.slope_deg
        g.border_type = sg.border_type
        out.append(g)
    return out


def band_edges(frames, profile, settings=None):
    """Monta as bordas de todas as faixas do perfil em cada amostra (contrato: Edges)."""
    if settings is None:
        settings = getattr(frames, "settings", None)
    ed = Edges(frames, profile, settings)
    bands = list(profile.bands) if profile is not None else []
    segs = _segments(settings)
    sections = {}
    for b in bands:
        if b.kind == 'MESH' and b.mesh_object is not None and b.mesh_object.type == 'MESH':
            sections[b.as_pointer()] = mesh_section(b.mesh_object)

    for i in range(frames.count):
        s = frames.s[i]
        pos = frames.pos[i]
        tb = math.tan(frames.bank[i])
        active = [(g, _seg_weight(g, s, frames.length, frames.cyclic)) for g in segs]
        active = [(g, w) for g, w in active if w > 0.0]
        per_side = {}
        for sgn in (1, -1):
            lst = []
            off = 0.0
            h = 0.0                 # nível relativo (sem inclinação) da pista
            z_prev = pos.z
            on_road = True
            first_road = True
            for bi, b in enumerate(bands):
                if not _side_ok(b.side, sgn):
                    continue
                kind = b.kind
                width = b.width
                height = b.height
                slope = b.slope_deg
                btype = b.border_type
                for g, w in active:
                    if not _side_ok(g.side, sgn):
                        continue
                    if g.band and g.band != b.name and g.band != b.kind:
                        continue
                    if g.kind and w >= 0.5:
                        kind = g.kind
                    if g.width >= 0.0:
                        width = width + (g.width - width) * w
                    if g.height >= 0.0:
                        height = height + (g.height - height) * w
                    if g.slope_deg != 0.0:
                        slope = slope + (g.slope_deg - slope) * w
                    if g.border_type != 'KEEP' and w >= 0.5:
                        btype = g.border_type
                be = BandEdge()
                be.index = bi
                be.name = b.name
                be.kind = kind
                be.side = sgn
                be.band = b
                be.height = height
                be.slope_deg = slope
                be.border_type = btype
                be.border_height = b.border_height
                be.material = b.material
                be.mesh_object = b.mesh_object
                be.collision = b.collision
                be.lane_count = b.lane_count
                be.kerb_on_curves = b.kerb_on_curves
                be.scale = {1: 1.0, -1: 1.0}
                be.shift = 0.0
                be.h_base = 0.0
                be.section = None
                wside = frames.wl[i] if sgn > 0 else frames.wr[i]
                if kind == 'MESH':
                    sec = sections.get(b.as_pointer())
                    be.section = sec
                    if sec is None:
                        be.kind = kind = 'ASPHALT' if first_road else 'SIDEWALK'
                if kind == 'MESH':
                    sec = be.section
                    if first_road and off == 0.0:
                        ref = b.width if b.width > 0.0 else sec.riser_offset(sgn)
                        k = wside / ref if ref > 1e-6 else 1.0
                        be.scale = {1: (frames.wl[i] / ref if ref > 1e-6 else 1.0),
                                    -1: (frames.wr[i] / ref if ref > 1e-6 else 1.0)}
                        be.shift = 0.0
                        be.h_base = 0.0
                        be.off_in = 0.0
                        be.off_out = sec.extent[sgn] * k
                    else:
                        be.shift = sec.inner(sgn)
                        be.h_base = h
                        be.off_in = off
                        be.off_out = off + (sec.extent[sgn] - be.shift)
                    be.width = be.off_out - be.off_in
                    zl_in = sec.z_at(sgn, sec.inner(sgn) if be.shift else 0.0)
                    zl_out = sec.z_at(sgn, sec.extent[sgn])
                    be.z_in = pos.z + be.h_base + zl_in - sgn * be.off_in * tb
                    be.z_out = pos.z + be.h_base + zl_out - sgn * be.off_out * tb
                    h = be.h_base + zl_out
                    first_road = False
                elif kind in ROAD_KINDS and on_road:
                    if kind == 'ASPHALT' and first_road:
                        width = wside - off
                    be.width = max(0.0, width)
                    h = h + height
                    be.off_in = off
                    be.off_out = off + be.width
                    be.z_in = pos.z + h - sgn * be.off_in * tb
                    be.z_out = pos.z + h - sgn * be.off_out * tb
                    first_road = False
                elif kind == 'SLOPE':
                    on_road = False
                    be.width = max(0.0, width)
                    be.off_in = off
                    be.off_out = off + be.width
                    be.z_in = z_prev
                    be.z_out = be.z_in + be.width * math.tan(math.radians(slope))
                elif kind == 'HILL':
                    on_road = False
                    be.width = max(0.0, width)
                    be.off_in = off
                    be.off_out = off + be.width
                    be.z_in = z_prev
                    be.z_out = z_prev + height
                else:                               # faixa da pista depois do talude: plana
                    be.width = max(0.0, width)
                    be.off_in = off
                    be.off_out = off + be.width
                    be.z_in = z_prev + height
                    be.z_out = be.z_in
                off = be.off_out
                z_prev = be.z_out
                lst.append(be)
            per_side[sgn] = lst
        ed.data.append(per_side)
    return ed
