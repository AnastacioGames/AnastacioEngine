# Track Tool: Light Probe Volumes ao longo da pista (plano: docs/plano-track-probes.md).
#
# plan(frames, edges, cfg) divide a pista em trechos e devolve caixas alinhadas ao mundo que
# cobrem só a faixa da pista (até a faixa `upto`) mais margem, piso e altura. Núcleo puro
# (mathutils), testável em background. A conta de sondas é a mesma do KX_ProbeVolume (C++).
import math

from mathutils import Vector

QUALITY_MAX_PROBES = {'LOW': 64, 'MEDIUM': 128, 'HIGH': 256}
QUALITY_NAME = {'LOW': "Low", 'MEDIUM': "Medium", 'HIGH': "High"}
EPS = 1e-3      # metros tirados do tamanho alinhado: ceil() da engine não ganha uma sonda a mais


class Config(object):
    """Configuração do plano. Valores padrão = os do painel."""

    def __init__(self, spacing=6.0, height=4.0, floor=1.0, margin=2.0, upto='BORDER',
                 quality='MEDIUM', max_total=15000, max_turn=15.0, max_waste=2.5):
        self.spacing = max(float(spacing), 0.5)
        self.height = float(height)
        self.floor = float(floor)
        self.margin = float(margin)
        self.upto = upto
        self.quality = quality
        self.max_total = int(max_total)
        self.max_turn = float(max_turn)
        self.max_waste = float(max_waste)

    @classmethod
    def from_settings(cls, st):
        def g(name, default):
            return getattr(st, "probe_" + name, default)
        return cls(g("spacing", 4.0), g("height", 6.0), g("floor", 1.0), g("margin", 2.0),
                   g("upto", 'BORDER'), g("quality", 'MEDIUM'), g("max_total", 2000),
                   g("max_turn", 15.0), g("max_waste", 2.5))


def engine_grid(size, spacing, max_probes):
    """(dims, spacing usado) como o construtor do KX_ProbeVolume: o espaçamento cresce 10% até a
    grade caber no limite da qualidade."""
    half = [max(s * 0.5, 0.01) for s in size]
    sp = spacing
    while True:
        dims = [max(2, int(math.ceil(2.0 * h / sp)) + 1) for h in half]
        if dims[0] * dims[1] * dims[2] <= max_probes:
            return dims, sp
        sp *= 1.1


class Box(object):
    """Caixa de um trecho: bmin/bmax alinhados ao espaçamento, amostras [i0, i1], s0/s1."""

    def __init__(self, bmin, bmax, i0, i1, s0, s1, spacing, max_probes):
        self.bmin, self.bmax = bmin, bmax
        self.i0, self.i1, self.s0, self.s1 = i0, i1, s0, s1
        self.dims, self.used_spacing = engine_grid(self.size, spacing, max_probes)
        self.probes = self.dims[0] * self.dims[1] * self.dims[2]
        self.grown = self.used_spacing > spacing * 1.01

    @property
    def size(self):
        return [self.bmax[k] - self.bmin[k] for k in range(3)]

    @property
    def center(self):
        return Vector([(self.bmin[k] + self.bmax[k]) * 0.5 for k in range(3)])

    @property
    def half(self):
        return Vector([s * 0.5 for s in self.size])

    def contains(self, p, tol=1e-4):
        return all(self.bmin[k] - tol <= p[k] <= self.bmax[k] + tol for k in range(3))


class Plan(object):
    def __init__(self, cfg, boxes, warnings):
        self.cfg = cfg
        self.boxes = boxes
        self.warnings = warnings
        self.total = sum(b.probes for b in boxes)
        self.over_limit = self.total > cfg.max_total

    def text(self):
        return "%d boxes, %d probes (limit %d)" % (len(self.boxes), self.total, self.cfg.max_total)


def section_points(fr, ed, i, cfg):
    """Pontos da seção na amostra i: centro e bordas externas (até cfg.upto) dos dois lados,
    com a altura da borda."""
    pts = [fr.pos[i].copy()]
    for side in (1, -1):
        off, z = ed.outer(i, side, cfg.upto)
        lat = fr.lat[i]
        p = fr.pos[i]
        pts.append(Vector((p.x + lat.x * side * off, p.y + lat.y * side * off, z)))
    return pts


def _heading(tan):
    return math.atan2(tan.y, tan.x)


def _angle_diff(a, b):
    d = (b - a + math.pi) % (2.0 * math.pi) - math.pi
    return abs(d)


