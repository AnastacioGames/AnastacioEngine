# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
# ##### END GPL LICENSE BLOCK #####

"""Atlas "Casas_Atlas": uma textura so para todas as casas, pintada por pixels (numpy).

Layout em celulas alinhadas a 32 px (origem embaixo a esquerda, como Image.pixels).
Cada celula tem uma margem (GUTTER) pintada com o mesmo conteudo e o UV usa so o
miolo, entao a filtragem linear com mipmap (que no jogo e global, nao por textura)
nao mistura celulas vizinhas ate o mip 3 (1/8 do tamanho), quando a casa ja esta
longe e no LOD1.

Este modulo nao depende de bpy: paint() devolve um array (H, W, 4) float32.
"""

import numpy as np

W, H = 1024, 512
GUTTER = 4
VERSION = "casas-atlas-7"

# nome -> (x, y, w, h) em pixels
CELLS = {}
# tamanho real (m) que o miolo da celula representa, para manter a escala
METERS = {}

WALLS = {
    # nome: cor do reboco (sRGB 0-1)
    "verde_agua": (0.55, 0.83, 0.74),
    "amarelo": (0.96, 0.82, 0.36),
    "rosa": (0.94, 0.62, 0.68),
    "azul": (0.50, 0.68, 0.88),
    "salmao": (0.96, 0.64, 0.50),
    "branco": (0.90, 0.88, 0.82),
    "creme": (0.94, 0.86, 0.66),
    "verde": (0.64, 0.80, 0.44),
    "cinza": (0.64, 0.63, 0.60),  # reboco cru (massa sem pintura)
}
REBOCO = [k for k in WALLS if k != "cinza"]
BRICKS = ("tijolo", "baiano")
ALL_WALLS = list(WALLS) + list(BRICKS)

FLATS = {
    "caixa_azul": (0.16, 0.42, 0.78),
    "caixa_tampa": (0.11, 0.30, 0.62),
    "concreto": (0.60, 0.60, 0.57),
    "branco": (0.93, 0.93, 0.91),
    "preto": (0.07, 0.07, 0.08),
    "metal": (0.70, 0.72, 0.74),
    "ferrugem": (0.42, 0.22, 0.13),
    "madeira": (0.47, 0.31, 0.19),
    "cumeeira": (0.62, 0.30, 0.18),
    "granito": (0.50, 0.48, 0.47),
    "meio_fio": (0.78, 0.77, 0.73),
    "laje_borda": (0.66, 0.65, 0.61),
    "forro": (0.88, 0.87, 0.84),
    "vidro": (0.20, 0.27, 0.33),
    "placa_lado": (0.25, 0.25, 0.27),
    "parabolica": (0.80, 0.81, 0.82),
    "grade": (0.12, 0.12, 0.13),
    "verde_escuro": (0.18, 0.32, 0.24),
    "terra": (0.42, 0.33, 0.24),
    "cinza_escuro": (0.30, 0.30, 0.31),
}

SIGNS = {
    # placa: (texto, fundo, letra, borda)
    "bar": ("BAR DO ZE", (0.98, 0.80, 0.10), (0.75, 0.08, 0.06), (0.75, 0.08, 0.06)),
    "padaria": ("PADARIA", (0.96, 0.93, 0.84), (0.50, 0.25, 0.10), (0.85, 0.55, 0.15)),
    "mercadinho": ("MERCADINHO", (0.80, 0.10, 0.08), (1.0, 1.0, 0.95), (0.98, 0.80, 0.10)),
    "oficina": ("OFICINA", (0.10, 0.28, 0.62), (1.0, 1.0, 1.0), (0.95, 0.95, 0.95)),
}
AWNINGS = ("toldo_verde", "toldo_vermelho", "toldo_azul")


def _cell(name, x, y, w, h, meters=None):
    CELLS[name] = (x, y, w, h)
    if meters:
        METERS[name] = meters


