# Track Tool: amostragem do traçado (Bezier) em passo uniforme + referencial por amostra.
#
# Contrato em docs/plano-track-tool.md (frames.py). Convenções:
#   - torção Z Up: a lateral `lat` é sempre horizontal e aponta para a ESQUERDA;
#   - radius e tilt do Bezier são ignorados (largura e inclinação vêm de range_track);
#   - bank (rad): + = cai para a esquerda (borda esquerda mais baixa). Na inclinação Auto a borda
#     de DENTRO da curva fica mais baixa: curva para a esquerda (turn > 0) -> bank > 0;
#   - turn_deg: variação do rumo (graus, + = vira à esquerda) numa janela de 24 m centrada na
#     amostra (mesma grandeza do K do protótipo gerar_cenario_pista.py, em graus).
# Esta é a ÚNICA regra de sinal da inclinação: layout/sweep só usam bank daqui.
import math
from bisect import bisect_right

from mathutils import Quaternion, Vector, kdtree
from mathutils.geometry import interpolate_bezier

TURN_WINDOW = 12.0      # metros para cada lado no cálculo de turn_deg
DEFAULT_SURFACE = "asphalt"


def _clamp(x, a, b):
    return a if x < a else b if x > b else x


def _bezier_points(curve_obj):
    """(lista de (co, handle_left, handle_right) no espaço local, cíclico) da primeira spline."""
    for sp in curve_obj.data.splines:
        if sp.type == 'BEZIER' and len(sp.bezier_points) >= 2:
            pts = [(p.co.copy(), p.handle_left.copy(), p.handle_right.copy())
                   for p in sp.bezier_points]
            return pts, bool(sp.use_cyclic_u)
        if len(sp.points) >= 2:     # POLY/NURBS: usa os pontos como polilinha
            pts = []
            for p in sp.points:
                c = Vector(p.co[:3])
                pts.append((c, c.copy(), c.copy()))
            return pts, bool(sp.use_cyclic_u)
    raise ValueError("curve without a usable spline: %s" % curve_obj.name)


def _dense_polyline(curve_obj, step):
    """Polilinha densa (mundo) e o parâmetro u (índice do ponto + fração) de cada ponto."""
    mw = curve_obj.matrix_world
    bp, cyclic = _bezier_points(curve_obj)
    n = len(bp)
    segs = [(k, k + 1) for k in range(n - 1)]
    if cyclic:
        segs.append((n - 1, 0))
    pts, us = [], []
    for k, (a, b) in enumerate(segs):
        ca, _, hra = bp[a]
        cb, hlb, _ = bp[b]
        comp = (hra - ca).length + (hlb - hra).length + (cb - hlb).length
        m = max(8, int(comp / step * 4.0) + 1)
        seg = interpolate_bezier(ca, hra, hlb, cb, m)
        first = 0 if not pts else 1
        for j in range(first, m):
            pts.append(mw * seg[j])
            us.append(k + j / float(m - 1))
    return pts, us, cyclic, n