class _Acc(object):
    """AABB e área da faixa somadas de um trecho em construção."""

    def __init__(self):
        self.lo = [1e30, 1e30, 1e30]
        self.hi = [-1e30, -1e30, -1e30]
        self.area = 0.0

    def copy(self):
        a = _Acc()
        a.lo, a.hi, a.area = list(self.lo), list(self.hi), self.area
        return a

    def add(self, pts, width, step):
        for p in pts:
            for k in range(3):
                self.lo[k] = min(self.lo[k], p[k])
                self.hi[k] = max(self.hi[k], p[k])
        self.area += width * step


def _raw_box(acc, cfg):
    m = cfg.margin
    lo = [acc.lo[0] - m, acc.lo[1] - m, acc.lo[2] - cfg.floor]
    hi = [acc.hi[0] + m, acc.hi[1] + m, acc.hi[2] + cfg.height]
    return lo, hi


def _aligned(lo, hi, sp):
    """Caixa alinhada a múltiplos do espaçamento no mundo (sondas de caixas vizinhas caem nos
    mesmos pontos). EPS tira a sonda a mais que o ceil() da engine daria no tamanho exato."""
    bmin, bmax = [], []
    for k in range(3):
        a = math.floor(lo[k] / sp) * sp
        b = math.ceil(hi[k] / sp) * sp
        if b - a < sp:
            b = a + sp
        bmin.append(a + EPS * 0.5)
        bmax.append(b - EPS * 0.5)
    return Vector(bmin), Vector(bmax)


def _waste(acc, cfg):
    lo, hi = _raw_box(acc, cfg)
    box = max(hi[0] - lo[0], 1e-6) * max(hi[1] - lo[1], 1e-6) * max(hi[2] - lo[2], 1e-6)
    band = max(acc.area, 1e-6) * (cfg.height + cfg.floor + (acc.hi[2] - acc.lo[2]))
    return box / band


def _trim_pair(a, b, sp, max_probes):
    """Corta de b a fatia que já está dentro de a, deixando um plano de sondas em comum (a troca de
    volume entre blocos vizinhos continua sem degrau). Só corta quando a fatia inteira está dentro
    de a nos outros dois eixos: a cobertura não muda."""
    best = None
    for k in range(3):
        others = [j for j in range(3) if j != k]
        if not all(a.bmin[j] - 1e-4 <= b.bmin[j] and b.bmax[j] <= a.bmax[j] + 1e-4 for j in others):
            continue
        if b.bmin[k] < a.bmax[k] and b.bmax[k] > a.bmax[k]:
            new = a.bmax[k] - sp + EPS
            if new > b.bmin[k] + 1e-4:
                gain = new - b.bmin[k]
                if best is None or gain > best[0]:
                    best = (gain, k, 'min', new)
        if b.bmax[k] > a.bmin[k] and b.bmin[k] < a.bmin[k]:
            new = a.bmin[k] + sp - EPS
            if new < b.bmax[k] - 1e-4:
                gain = b.bmax[k] - new
                if best is None or gain > best[0]:
                    best = (gain, k, 'max', new)
    if best is None:
        return False
    _, k, end, new = best
    if end == 'min':
        b.bmin[k] = new
    else:
        b.bmax[k] = new
    b.dims, b.used_spacing = engine_grid(b.size, sp, max_probes)
    b.probes = b.dims[0] * b.dims[1] * b.dims[2]
    return True


def _trim_overlap(boxes, sp, max_probes):
    for a, b in zip(boxes, boxes[1:]):
        if not _trim_pair(a, b, sp, max_probes):
            _trim_pair(b, a, sp, max_probes)