def _layout():
    CELLS.clear()
    METERS.clear()
    # linha A (y 0-128): paredes
    for i, k in enumerate(WALLS):
        _cell("w_" + k, 64 * i, 0, 64, 128, (3.0, 3.0))
    _cell("w_tijolo", 576, 0, 128, 128, (4.0, 3.0))
    _cell("w_baiano", 704, 0, 128, 128, (4.0, 3.0))
    _cell("muro_pichado", 832, 0, 128, 128, (5.0, 3.0))
    _cell("fundacao", 960, 0, 64, 128, (3.0, 3.0))
    # linha B (y 128-256): telhados e portas largas
    _cell("telha", 0, 128, 256, 128, (8.0, 4.0))
    _cell("fibro", 256, 128, 256, 128, (8.0, 4.0))
    _cell("portao_garagem", 512, 128, 128, 128)
    _cell("porta_enrolar", 640, 128, 128, 128)
    _cell("loja", 768, 128, 128, 128)
    _cell("calcada", 896, 128, 128, 128, (4.0, 4.0))
    # linha C (y 256-384): janelas, placas, portas, toldos
    for i, k in enumerate(("jan_grade_preta", "jan_grade_branca", "jan_basculante", "jan_madeira",
                           "jan_correr", "jan_vao", "ac_frente", "beiral")):
        _cell(k, 64 * i, 256, 64, 64)
    METERS["beiral"] = (2.0, 1.0)
    for i, k in enumerate(SIGNS):
        _cell("placa_" + k, 256 * (i % 2), 320 + 32 * (i // 2), 256, 32)
    for i, k in enumerate(("porta_madeira", "porta_ferro", "portao_social", "porta_sacada", "escada")):
        _cell(k, 512 + 64 * i, 256, 64, 128)
    for i, k in enumerate(AWNINGS):
        _cell(k, 832 + 64 * i, 256, 64, 64)
    _cell("roupas", 832, 320, 64, 64)
    _cell("laje", 896, 320, 64, 64, (6.0, 6.0))
    _cell("antena_prato", 960, 320, 64, 64)
    # linha D (y 384-512): fachadas do LOD1 e cores chapadas
    for i, k in enumerate(ALL_WALLS):
        _cell("f1_%s_t" % k, 64 * i, 384, 64, 32)
        _cell("f1_%s_a" % k, 64 * i, 416, 64, 32)
    for i, k in enumerate(SIGNS):
        _cell("f1_loja_" + k, 64 * i, 448, 64, 32)
    _cell("f1_muro", 256, 448, 64, 32)
    _cell("f1_muro_pichado", 320, 448, 64, 32)
    slots = [(704 + 32 * c, 384 + 32 * r) for r in range(4) for c in range(10)]
    for (k, (x, y)) in zip(FLATS, slots):
        _cell(k, x, y, 32, 32)


_layout()


def uv_rect(name, sub=(0.0, 0.0, 1.0, 1.0)):
    """Retangulo UV (u0, v0, u1, v1) do miolo da celula; sub = fracao do miolo."""
    x, y, w, h = CELLS[name]
    g = GUTTER
    u0, u1 = (x + g) / W, (x + w - g) / W
    v0, v1 = (y + g) / H, (y + h - g) / H
    return (u0 + (u1 - u0) * sub[0], v0 + (v1 - v0) * sub[1],
            u0 + (u1 - u0) * sub[2], v0 + (v1 - v0) * sub[3])


# --------------------------------------------------------------------------- pintura

def _rs(k):
    return np.random.RandomState(k)


def _noise(rs, h, w, scale):
    """Ruido suave (value noise) em [0, 1]."""
    gh, gw = int(h / scale) + 3, int(w / scale) + 3
    g = rs.rand(gh, gw)
    y = np.arange(h) / float(scale)
    x = np.arange(w) / float(scale)
    y0 = np.floor(y).astype(int)
    x0 = np.floor(x).astype(int)
    fy = (y - y0)[:, None]
    fx = (x - x0)[None, :]
    fy = fy * fy * (3 - 2 * fy)
    fx = fx * fx * (3 - 2 * fx)
    a = g[y0][:, x0]
    b = g[y0][:, x0 + 1]
    c = g[y0 + 1][:, x0]
    d = g[y0 + 1][:, x0 + 1]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def _canvas(h, w, col):
    c = np.empty((h, w, 3), np.float32)
    c[:] = col
    return c


def _mix(c, col, t):
    t = np.clip(t, 0.0, 1.0)[..., None]
    return c * (1 - t) + np.asarray(col, np.float32) * t


def _rect(c, x0, y0, x1, y1, col):
    """Retangulo em coordenadas locais (y para cima), fim exclusivo."""
    h, w = c.shape[:2]
    x0, x1 = max(0, int(x0)), min(w, int(x1))
    y0, y1 = max(0, int(y0)), min(h, int(y1))
    if x1 > x0 and y1 > y0:
        c[y0:y1, x0:x1] = col


def _shade(c, x0, y0, x1, y1, f):
    h, w = c.shape[:2]
    x0, x1 = max(0, int(x0)), min(w, int(x1))
    y0, y1 = max(0, int(y0)), min(h, int(y1))
    if x1 > x0 and y1 > y0:
        c[y0:y1, x0:x1] *= f


def _grain(c, rs, amp):
    h, w = c.shape[:2]
    c *= (1.0 + amp * (rs.rand(h, w) - 0.5))[..., None]
    return c


def _resample(src, w, h):
    """Reduz por media (super-amostragem 4x4)."""
    sh, sw = src.shape[:2]
    out = np.zeros((h, w, 3), np.float32)
    for sy in range(4):
        py = np.clip(((np.arange(h) + (sy + 0.5) / 4) * sh / h).astype(int), 0, sh - 1)
        for sx in range(4):
            px = np.clip(((np.arange(w) + (sx + 0.5) / 4) * sw / w).astype(int), 0, sw - 1)
            out += src[py][:, px]
    return out / 16.0


def _stroke(c, pts, col, r=1.0):
    """Linha grossa por uma polilinha (pichacao, fios)."""
    h, w = c.shape[:2]
    for (xa, ya), (xb, yb) in zip(pts[:-1], pts[1:]):
        n = int(max(abs(xb - xa), abs(yb - ya)) * 2) + 2
        for t in np.linspace(0, 1, n):
            x = xa + (xb - xa) * t
            y = ya + (yb - ya) * t
            x0, x1 = int(x - r + 0.5), int(x + r + 0.5)
            y0, y1 = int(y - r + 0.5), int(y + r + 0.5)
            _rect(c, x0, y0, max(x1, x0 + 1), max(y1, y0 + 1), col)


# fonte 5x7 (linhas de cima para baixo)
_FONT = {
    "A": (" ### ", "#   #", "#   #", "#####", "#   #", "#   #", "#   #"),
    "B": ("#### ", "#   #", "#   #", "#### ", "#   #", "#   #", "#### "),
    "C": (" ####", "#    ", "#    ", "#    ", "#    ", "#    ", " ####"),
    "D": ("#### ", "#   #", "#   #", "#   #", "#   #", "#   #", "#### "),
    "E": ("#####", "#    ", "#    ", "#### ", "#    ", "#    ", "#####"),
    "F": ("#####", "#    ", "#    ", "#### ", "#    ", "#    ", "#    "),
    "G": (" ####", "#    ", "#    ", "#  ##", "#   #", "#   #", " ####"),
    "H": ("#   #", "#   #", "#   #", "#####", "#   #", "#   #", "#   #"),
    "I": ("#####", "  #  ", "  #  ", "  #  ", "  #  ", "  #  ", "#####"),
    "L": ("#    ", "#    ", "#    ", "#    ", "#    ", "#    ", "#####"),
    "M": ("#   #", "## ##", "# # #", "# # #", "#   #", "#   #", "#   #"),
    "N": ("#   #", "##  #", "# # #", "#  ##", "#   #", "#   #", "#   #"),
    "O": (" ### ", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "),
    "P": ("#### ", "#   #", "#   #", "#### ", "#    ", "#    ", "#    "),
    "R": ("#### ", "#   #", "#   #", "#### ", "# #  ", "#  # ", "#   #"),
    "S": (" ####", "#    ", "#    ", " ### ", "    #", "    #", "#### "),
    "T": ("#####", "  #  ", "  #  ", "  #  ", "  #  ", "  #  ", "  #  "),
    "U": ("#   #", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "),
    "Z": ("#####", "    #", "   # ", "  #  ", " #   ", "#    ", "#####"),
    " ": ("     ",) * 7,
}


def _text(c, s, cx, cy, scale, col):
    adv = 6 * scale
    tw = len(s) * adv - scale
    x0 = int(cx - tw / 2)
    y_top = int(cy + 7 * scale / 2)
    for i, ch in enumerate(s):
        g = _FONT.get(ch, _FONT[" "])
        for r, row in enumerate(g):
            for k, bit in enumerate(row):
                if bit == "#":
                    x = x0 + i * adv + k * scale
                    y = y_top - (r + 1) * scale
                    _rect(c, x, y, x + scale, y + scale, col)


# ----------------------------------------------------------------------- celulas

def _wall_reboco(col, seed, dirt=1.0, w=64, h=128):
    rs = _rs(seed)
    c = _canvas(h, w, col)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    n = _noise(rs, h, w, 12)
    c *= (0.95 + 0.08 * n)[..., None]
    _grain(c, rs, 0.05)
    # mancha de umidade na base (borda irregular), ~0.6 m
    edge = 18 + 7 * _noise(rs, 1, w, 9)[0] + 3 * np.sin(xx[0] * 0.45)
    t = np.clip((edge[None, :] - yy) / 9.0, 0, 1) * dirt
    dark = np.asarray(col, np.float32) * 0.55 + np.asarray((0.30, 0.26, 0.20), np.float32) * 0.25
    c = _mix(c, dark, t * 0.75)
    # respingo de chao
    c = _mix(c, (0.35, 0.30, 0.24), np.clip((7 - yy) / 7.0, 0, 1) * 0.5 * dirt)
    # escorrido fraco descendo de pontos (encardido)
    streak = (rs.rand(w) > 0.82).astype(np.float32) * rs.rand(w)
    s = _noise(rs, 1, w, 3)[0] * streak
    c = _mix(c, dark, s[None, :] * np.clip((yy - 30) / 90.0, 0, 1) * 0.18 * dirt)
    return c


def _wall_tijolo(seed, w=128, h=128):
    rs = _rs(seed)
    mortar = np.asarray((0.74, 0.70, 0.62), np.float32)
    c = _canvas(h, w, mortar)
    rows = h // 4
    tones = np.asarray(((0.64, 0.30, 0.19), (0.72, 0.37, 0.23), (0.58, 0.27, 0.17), (0.69, 0.33, 0.20)),
                       np.float32)
    for r in range(rows):
        off = 4 if r % 2 else 0
        for b in range(-1, w // 8 + 1):
            x0 = b * 8 + off
            col = tones[rs.randint(len(tones))] * (0.9 + 0.2 * rs.rand())
            _rect(c, x0 + 1, r * 4 + 1, x0 + 8, r * 4 + 4, col)
    n = _noise(rs, h, w, 20)
    c *= (0.92 + 0.12 * n)[..., None]
    _grain(c, rs, 0.06)
    return c


def _wall_baiano(seed, w=128, h=128):
    rs = _rs(seed)
    mortar = np.asarray((0.58, 0.56, 0.52), np.float32)
    c = _canvas(h, w, mortar)
    _grain(c, rs, 0.15)
    for r in range(h // 8 + 1):
        off = 5 if r % 2 else 0
        for b in range(-1, w // 10 + 2):
            x0 = b * 10 + off + rs.randint(-1, 2)
            y0 = r * 8 + rs.randint(0, 2)
            col = np.asarray((0.86, 0.46, 0.25), np.float32) * (0.85 + 0.25 * rs.rand())
            _rect(c, x0 + 2, y0 + 2, x0 + 10, y0 + 8, col)
            # ranhuras horizontais do bloco
            _shade(c, x0 + 2, y0 + 4, x0 + 10, y0 + 5, 0.88)
            _shade(c, x0 + 2, y0 + 6, x0 + 10, y0 + 7, 0.88)
    # argamassa escorrida
    blobs = _noise(rs, h, w, 4)
    c = _mix(c, mortar * 1.05, np.clip((blobs - 0.72) * 4, 0, 1))
    # pilares de concreto nas bordas e viga em cima (aparecem a cada trecho de parede)
    conc = np.asarray((0.60, 0.59, 0.56), np.float32)
    for x0, x1 in ((0, 13), (w - 13, w)):
        _rect(c, x0, 0, x1, h, conc)
    _rect(c, 0, h - 13, w, h, conc)
    n = _noise(rs, h, w, 5)
    pil = np.zeros((h, w), np.float32)
    pil[:, :13] = 1
    pil[:, w - 13:] = 1
    pil[h - 13:, :] = 1
    c *= (1 - pil * 0.12 * n)[..., None]
    _shade(c, 12, 0, 14, h - 12, 0.75)
    _shade(c, w - 14, 0, w - 12, h - 12, 0.75)
    _shade(c, 12, h - 14, w - 12, h - 12, 0.7)
    return c


def _muro_pichado(seed, w=128, h=128):
    rs = _rs(seed)
    c = _wall_reboco((0.80, 0.79, 0.75), seed + 1, 1.3, w, h)
    tags = [(0.10, 0.10, 0.11), (0.10, 0.10, 0.11), (0.18, 0.18, 0.35)]
    for k in range(3):
        x = 6 + rs.rand() * (w - 40)
        y = 30 + rs.rand() * 50
        col = tags[rs.randint(len(tags))]
        pts = [(x, y)]
        for _ in range(rs.randint(5, 10)):
            x += rs.uniform(2, 7)
            y = 30 + rs.rand() * 50 if rs.rand() < 0.3 else y + rs.uniform(-14, 14)
            y = min(max(y, 34), 80)
            pts.append((x, y))
        _stroke(c, pts, col, 0.8)
    return c


def _fundacao(seed, w=64, h=128):
    rs = _rs(seed)
    c = _canvas(h, w, (0.52, 0.51, 0.48))
    c *= (0.85 + 0.25 * _noise(rs, h, w, 3))[..., None]
    _grain(c, rs, 0.25)
    return c


def _telha(seed, w=256, h=128):
    rs = _rs(seed)
    xx = np.arange(w, dtype=np.float32)
    yy = np.arange(h, dtype=np.float32)
    c = _canvas(h, w, (0.80, 0.42, 0.24))
    period, row = 8, 13
    tone = rs.rand(h // row + 2, w // period + 2)
    ti = (yy // row).astype(int)[:, None]
    tj = (xx // period).astype(int)[None, :]
    var = tone[ti, tj]
    pal = np.asarray(((0.80, 0.40, 0.22), (0.72, 0.34, 0.19), (0.86, 0.50, 0.30), (0.66, 0.32, 0.20)),
                     np.float32)
    c = pal[(var * 3.999).astype(int)]
    prof = 0.82 + 0.28 * np.sin(xx / period * 2 * np.pi)[None, :] ** 1
    lip = 0.9 + 0.18 * ((yy % row) / row)[:, None]
    c *= (prof * lip)[..., None]
    _shade(c, 0, 0, w, h, 1.0)
    for r in range(0, h, row):
        _shade(c, 0, r, w, r + 1, 0.55)
    # limo/escurecido, mais forte embaixo (beiral)
    n = _noise(rs, h, w, 14)
    low = np.clip(1.0 - yy / h, 0, 1)[:, None]
    c = _mix(c, (0.30, 0.26, 0.20), np.clip(n - 0.55, 0, 1) * 1.1 * (0.4 + 0.6 * low))
    _grain(c, rs, 0.08)
    return c


def _fibro(seed, w=256, h=128):
    rs = _rs(seed)
    xx = np.arange(w, dtype=np.float32)
    yy = np.arange(h, dtype=np.float32)
    c = _canvas(h, w, (0.69, 0.69, 0.66))
    prof = 0.86 + 0.2 * np.sin(xx / 6.0 * 2 * np.pi)
    c *= prof[None, :, None]
    for r in range(0, h, 58):
        _shade(c, 0, r, w, r + 2, 0.7)
    for k in range(0, w, 35):
        _shade(c, k, 0, k + 1, h, 0.85)
    n = _noise(rs, h, w, 10)
    c = _mix(c, (0.25, 0.25, 0.23), np.clip(n - 0.55, 0, 1) * 1.4)
    streak = _noise(rs, 1, w, 2)[0]
    c = _mix(c, (0.35, 0.34, 0.31), (np.clip(streak - 0.6, 0, 1) * 1.2)[None, :] * np.ones((h, 1)))
    _grain(c, rs, 0.07)
    return c


def _laje(seed, w=64, h=64):
    rs = _rs(seed)
    c = _canvas(h, w, (0.62, 0.61, 0.58))
    c *= (0.85 + 0.25 * _noise(rs, h, w, 8))[..., None]
    c = _mix(c, (0.35, 0.34, 0.31), np.clip(_noise(rs, h, w, 6) - 0.65, 0, 1) * 1.5)
    _grain(c, rs, 0.1)
    return c


def _calcada(seed, w=128, h=128):
    rs = _rs(seed)
    c = _canvas(h, w, (0.70, 0.69, 0.66))
    c *= (0.9 + 0.15 * _noise(rs, h, w, 10))[..., None]
    _grain(c, rs, 0.08)
    for k in range(0, w, 32):
        _shade(c, k, 0, k + 1, h, 0.6)
    for k in range(0, h, 32):
        _shade(c, 0, k, w, k + 1, 0.6)
    c = _mix(c, (0.40, 0.38, 0.34), np.clip(_noise(rs, h, w, 7) - 0.7, 0, 1) * 1.6)
    return c


def _portao_garagem(seed, w=128, h=128):
    rs = _rs(seed)
    col = np.asarray((0.32, 0.34, 0.37), np.float32)
    c = _canvas(h, w, col)
    xx = np.arange(w)
    rib = np.where(xx % 6 < 1, 1.25, np.where(xx % 6 == 1, 0.8, 1.0)).astype(np.float32)
    c *= rib[None, :, None]
    # faixa de ventilacao em cima
    _rect(c, 4, h - 34, w - 4, h - 8, col * 0.9)
    for y in range(h - 32, h - 10, 4):
        _rect(c, 8, y, w - 8, y + 2, (0.08, 0.08, 0.09))
    # moldura
    for (x0, y0, x1, y1) in ((0, 0, w, 5), (0, h - 6, w, h), (0, 0, 5, h), (w - 5, 0, w, h), (w // 2 - 1, 0, w // 2 + 2, h)):
        _rect(c, x0, y0, x1, y1, col * 0.6)
    _rect(c, w // 2 + 6, 52, w // 2 + 10, 64, (0.75, 0.75, 0.72))
    # ferrugem embaixo
    yy = np.arange(h, dtype=np.float32)
    c = _mix(c, (0.40, 0.22, 0.12), np.clip(_noise(rs, h, w, 5) - 0.5, 0, 1) * np.clip((24 - yy) / 24, 0, 1)[:, None] * 1.6)
    _grain(c, rs, 0.06)
    return c


def _porta_enrolar(seed, w=128, h=128):
    rs = _rs(seed)
    col = np.asarray((0.72, 0.73, 0.74), np.float32)
    c = _canvas(h, w, col)
    yy = np.arange(h)
    slat = np.where(yy % 4 == 0, 0.62, np.where(yy % 4 == 3, 1.1, 1.0)).astype(np.float32)
    c *= slat[:, None, None]
    _rect(c, 0, 0, w, 8, (0.30, 0.30, 0.31))
    _rect(c, 22, 2, 30, 8, (0.15, 0.15, 0.15))
    _rect(c, w - 30, 2, w - 22, 8, (0.15, 0.15, 0.15))
    _rect(c, 0, h - 14, w, h, (0.45, 0.46, 0.47))
    _rect(c, 0, 0, 4, h, (0.42, 0.42, 0.43))
    _rect(c, w - 4, 0, w, h, (0.42, 0.42, 0.43))
    c = _mix(c, (0.35, 0.34, 0.30), np.clip(_noise(rs, h, w, 9) - 0.55, 0, 1) * 1.0)
    # pichacao discreta
    pts = [(30, 60), (40, 75), (46, 58), (55, 72), (63, 60), (72, 74), (80, 62)]
    _stroke(c, pts, (0.1, 0.1, 0.12), 0.7)
    _grain(c, rs, 0.05)
    return c


def _loja(seed, w=128, h=128):
    rs = _rs(seed)
    c = _canvas(h, w, (0.26, 0.23, 0.20))
    yy = np.arange(h, dtype=np.float32)
    c *= (0.7 + 0.6 * (yy / h))[:, None, None]
    # luz fluorescente
    _rect(c, 20, h - 22, w - 20, h - 19, (1.0, 1.0, 0.95))
    # prateleiras com produtos coloridos
    cols = [(0.9, 0.2, 0.15), (0.95, 0.85, 0.2), (0.2, 0.5, 0.9), (0.95, 0.95, 0.9), (0.2, 0.7, 0.3),
            (0.9, 0.5, 0.1), (0.6, 0.2, 0.6)]
    for sy in (44, 64, 84):
        _rect(c, 6, sy - 2, w - 6, sy, (0.55, 0.45, 0.32))
        x = 8
        while x < w - 10:
            pw = rs.randint(3, 7)
            ph = rs.randint(5, 14)
            _rect(c, x, sy, x + pw, sy + ph, np.asarray(cols[rs.randint(len(cols))]) * (0.7 + 0.3 * rs.rand()))
            x += pw + rs.randint(0, 2)
    # balcao
    _rect(c, 10, 0, w - 10, 30, (0.82, 0.80, 0.74))
    _rect(c, 10, 26, w - 10, 30, (0.45, 0.35, 0.25))
    _rect(c, 14, 4, w - 14, 22, (0.55, 0.62, 0.65))
    for x in range(20, w - 14, 10):
        _rect(c, x, 6, x + 6, 12, cols[rs.randint(len(cols))])
    # porta de enrolar recolhida e laterais
    _rect(c, 0, h - 14, w, h, (0.55, 0.56, 0.57))
    for y in range(h - 14, h, 3):
        _rect(c, 0, y, w, y + 1, (0.40, 0.40, 0.41))
    _rect(c, 0, 0, 4, h, (0.42, 0.42, 0.43))
    _rect(c, w - 4, 0, w, h, (0.42, 0.42, 0.43))
    return c


def _glass(h, w, seed, base=(0.22, 0.29, 0.35)):
    rs = _rs(seed)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    c = _canvas(h, w, base)
    refl = np.clip(((xx + yy) / (w + h) - 0.35) * 2.0, 0, 1)
    c = _mix(c, (0.62, 0.72, 0.80), refl * 0.55)
    band = ((xx - yy * 0.8) % 40 < 6).astype(np.float32)
    c = _mix(c, (0.85, 0.9, 0.95), band * 0.18)
    return c


def _window(kind, seed, w=64, h=64):
    rs = _rs(seed)
    frame = (0.92, 0.92, 0.90)
    c = _canvas(h, w, frame)
    if kind == "vao":
        c = _canvas(h, w, (0.08, 0.07, 0.07))
        yy = np.arange(h, dtype=np.float32)
        c *= (0.8 + 0.6 * (yy / h))[:, None, None]
        _rect(c, 0, h - 8, w, h, (0.58, 0.57, 0.54))  # verga de concreto
        _rect(c, 0, 0, w, 4, (0.55, 0.53, 0.50))
        n = _noise(rs, h, w, 3)
        edge = np.zeros((h, w), np.float32)
        edge[:, :4] = 1
        edge[:, w - 4:] = 1
        c = _mix(c, (0.58, 0.56, 0.52), edge * (n > 0.4))
        return c
    if kind == "ac":
        c = _canvas(h, w, (0.90, 0.90, 0.88))
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        r = np.hypot(xx - 24, yy - 30)
        c = _mix(c, (0.25, 0.26, 0.27), (r < 18).astype(np.float32))
        ang = np.arctan2(yy - 30, xx - 24)
        c = _mix(c, (0.75, 0.75, 0.74), ((r < 18) & ((np.abs(np.sin(ang * 3)) < 0.25) | (r % 5 < 1))).astype(np.float32))
        for y in range(8, h - 8, 4):
            _rect(c, 48, y, w - 6, y + 2, (0.70, 0.70, 0.68))
        _shade(c, 0, 0, w, 3, 0.7)
        return c
    if kind == "beiral":
        c = _canvas(h, w, (0.52, 0.36, 0.24))
        for x in range(0, w, 16):
            _rect(c, x, 0, x + 5, h, (0.36, 0.24, 0.15))
        _grain(c, rs, 0.1)
        return c
    # moldura (requadro) e peitoril
    _rect(c, 0, 0, w, 6, (0.58, 0.56, 0.54))
    _shade(c, 0, 5, w, 6, 0.6)
    gx0, gy0, gx1, gy1 = 5, 9, w - 5, h - 5
    if kind == "madeira":
        wood = np.asarray((0.50, 0.32, 0.18), np.float32)
        _rect(c, gx0, gy0, gx1, gy1, wood)
        for y in range(gy0, gy1, 3):
            _rect(c, gx0, y, gx1, y + 1, wood * 0.65)
        _rect(c, w // 2 - 1, gy0, w // 2 + 1, gy1, wood * 0.4)
        for x in (gx0, gx1 - 2):
            _rect(c, x, gy0, x + 2, gy1, wood * 0.75)
        _rect(c, gx0, gy1 - 2, gx1, gy1, wood * 0.75)
        _grain(c, rs, 0.08)
        return c
    g = _glass(gy1 - gy0, gx1 - gx0, seed)
    c[gy0:gy1, gx0:gx1] = g
    if kind == "basculante":
        al = (0.80, 0.81, 0.82)
        c[gy0:gy1, gx0:gx1] = _canvas(gy1 - gy0, gx1 - gx0, (0.72, 0.78, 0.76))
        xx = np.arange(gx1 - gx0)
        c[gy0:gy1, gx0:gx1] *= np.where(xx % 3 == 0, 0.86, 1.0)[None, :, None]
        n = 4
        ph = (gy1 - gy0) / n
        for k in range(n):
            y0 = gy0 + int(k * ph)
            c[y0:y0 + int(ph), gx0:gx1] *= np.linspace(0.8, 1.05, int(ph))[:, None, None]
            _rect(c, gx0, y0, gx1, y0 + 2, al)
        _rect(c, gx0, gy1 - 2, gx1, gy1, al)
        return c
    if kind == "correr":
        al = (0.82, 0.83, 0.84)
        _rect(c, w // 2 - 2, gy0, w // 2 + 2, gy1, al)
        _rect(c, gx0, gy0, gx1, gy0 + 2, al)
        _rect(c, gx0, gy1 - 2, gx1, gy1, al)
        # cortina de um lado
        _rect(c, w // 2 + 2, gy0 + 2, gx1 - 6, gy1 - 2, (0.85, 0.80, 0.62))
        for x in range(w // 2 + 4, gx1 - 6, 4):
            _rect(c, x, gy0 + 2, x + 1, gy1 - 2, (0.70, 0.64, 0.48))
        return c
    # janela de correr com grade (preta ou branca)
    al = (0.80, 0.81, 0.82)
    _rect(c, w // 2 - 1, gy0, w // 2 + 2, gy1, al)
    if rs.rand() < 2:  # cortina
        _rect(c, gx0 + 2, gy0 + 2, w // 2 - 4, gy1 - 3, (0.80, 0.55, 0.50) if kind.endswith("branca") else (0.72, 0.72, 0.60))
    bar = (0.08, 0.08, 0.09) if kind.endswith("preta") else (0.95, 0.95, 0.94)
    for x in range(gx0 + 4, gx1, 7):
        _rect(c, x, gy0, x + 2, gy1, bar)
    for y in (gy0 + 1, gy0 + (gy1 - gy0) // 2, gy1 - 3):
        _rect(c, gx0, y, gx1, y + 2, bar)
    # arco decorativo da grade
    for x in range(gx0, gx1):
        t = (x - gx0) / float(gx1 - gx0)
        y = int(gy1 - 4 - 10 * (4 * t * (1 - t)))
        _rect(c, x, y, x + 1, y + 2, bar)
    return c


def _door(kind, seed, w=64, h=128):
    rs = _rs(seed)
    c = _canvas(h, w, (0.92, 0.92, 0.90))
    x0, x1, y0, y1 = 4, w - 4, 2, h - 4
    _rect(c, 0, 0, w, 2, (0.50, 0.48, 0.46))
    if kind == "madeira":
        wood = np.asarray((0.52, 0.33, 0.19), np.float32)
        _rect(c, x0, y0, x1, y1, wood)
        c[y0:y1, x0:x1] *= (0.9 + 0.2 * _noise(rs, y1 - y0, x1 - x0, 2.0)[..., None] ** 2)
        for (a, b, cc, d) in ((10, 12, w - 10, 56), (10, 66, w - 10, h - 14)):
            _shade(c, a, b, cc, d, 0.82)
            _shade(c, a, d - 2, cc, d, 0.7)
        _rect(c, w - 14, 60, w - 9, 64, (0.80, 0.75, 0.50))
        return c
    if kind == "ferro":
        col = np.asarray((0.20, 0.33, 0.26), np.float32)
        _rect(c, x0, y0, x1, y1, col)
        g = _glass(52, x1 - x0 - 12, seed)
        c[y1 - 58:y1 - 6, x0 + 6:x1 - 6] = g
        for x in range(x0 + 9, x1 - 6, 6):
            _rect(c, x, y1 - 58, x + 2, y1 - 6, col * 0.6)
        for y in range(y0 + 6, y1 - 64, 5):
            _rect(c, x0 + 4, y, x1 - 4, y + 1, col * 0.7)
        _rect(c, w - 14, 60, w - 10, 66, (0.8, 0.8, 0.78))
        return c
    if kind == "social":
        dark = (0.12, 0.12, 0.13)
        yy = np.arange(h, dtype=np.float32)
        bg = _canvas(h, w, (0.44, 0.46, 0.40))
        bg *= (0.75 + 0.35 * (yy / h))[:, None, None]
        c[:] = bg
        _rect(c, 0, 0, w, 38, (0.25, 0.27, 0.30))
        for y in range(4, 36, 5):
            _rect(c, 2, y, w - 2, y + 1, (0.18, 0.19, 0.21))
        for x in range(3, w, 6):
            _rect(c, x, 38, x + 2, h - 2, dark)
            _rect(c, x - 1, h - 6, x + 3, h - 3, dark)
        _rect(c, 0, 36, w, 40, dark)
        _rect(c, 0, h - 10, w, h - 8, dark)
        _rect(c, 0, 0, 3, h, dark)
        _rect(c, w - 3, 0, w, h, dark)
        return c
    if kind == "sacada":
        al = (0.82, 0.83, 0.84)
        _rect(c, x0, y0, x1, y1, al)
        g = _glass(y1 - y0 - 6, (x1 - x0) // 2 - 4, seed)
        c[y0 + 3:y1 - 3, x0 + 3:x0 + 3 + g.shape[1]] = g
        g2 = _glass(y1 - y0 - 6, (x1 - x0) // 2 - 4, seed + 1)
        c[y0 + 3:y1 - 3, w // 2 + 1:w // 2 + 1 + g2.shape[1]] = g2
        _rect(c, w // 2 + 3, y0 + 3, x1 - 4, y1 - 3, (0.88, 0.84, 0.70))
        for x in range(w // 2 + 5, x1 - 4, 4):
            _rect(c, x, y0 + 3, x + 1, y1 - 3, (0.72, 0.66, 0.52))
        return c
    if kind == "escada":
        c = _canvas(h, w, (0.62, 0.61, 0.58))
        for y in range(0, h, 11):
            _rect(c, 0, y, w, y + 4, (0.44, 0.43, 0.41))
            _rect(c, 0, y + 10, w, y + 11, (0.75, 0.74, 0.71))
        _grain(c, rs, 0.12)
        return c
    return c


def _awning(cols, seed, w=64, h=64):
    rs = _rs(seed)
    c = _canvas(h, w, cols[0])
    xx = np.arange(w)
    stripe = ((xx // 8) % 2).astype(np.float32)
    c = _mix(c, cols[1], stripe[None, :] * np.ones((h, 1)))
    yy = np.arange(h, dtype=np.float32)
    c *= (0.85 + 0.2 * (yy / h))[:, None, None]
    # barrado (sanefa) nos 16 px de baixo, com borda escura
    _shade(c, 0, 0, w, 16, 0.92)
    _rect(c, 0, 15, w, 17, np.asarray(cols[0]) * 0.6)
    _grain(c, rs, 0.05)
    return c


def _roupas(seed, w=64, h=64):
    rs = _rs(seed)
    c = _canvas(h, w, (0.55, 0.62, 0.68))
    cols = [(0.9, 0.2, 0.2), (0.95, 0.95, 0.92), (0.2, 0.35, 0.8), (0.95, 0.8, 0.2), (0.3, 0.7, 0.4),
            (0.95, 0.5, 0.7), (0.2, 0.2, 0.25), (0.6, 0.75, 0.9)]
    x = 0
    while x < w:
        pw = rs.randint(6, 14)
        top = h - 4
        ln = rs.randint(int(h * 0.45), h - 6)
        _rect(c, x, top - ln, x + pw - 1, top, cols[rs.randint(len(cols))])
        x += pw
    _rect(c, 0, h - 4, w, h - 3, (0.2, 0.2, 0.2))
    return c


def _sign(text, bg, fg, border, w=256, h=32):
    c = _canvas(h, w, bg)
    _rect(c, 0, 0, w, 3, border)
    _rect(c, 0, h - 3, w, h, border)
    scale = 3 if len(text) * 18 < w - 16 else 2
    _text(c, text, w / 2, h / 2, scale, fg)
    return c


def _antena(seed, w=64, h=64):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.hypot(xx - w / 2, yy - h / 2) / (w / 2)
    c = _canvas(h, w, (0.82, 0.83, 0.84))
    c *= (0.75 + 0.3 * r)[..., None]
    return c


def _lod1_facade(wall_cell, items, w=64, h=32):
    """Fachada distante: parede reduzida + aberturas coladas."""
    c = _resample(wall_cell[16:, :], w, h)
    for (src, x0, y0, x1, y1) in items:
        c[y0:y1, x0:x1] = _resample(src, x1 - x0, y1 - y0)
    return c


_CACHE = {}


def paint():
    """Pinta o atlas inteiro. Retorna np.float32 (H, W, 4), linha 0 = embaixo."""
    if "img" in _CACHE:
        return _CACHE["img"]
    img = np.zeros((H, W, 3), np.float32)

    def put(name, c):
        x, y, w, h = CELLS[name]
        img[y:y + h, x:x + w] = c[:h, :w]

    walls = {}
    for i, (k, col) in enumerate(WALLS.items()):
        dirt = 1.4 if k in ("branco", "creme") else 1.0
        walls[k] = _wall_reboco(col, 10 + i, dirt)
        put("w_" + k, walls[k])
    walls["tijolo"] = _wall_tijolo(31)
    walls["baiano"] = _wall_baiano(32)
    put("w_tijolo", walls["tijolo"])
    put("w_baiano", walls["baiano"])
    put("muro_pichado", _muro_pichado(33))
    put("fundacao", _fundacao(34))
    put("telha", _telha(40))
    put("fibro", _fibro(41))
    pg = _portao_garagem(42)
    put("portao_garagem", pg)
    pe = _porta_enrolar(43)
    put("porta_enrolar", pe)
    loja = _loja(44)
    put("loja", loja)
    put("calcada", _calcada(45))
    wins = {}
    for i, k in enumerate(("grade_preta", "grade_branca", "basculante", "madeira", "correr", "vao", "ac", "beiral")):
        wins[k] = _window(k, 50 + i)
    for k, name in (("grade_preta", "jan_grade_preta"), ("grade_branca", "jan_grade_branca"),
                    ("basculante", "jan_basculante"), ("madeira", "jan_madeira"), ("correr", "jan_correr"),
                    ("vao", "jan_vao"), ("ac", "ac_frente"), ("beiral", "beiral")):
        put(name, wins[k])
    signs = {}
    for k, (txt, bg, fg, bd) in SIGNS.items():
        signs[k] = _sign(txt, bg, fg, bd)
        put("placa_" + k, signs[k])
    doors = {}
    for i, k in enumerate(("madeira", "ferro", "social", "sacada", "escada")):
        doors[k] = _door(k, 60 + i)
    for k, name in (("madeira", "porta_madeira"), ("ferro", "porta_ferro"), ("social", "portao_social"),
                    ("sacada", "porta_sacada"), ("escada", "escada")):
        put(name, doors[k])
    for name, cols in zip(AWNINGS, (((0.15, 0.55, 0.30), (0.95, 0.95, 0.92)),
                                    ((0.80, 0.12, 0.10), (0.95, 0.95, 0.92)),
                                    ((0.15, 0.35, 0.75), (0.98, 0.85, 0.20)))):
        put(name, _awning(cols, 70))
    put("roupas", _roupas(71))
    put("laje", _laje(72))
    put("antena_prato", _antena(73))
    for k, col in FLATS.items():
        x, y, w, h = CELLS[k]
        c = _canvas(h, w, col)
        c *= np.linspace(0.86, 1.0, h, dtype=np.float32)[:, None, None]
        put(k, c)

    # fachadas do LOD1 (64x32 = um andar de ~7 x 3 m)
    for k in ALL_WALLS:
        jan = wins["madeira"] if k == "tijolo" else wins["vao"] if k == "baiano" else wins["grade_preta"]
        porta = doors["madeira"] if k in ("tijolo", "creme", "branco") else doors["ferro"]
        put("f1_%s_t" % k, _lod1_facade(walls[k], [(jan, 6, 11, 18, 24), (porta, 27, 3, 37, 24),
                                                   (jan, 46, 11, 58, 24)]))
        put("f1_%s_a" % k, _lod1_facade(walls[k], [(jan, 6, 10, 18, 24), (jan, 26, 10, 38, 24),
                                                   (jan, 46, 10, 58, 24)]))
    for k in SIGNS:
        c = _resample(walls["branco"][16:, :], 64, 32)
        c[3:21, 4:60] = _resample(loja, 56, 18)
        c[22:30, 2:62] = _resample(signs[k], 60, 8)
        put("f1_loja_" + k, c)
    for name, base in (("f1_muro", walls["cinza"]), ("f1_muro_pichado", _muro_pichado(33))):
        c = _resample(base, 64, 32)
        c[2:24, 6:30] = _resample(pg, 24, 22)
        c[2:24, 40:50] = _resample(doors["social"], 10, 22)
        put(name, c)

    out = np.ones((H, W, 4), np.float32)
    out[..., :3] = np.clip(img, 0.0, 1.0)
    _CACHE["img"] = out
    return out