class Frames:
    """Amostras do traçado. Listas por amostra i: s, pos, tan, lat, up, bank, turn_deg, wl, wr,
    surface (e u = parâmetro do Bezier). Atributos: length, cyclic, step, count, name."""

    def __init__(self):
        self.name = ""
        self.s, self.pos, self.tan, self.lat, self.up = [], [], [], [], []
        self.bank, self.turn_deg, self.wl, self.wr, self.surface, self.u = [], [], [], [], [], []
        self.length = 0.0
        self.cyclic = False
        self.step = 1.0
        self.count = 0
        self.point_count = 0
        self.point_bank_deg = []     # inclinação final por ponto do Bezier (graus)
        self.point_turn_deg = []     # curva por ponto do Bezier (graus, regra do protótipo)
        self._kd = None

    def __len__(self):
        return self.count

    # ------------------------------------------------------------ índices
    def wrap(self, i):
        """Índice válido: cíclico dá a volta, aberto limita."""
        if self.cyclic:
            return i % self.count
        return 0 if i < 0 else self.count - 1 if i >= self.count else i

    def _norm_s(self, s):
        if self.cyclic:
            return s % self.length if self.length > 0 else 0.0
        return _clamp(s, 0.0, self.length)

    def index_at(self, s):
        """(i0, i1, t) para interpolar em s."""
        s = self._norm_s(s)
        k = s / self.step
        i0 = int(math.floor(k))
        t = k - i0
        if self.cyclic:
            i0 %= self.count
            i1 = (i0 + 1) % self.count
        else:
            if i0 >= self.count - 1:
                i0, t = self.count - 2, 1.0
            i1 = i0 + 1
        return i0, i1, t

    # ------------------------------------------------------------ consultas
    def at(self, s):
        """(pos, tan, lat, up, bank) interpolados em s."""
        i0, i1, t = self.index_at(s)
        pos = self.pos[i0].lerp(self.pos[i1], t)
        tan = self.tan[i0].lerp(self.tan[i1], t)
        if tan.length < 1e-9:
            tan = self.tan[i0].copy()
        tan.normalize()
        bank = self.bank[i0] + (self.bank[i1] - self.bank[i0]) * t
        lat = _lateral(tan, self.lat[i0])
        up = _up(tan, lat, bank)
        return pos, tan, lat, up, bank

    def _ensure_kd(self):
        if self._kd is None:
            kd = kdtree.KDTree(self.count)
            for i, p in enumerate(self.pos):
                kd.insert(Vector((p.x, p.y, 0.0)), i)
            kd.balance()
            self._kd = kd
        return self._kd

    def nearest(self, x, y):
        """(i, s, side, dist_lateral): amostra mais próxima em XY, s refinado na projeção,
        side +1 = esquerda / -1 = direita, dist_lateral >= 0."""
        kd = self._ensure_kd()
        _, i, _ = kd.find(Vector((x, y, 0.0)))
        p = self.pos[i]
        dx, dy = x - p.x, y - p.y
        th = Vector((self.tan[i].x, self.tan[i].y))
        if th.length > 1e-9:
            th.normalize()
        along = dx * th.x + dy * th.y
        along = _clamp(along, -self.step, self.step)
        s = self.s[i] + along
        if self.cyclic:
            s %= self.length
        else:
            s = _clamp(s, 0.0, self.length)
        # lateral medida no referencial interpolado (mais estável entre amostras)
        pos, tan, lat, _, _ = self.at(s)
        sl = (x - pos.x) * lat.x + (y - pos.y) * lat.y
        return i, s, (1 if sl >= 0.0 else -1), abs(sl)

    def kdtree(self):
        """KDTree (XY, z=0) das amostras, para os outros módulos."""
        return self._ensure_kd()


def _lateral(tan, fallback):
    h = Vector((-tan.y, tan.x, 0.0))
    if h.length < 1e-6:
        return fallback.copy()
    return h.normalized()


def _up(tan, lat, bank):
    """Normal da pista: perpendicular a tan e lat, girada por bank (+ = cai p/ a esquerda)."""
    up0 = tan.cross(lat)
    if up0.length < 1e-9:
        up0 = Vector((0.0, 0.0, 1.0))
    up0.normalize()
    if bank != 0.0:
        up0 = Quaternion(tan, -bank) * up0
    return up0


def _point_settings(settings, n):
    """Dados por ponto do Bezier a partir de settings.points (pontos sem item = padrão)."""
    by_index = {}
    if settings is not None:
        for p in settings.points:
            if 0 <= p.index < n:
                by_index[p.index] = p
    return by_index


def _cp_turn_deg(cps_world, cyclic):
    """Regra do protótipo (ajustar_inclinacao_pista.curvas): ângulo da curva em cada ponto do
    Bezier, no plano XY, + = vira para a esquerda."""
    n = len(cps_world)
    out = [0.0] * n
    rng = range(n) if cyclic else range(1, n - 1)
    for i in rng:
        p0, p1, p2 = cps_world[(i - 1) % n], cps_world[i], cps_world[(i + 1) % n]
        ax, ay = p1.x - p0.x, p1.y - p0.y
        bx, by = p2.x - p1.x, p2.y - p1.y
        out[i] = math.degrees(math.atan2(ax * by - ay * bx, ax * bx + ay * by))
    return out


def profile_asphalt_width(profile, default=3.5):
    """Meia largura do asfalto pelo perfil (primeira faixa ASPHALT ou MESH)."""
    if profile is not None:
        for b in profile.bands:
            if b.kind in ('ASPHALT', 'MESH') and b.width > 0.0:
                return b.width
    return default


