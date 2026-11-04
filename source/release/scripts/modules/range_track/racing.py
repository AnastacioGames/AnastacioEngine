# Track Tool: linha ideal (Python puro, sem bpy).
#
# A linha ideal é um deslocamento lateral `race[i]` por amostra (+ = esquerda), dentro de
# [-(wr - margem), wl - margem], que minimiza a curvatura do caminho
#     q_i = c_i + race_i * l_i      (XY; c = centro, l = lateral horizontal unitária)
# medida pela soma de |q_{i-1} - 2 q_i + q_{i+1}|² ("minimum curvature").
#
# Método (determinístico): Gauss-Seidel projetado. Para cada i, com os vizinhos fixos, o ótimo é
#     race_i -= (sum_j w_j d_j) . l_i / sum_j w_j²,   d_j = q_{j-1} - 2 q_j + q_{j+1}
# com j em {i-1 (w=1), i (w=-2), i+1 (w=1)} entre os d_j que existem; no miolo isso é a 4ª
# diferença (q_{i-2} - 4 q_{i-1} + 6 q_i - 4 q_{i+1} + q_{i+2}) / 6. Depois limita ao intervalo.
# Como esse operador converge devagar nos comprimentos de onda longos, resolve primeiro numa
# versão rala da pista (uma amostra a cada `stride`, de ~32 m até 1) e interpola o resultado para
# o nível seguinte (pirâmide grosso -> fino). Pista aberta: pontas no centro (fixas).

import math

MARGIN = 1.0          # folga até a borda do asfalto (m)
_TOL = 1e-4           # para quando a maior mudança de um passe fica abaixo disto (m)
_ITER_COARSE = 400    # passes máximos nos níveis ralos
_ITER_FINE = 60       # passes máximos no nível final (1 amostra)


def _bounds(wl, wr, margin):
    lo = []
    hi = []
    for a, b in zip(wl, wr):
        h = a - margin
        l = -(b - margin)
        if l > h:  # pista mais estreita que 2 margens: meio do asfalto
            l = h = 0.5 * (a - b)
        lo.append(l)
        hi.append(h)
    return lo, hi


def _stencil(m, cyclic):
    """Por amostra: (i, a2, a1, b1, b2, c2a, c1a, c0, c1b, c2b, 1/sum w²) ou None (fixa)."""
    out = []
    for i in range(m):
        if cyclic:
            out.append((i, (i - 2) % m, (i - 1) % m, (i + 1) % m, (i + 2) % m,
                        1.0, -4.0, 6.0, -4.0, 1.0, 1.0 / 6.0))
            continue
        if i == 0 or i == m - 1:
            continue
        coef = {}
        w2 = 0.0
        for j, w in ((i - 1, 1.0), (i, -2.0), (i + 1, 1.0)):
            if 1 <= j <= m - 2:
                for idx, c in ((j - 1, 1.0), (j, -2.0), (j + 1, 1.0)):
                    coef[idx] = coef.get(idx, 0.0) + w * c
                w2 += w * w
        if w2 == 0.0:
            continue
        def g(k):
            return (k, coef.get(k, 0.0)) if 0 <= k < m else (i, 0.0)
        a2, c2a = g(i - 2)
        a1, c1a = g(i - 1)
        b1, c1b = g(i + 1)
        b2, c2b = g(i + 2)
        out.append((i, a2, a1, b1, b2, c2a, c1a, coef.get(i, 0.0), c1b, c2b, 1.0 / w2))
    return out


def _relax(cx, cy, lx, ly, lo, hi, off, cyclic, iterations):
    """Gauss-Seidel projetado em `off` (alterado no lugar) num nível com m amostras."""
    m = len(cx)
    if m < 3:
        return 0
    qx = [cx[i] + off[i] * lx[i] for i in range(m)]
    qy = [cy[i] + off[i] * ly[i] for i in range(m)]
    st = _stencil(m, cyclic)
    it = 0
    for it in range(1, iterations + 1):
        change = 0.0
        for i, a2, a1, b1, b2, c2a, c1a, c0, c1b, c2b, inv in st:
            gx = c2a * qx[a2] + c1a * qx[a1] + c0 * qx[i] + c1b * qx[b1] + c2b * qx[b2]
            gy = c2a * qy[a2] + c1a * qy[a1] + c0 * qy[i] + c1b * qy[b1] + c2b * qy[b2]
            li_x = lx[i]
            li_y = ly[i]
            o0 = off[i]
            o = o0 - (gx * li_x + gy * li_y) * inv
            if o < lo[i]:
                o = lo[i]
            elif o > hi[i]:
                o = hi[i]
            d = o - o0
            if d != 0.0:
                off[i] = o
                qx[i] = cx[i] + o * li_x
                qy[i] = cy[i] + o * li_y
                if d > change:
                    change = d
                elif -d > change:
                    change = -d
        if change < _TOL:
            break
    return it


def _level_indices(n, stride, cyclic):
    idx = list(range(0, n, stride))
    if not cyclic and idx[-1] != n - 1:
        idx.append(n - 1)
    return idx


def _upsample(idx, vals, n, cyclic):
    """Interpolação linear (por índice) dos valores do nível para as n amostras."""
    out = [0.0] * n
    m = len(idx)
    for k in range(m):
        i0 = idx[k]
        v0 = vals[k]
        if k + 1 < m:
            i1 = idx[k + 1]
            v1 = vals[k + 1]
        elif cyclic:
            i1 = n
            v1 = vals[0]
        else:
            out[i0] = v0
            continue
        span = i1 - i0
        for i in range(i0, min(i1, n)):
            out[i] = v0 + (v1 - v0) * (i - i0) / span
    return out


def racing_line(px, py, lx, ly, wl, wr, cyclic, margin=MARGIN, stats=None):
    """Deslocamento lateral da linha ideal por amostra (lista de floats, + = esquerda).
    stats: lista opcional que recebe (stride, amostras, passes) de cada nível."""
    n = len(px)
    if n == 0:
        return []
    lo, hi = _bounds(wl, wr, margin)
    off = [min(max(0.0, lo[i]), hi[i]) for i in range(n)]
    if n < 3:
        return off
    # passo médio entre amostras -> strides de ~32 m até 1 amostra
    total = 0.0
    for i in range(n - 1):
        total += math.hypot(px[i + 1] - px[i], py[i + 1] - py[i])
    avg = total / (n - 1)
    stride = 1
    while stride * 2 * avg <= 32.0 and n // (stride * 2) >= 8:
        stride *= 2
    while True:
        idx = _level_indices(n, stride, cyclic)
        sub = [off[i] for i in idx]
        its = _relax([px[i] for i in idx], [py[i] for i in idx], [lx[i] for i in idx],
                     [ly[i] for i in idx], [lo[i] for i in idx], [hi[i] for i in idx], sub, cyclic,
                     _ITER_COARSE if stride > 1 else _ITER_FINE)
        if stats is not None:
            stats.append((stride, len(idx), its))
        if stride == 1:
            off = sub
            break
        off = _upsample(idx, sub, n, cyclic)
        for i in range(n):
            off[i] = min(max(off[i], lo[i]), hi[i])
        stride //= 2
    return off