def plan(fr, ed, cfg=None):
    """Plano das caixas. Trechos crescem enquanto: a curva desde o início do trecho fica abaixo
    de max_turn, a caixa alinhada ao mundo desperdiça até max_waste vezes o volume da faixa e a
    grade cabe no limite da qualidade sem aumentar o espaçamento. Um trecho tem ao menos
    2 espaçamentos (curva fechada não vira uma caixa por amostra)."""
    cfg = cfg or Config()
    sp = cfg.spacing
    max_probes = QUALITY_MAX_PROBES.get(cfg.quality, 128)
    n = fr.count
    last = n if fr.cyclic else n - 1     # amostra final (n = volta para 0 no cíclico)
    min_len = 2.0 * sp
    warnings = []

    sec = {}

    def section(i):
        j = fr.wrap(i) if fr.cyclic else i
        if j not in sec:
            pts = section_points(fr, ed, j, cfg)
            width = (pts[1].to_2d() - pts[2].to_2d()).length + 2.0 * cfg.margin
            sec[j] = (pts, width)
        return sec[j]

    def s_of(i):
        return fr.length if (fr.cyclic and i == n) else fr.s[min(i, n - 1)]

    def tan_of(i):
        return fr.tan[fr.wrap(i) if fr.cyclic else i]

    boxes = []
    a = 0
    while a < last:
        acc = _Acc()
        pts, w = section(a)
        acc.add(pts, w, 0.0)
        h0 = _heading(tan_of(a))
        b = a
        acc_fits = True
        while b < last:
            c = b + 1
            nxt = acc.copy()
            pts, w = section(c)
            nxt.add(pts, w, s_of(c) - s_of(b))
            length = s_of(c) - s_of(a)
            lo, hi = _raw_box(nxt, cfg)
            bmin, bmax = _aligned(lo, hi, sp)
            dims, used = engine_grid([bmax[k] - bmin[k] for k in range(3)], sp, max_probes)
            fits = used <= sp * 1.01
            # Seção larga demais para a qualidade (nem um passo cabe): segue até min_len e a engine
            # aumenta o espaçamento; o plano avisa uma vez com o espaçamento que cabe.
            if b > a and not fits and acc_fits:
                break
            acc_fits = fits
            if length > min_len and b > a:
                if _angle_diff(h0, _heading(tan_of(c))) > math.radians(cfg.max_turn):
                    break
                if _waste(nxt, cfg) > cfg.max_waste:
                    break
            acc = nxt
            b = c
        lo, hi = _raw_box(acc, cfg)
        bmin, bmax = _aligned(lo, hi, sp)
        box = Box(bmin, bmax, a, b, s_of(a), s_of(b), sp, max_probes)
        boxes.append(box)
        a = b               # a próxima caixa começa na última amostra desta: sobreposição
    _trim_overlap(boxes, sp, max_probes)
    if fr.cyclic and len(boxes) > 2:
        _trim_pair(boxes[-1], boxes[0], sp, max_probes)
    grown = [b for b in boxes if b.grown]
    if grown:
        need = max(b.used_spacing for b in grown)
        warnings.append("%d of %d boxes: the track is too wide for %d probes (%s) at %.1f m; use High "
                        "quality or a spacing of about %.1f m" % (len(grown), len(boxes), max_probes,
                                                                 QUALITY_NAME.get(cfg.quality, cfg.quality),
                                                                 sp, math.ceil(need * 2.0) / 2.0))
    result = Plan(cfg, boxes, warnings)
    result.grown = len(grown)
    if result.over_limit:
        result.warnings.append("%d probes over the limit %d: raise the spacing or the limit"
                               % (result.total, cfg.max_total))
    return result


def uncovered(fr, ed, result, cfg=None):
    """Amostras cujos pontos da seção (centro e bordas, no chão e na altura) ficam fora de todas
    as caixas. Lista de índices (vazia = cobertura total)."""
    cfg = cfg or result.cfg
    out = []
    for i in range(fr.count):
        pts = section_points(fr, ed, i, cfg)
        pts += [p + Vector((0.0, 0.0, cfg.height * 0.99)) for p in pts]
        for p in pts:
            if not any(b.contains(p) for b in result.boxes):
                out.append(i)
                break
    return out


def suggest_spacing(fr, ed, cfg):
    """Menor espaçamento (passos de 0,5 m) cujo total cabe no limite, ou None."""
    sp = cfg.spacing
    for _ in range(64):
        c = Config(sp, cfg.height, cfg.floor, cfg.margin, cfg.upto, cfg.quality, cfg.max_total,
                   cfg.max_turn, cfg.max_waste)
        if not plan(fr, ed, c).over_limit:
            return sp
        sp += 0.5
    return None


def box_edges(box):
    """12 arestas (pares de Vector) da caixa, para o overlay."""
    lo, hi = box.bmin, box.bmax
    c = [Vector((x, y, z)) for z in (lo.z, hi.z) for y in (lo.y, hi.y) for x in (lo.x, hi.x)]
    idx = ((0, 1), (2, 3), (4, 5), (6, 7), (0, 2), (1, 3), (4, 6), (5, 7),
           (0, 4), (1, 5), (2, 6), (3, 7))
    return [(c[a], c[b]) for a, b in idx]