def sample(curve_obj, settings=None, profile=None):
    """Amostra o traçado a cada settings.sample_step metros (ajustado para dividir o comprimento
    em partes iguais). profile: opcional; se None, vem de settings.profile."""
    if settings is None:
        settings = curve_obj.range_track
    if profile is None:
        try:
            from . import props
            profile = props.find_profile(settings.profile, props.track_scene(curve_obj))
        except Exception:
            profile = None
    step_req = max(0.05, float(getattr(settings, "sample_step", 1.0) or 1.0))

    dense, us, cyclic, ncp = _dense_polyline(curve_obj, step_req)
    cum = [0.0]
    for a, b in zip(dense[:-1], dense[1:]):
        cum.append(cum[-1] + (b - a).length)
    total = cum[-1]
    if total <= 1e-6:
        raise ValueError("track with zero length: %s" % curve_obj.name)
    nseg = max(1, int(round(total / step_req)))
    step = total / nseg
    count = nseg if cyclic else nseg + 1

    fr = Frames()
    fr.name = curve_obj.name
    fr.cyclic = cyclic
    fr.length = total
    fr.step = step
    fr.count = count
    fr.point_count = ncp

    # posições e parâmetro u em s uniforme
    j = 0
    last = len(dense) - 1
    for k in range(count):
        s = k * step if k < nseg else total
        while j < last - 1 and cum[j + 1] < s:
            j += 1
        seg = cum[j + 1] - cum[j]
        t = (s - cum[j]) / seg if seg > 1e-12 else 0.0
        t = _clamp(t, 0.0, 1.0)
        fr.s.append(s)
        fr.pos.append(dense[j].lerp(dense[j + 1], t))
        fr.u.append(us[j] + (us[j + 1] - us[j]) * t)

    # tangente 3D (diferença central) e lateral horizontal (esquerda)
    lat_prev = Vector((0.0, 1.0, 0.0))
    for i in range(count):
        if cyclic:
            a, b = fr.pos[(i - 1) % count], fr.pos[(i + 1) % count]
        else:
            a, b = fr.pos[max(0, i - 1)], fr.pos[min(count - 1, i + 1)]
        t3 = b - a
        if t3.length < 1e-9:
            t3 = fr.tan[-1].copy() if fr.tan else Vector((1.0, 0.0, 0.0))
        t3.normalize()
        lat = _lateral(t3, lat_prev)
        lat_prev = lat
        fr.tan.append(t3)
        fr.lat.append(lat)

    # turn_deg (janela de +-12 m)
    w = max(1, int(round(TURN_WINDOW / step)))
    for i in range(count):
        if cyclic:
            ta, tb = fr.lat[(i - w) % count], fr.lat[(i + w) % count]
        else:
            ta, tb = fr.lat[max(0, i - w)], fr.lat[min(count - 1, i + w)]
        # lat é o rumo girado de 90 graus: o ângulo entre lats = ângulo entre rumos
        ang = math.atan2(ta.x * tb.y - ta.y * tb.x, ta.x * tb.x + ta.y * tb.y)
        fr.turn_deg.append(math.degrees(ang))

    # dados por ponto de controle: largura, inclinação, piso
    mw = curve_obj.matrix_world
    bp, _ = _bezier_points(curve_obj)
    cps_world = [mw * c for c, _, _ in bp]
    pset = _point_settings(settings, ncp)
    wdef = profile_asphalt_width(profile)

    turn_cp = _cp_turn_deg(cps_world, cyclic)
    gain = float(getattr(settings, "bank_gain", 0.08))
    bmax = float(getattr(settings, "bank_max", 6.0))
    auto_on = bool(getattr(settings, "bank_auto", True))
    raw = [_clamp(t * gain, -bmax, bmax) if auto_on else 0.0 for t in turn_cp]
    smooth = raw[:]
    if cyclic:
        for i in range(ncp):
            smooth[i] = 0.25 * raw[(i - 1) % ncp] + 0.5 * raw[i] + 0.25 * raw[(i + 1) % ncp]
    else:
        for i in range(1, ncp - 1):
            smooth[i] = 0.25 * raw[i - 1] + 0.5 * raw[i] + 0.25 * raw[i + 1]
        smooth[0] = smooth[-1] = 0.0
    bank_cp, wl_cp, wr_cp, surf_cp = [], [], [], []
    surf_last = DEFAULT_SURFACE
    for i in range(ncp):
        p = pset.get(i)
        if p is not None and p.bank_mode == 'MANUAL':
            bank_cp.append(p.bank_deg)
        else:
            bank_cp.append(smooth[i])
        wl_cp.append(p.width_left if p is not None and p.width_left > 0.0 else wdef)
        wr_cp.append(p.width_right if p is not None and p.width_right > 0.0 else wdef)
        if p is not None and p.surface:
            surf_last = p.surface
        surf_cp.append(surf_last)
    fr.point_turn_deg = turn_cp
    fr.point_bank_deg = bank_cp

    for i in range(count):
        u = fr.u[i]
        k0 = int(math.floor(u))
        t = u - k0
        k0 = k0 % ncp if cyclic else min(k0, ncp - 1)
        k1 = (k0 + 1) % ncp if cyclic else min(k0 + 1, ncp - 1)
        bdeg = bank_cp[k0] + (bank_cp[k1] - bank_cp[k0]) * t
        b = math.radians(bdeg)
        fr.bank.append(b)
        fr.wl.append(wl_cp[k0] + (wl_cp[k1] - wl_cp[k0]) * t)
        fr.wr.append(wr_cp[k0] + (wr_cp[k1] - wr_cp[k0]) * t)
        fr.surface.append(surf_cp[k0])
        fr.up.append(_up(fr.tan[i], fr.lat[i], b))
    return fr
