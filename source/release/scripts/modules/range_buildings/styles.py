# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
# ##### END GPL LICENSE BLOCK #####

"""Estilos de casa brasileira (bairro/periferia/interior).

Convencao: origem no chao, no centro da frente do lote; frente para -Y; o lote vai de
x = -W/2 a W/2 e de y = 0 (alinhamento da calcada) a y = D. Cada estilo sorteia tudo
no comeco (sem depender do LOD) e depois monta com as pecas de house.py.
"""

from . import atlas
from .geom import Wall
from .house import House

WIN = (1.2, 1.2, 1.0)        # largura, altura, peitoril
DOOR = (0.9, 2.1, 0.0)
BASC = (0.6, 0.6, 1.55)


def _front(H, rect, side, z, items, margin=0.5):
    """items: [(w, h, sill, cell)] distribuidos ao longo da parede."""
    wall = Wall(rect, side)
    placed = H.spread(wall.len, [it for it in items], margin)
    for a, (w, h, sill, cell) in placed:
        H.opening(rect, side, a, z + sill, w, h, cell)
    return placed


def _win(cell):
    return (WIN[0], WIN[1], WIN[2], cell)


def _door(cell):
    return (DOOR[0], DOOR[1], DOOR[2], cell)


def _basc():
    return (BASC[0], BASC[1], BASC[2], "jan_basculante")


def _lod1(kind, floors, ground=None):
    return [ground or ("f1_%s_t" % kind)] + ["f1_%s_a" % kind] * (floors - 1)


def _side_gaps(R, W):
    """Corredor lateral: so de um lado, dos dois ou geminada (sem recuo lateral)."""
    r = R.random()
    g = R.uniform(1.1, 1.5)
    g2 = R.uniform(0.6, 1.0)
    if W < 6.0:
        return (0.0, 0.0) if r < 0.6 else ((g, 0.0) if r < 0.8 else (0.0, g))
    if r < 0.35:
        return (g, 0.0)
    if r < 0.65:
        return (0.0, g)
    if r < 0.8:
        return (g, g2)
    return (0.0, 0.0)


def _roof_telha(H, R_hip, rect, zt, slope, over, kind, gaps):
    """Telhado colonial: 4 aguas se houver folga dos dois lados; senao 2 aguas sem beiral
    do lado colado no vizinho."""
    gl, gr = gaps
    if R_hip and gl >= over and gr >= over:
        return H.roof_hip(rect, zt, slope, over, "telha")
    return H.roof_gable(rect, zt, slope, over, "telha", kind, ol=min(over, gl), orr=min(over, gr))


def _side_windows(H, rect, F, fh, gaps, rnd_pick, back_door=True, skip_side=None):
    """Janelas nas laterais com corredor e nos fundos."""
    for s, g in (("L", gaps[0]), ("R", gaps[1])):
        if g < 0.5 or s == skip_side:
            continue
        for i in range(F):
            items = [_basc(), _win(rnd_pick)] if i == 0 else [_win(rnd_pick), _basc()]
            _front(H, rect, s, i * fh, items, 1.0)
    for i in range(F):
        items = [_win(rnd_pick), _door("porta_ferro")] if (i == 0 and back_door) else [_win(rnd_pick), _basc()]
        _front(H, rect, "B", i * fh, items, 0.8)


def _muro(H, W, y, h, kind, door_x, garage_x=None, garage_w=2.8, gate_h=None, t=0.15):
    gh = gate_h or h - 0.04
    gates = [(door_x + W / 2, 1.0, min(gh, 2.1), "portao_social")]
    if garage_x is not None:
        gates.append((garage_x + W / 2, garage_w, min(gh, 2.3), "portao_garagem"))
    H.wall_low(-W / 2, W / 2, y, h, t, kind, gates)


# =========================================================================== estilos

def terrea_colonial(R, H, W, D, F, brick=False):
    w_ = R.uniform(6.5, 9.5)
    W = W or w_
    f_ = 1 if not brick else (1 if R.random() < 0.6 else 2)
    F = F or f_
    fh = R.uniform(2.75, 2.95)
    has_muro = R.random() < (0.6 if not brick else 0.5)
    recuo = R.uniform(3.0, 4.5) if has_muro else 0.0
    bd = R.uniform(7.5, 10.0)
    gaps = _side_gaps(R, W)
    kind = "tijolo" if brick else R.choice(atlas.REBOCO)
    win = R.choice(["jan_madeira", "jan_grade_preta", "jan_grade_branca", "jan_grade_preta"])
    if brick:
        win = R.choice(["jan_madeira", "jan_madeira", "jan_grade_preta"])
    door = R.choice(["porta_madeira", "porta_madeira", "porta_ferro"])
    hip = R.random() < 0.55
    slope = R.uniform(0.40, 0.48)
    over = R.uniform(0.5, 0.7)
    porch = has_muro and R.random() < 0.45
    porch_d = R.uniform(1.8, 2.2)
    muro_kind = R.choice([kind, "cinza", "branco", R.choice(atlas.REBOCO)]) if not brick else "tijolo"
    muro_h = R.uniform(1.3, 1.8)
    garage = R.random() < 0.6
    ac = R.random() < 0.3
    door_first = R.random() < 0.5
    antena = R.random() < 0.3
    yaw = R.uniform(-2.5, -0.6)

    if D:
        recuo = min(recuo, max(0.0, D - 5.0))
        bd = max(4.0, D - recuo)
    D = recuo + bd
    x0, x1 = -W / 2 + gaps[0], W / 2 - gaps[1]
    rect = (x0, x1, recuo, recuo + bd)
    bw = x1 - x0
    H.body(rect, F, fh, kind, lod1_front=_lod1(kind, F))
    zt = F * fh
    _roof_telha(H, hip, rect, zt, slope, over, kind, gaps)
    # frente
    if bw >= 6.6:
        items = [_win(win), _door(door), _win(win)]
    else:
        items = [_door(door), _win(win)] if door_first else [_win(win), _door(door)]
    placed = _front(H, rect, "F", 0.0, items, 0.6)
    door_a = next((a for a, it in placed if it[3] == door), bw / 2)
    for i in range(1, F):
        _front(H, rect, "F", i * fh, [_win(win), _win(win)] if bw > 5 else [_win(win)], 0.8)
    _side_windows(H, rect, F, fh, gaps, win)
    if porch:
        H.porch(x0 + 0.2, x1 - 0.2, recuo, porch_d, zt - 0.12, 0.30, "telha")
    if has_muro:
        dx = x0 + door_a
        gx = None
        if garage and W >= 7.0:
            gx = (-W / 2 + 1.7) if dx > 0 else (W / 2 - 1.7)
            if abs(gx - dx) < 2.0:
                gx = None
        _muro(H, W, 0.0, muro_h, muro_kind, dx, gx)
        H.wall_side(-W / 2, 0.15, recuo + (bd if gaps[0] > 0.5 else 0.0), muro_h, 0.15, muro_kind)
    if ac:
        s = "L" if gaps[0] >= 0.6 else ("R" if gaps[1] >= 0.6 else "F")
        if s != "F":
            H.ac(rect, s, bd * 0.6, 1.9)
    if antena and F >= 1:
        H.antenna(x0 + bw * 0.25, recuo + bd * 0.7, zt + 0.2, yaw)
    return W, D


def terrea_laje(R, H, W, D, F):
    w_ = R.uniform(5.5, 8.5)
    W = W or w_
    F = F or 1
    fh = R.uniform(2.75, 2.9)
    has_muro = R.random() < 0.7
    recuo = R.uniform(3.0, 5.0) if has_muro else 0.0
    bd = R.uniform(7.0, 10.0)
    gaps = _side_gaps(R, W)
    kind = R.choice(atlas.REBOCO)
    win = R.choice(["jan_grade_preta", "jan_grade_branca", "jan_grade_preta", "jan_correr"])
    door = R.choice(["porta_ferro", "porta_madeira"])
    over = R.uniform(0.2, 0.35)
    plat = R.random() < 0.35
    tank_base = R.random() < 0.5
    tank_x = R.uniform(0.2, 0.8)
    varal = R.random() < 0.5
    antena = R.random() < 0.45
    yaw = R.uniform(-2.5, -0.6)
    ac = R.random() < 0.4
    muro_kind = R.choice([kind, "cinza", "branco", R.choice(atlas.REBOCO), "muro_pichado"])
    muro_h = R.uniform(1.4, 1.9)
    garage = R.random() < 0.65
    carport = R.random() < 0.5
    door_first = R.random() < 0.5

    if D:
        recuo = min(recuo, max(0.0, D - 5.0))
        bd = max(4.0, D - recuo)
    D = recuo + bd
    x0, x1 = -W / 2 + gaps[0], W / 2 - gaps[1]
    rect = (x0, x1, recuo, recuo + bd)
    bw = x1 - x0
    H.body(rect, F, fh, kind, lod1_front=_lod1(kind, F))
    zt = F * fh
    ov = (min(over, gaps[0]), min(over, gaps[1]), over, over)
    zl = H.slab(rect, zt, 0.15, ov, "laje_borda")
    outer = (x0 - ov[0], x1 + ov[1], recuo - over, recuo + bd + over)
    if plat:
        H.parapet(outer, zl, 0.7, 0.12, kind, "F")
    # frente
    items = [_win(win), _door(door), _win(win)] if bw >= 6.6 else (
        [_door(door), _win(win)] if door_first else [_win(win), _door(door)])
    placed = _front(H, rect, "F", 0.0, items, 0.6)
    door_a = next((a for a, it in placed if it[3] == door), bw / 2)
    for i in range(1, F):
        _front(H, rect, "F", i * fh, [_win(win), _win(win)], 0.8)
    _side_windows(H, rect, F, fh, gaps, win)
    # laje: caixa d'agua, varal, antena
    tx = x0 + 0.9 + (bw - 1.8) * tank_x
    ty = recuo + bd * 0.72
    z = zl
    if tank_base:
        z = H.tank_base(tx, ty, zl, 1.6, 0.6, kind)
    H.water_tank(tx, ty, z)
    if varal and bw > 4.5:
        vx = x0 + 0.6 if tx > (x0 + x1) / 2 else x1 - 3.4
        H.clothesline((vx, recuo + bd * 0.35), (vx + 2.8, recuo + bd * 0.35), zl)
    if antena:
        H.antenna(x1 - 0.8 if tx < (x0 + x1) / 2 else x0 + 0.8, recuo + 1.2, zl, yaw)
    if ac:
        H.ac(rect, "F", door_a + (1.6 if door_a < bw / 2 else -1.6), 2.15)
    if has_muro:
        dx = x0 + door_a
        gx = None
        if garage and W >= 6.5:
            gx = (-W / 2 + 1.7) if dx > 0 else (W / 2 - 1.7)
            if abs(gx - dx) < 2.0:
                gx = None
        _muro(H, W, 0.0, muro_h, muro_kind, dx, gx)
        H.wall_side(-W / 2, 0.15, recuo, muro_h, 0.15, muro_kind if muro_kind != "muro_pichado" else "cinza")
        if gx is not None and carport and recuo >= 3.0:
            cx0 = max(-W / 2 + 0.2, gx - 1.6)
            cx1 = min(W / 2 - 0.2, gx + 1.6)
            H.carport(cx0, cx1, 0.6, recuo, zt - 0.25)
    return W, D


def sobrado_sacada(R, H, W, D, F):
    w_ = R.uniform(6.0, 9.0)
    W = W or w_
    F = F or 2
    fh = R.uniform(2.8, 2.95)
    has_muro = R.random() < 0.55
    recuo = R.uniform(3.0, 4.5) if has_muro else 0.0
    bd = R.uniform(8.0, 10.5)
    stairs = R.random() < 0.45
    gaps = _side_gaps(R, W)
    if stairs:
        side = "L" if R.random() < 0.5 else "R"
        gaps = (max(gaps[0], 1.2), gaps[1]) if side == "L" else (gaps[0], max(gaps[1], 1.2))
    else:
        side = None
    kind = R.choice(atlas.REBOCO)
    kind_up = kind if R.random() < 0.7 else R.choice(atlas.REBOCO)
    win = R.choice(["jan_grade_preta", "jan_grade_branca", "jan_correr", "jan_grade_preta"])
    door = R.choice(["porta_madeira", "porta_ferro"])
    roof_laje = R.random() < 0.45
    hip = R.random() < 0.6
    slope = R.uniform(0.40, 0.46)
    over = R.uniform(0.5, 0.7)
    garage_in = R.random() < 0.45
    bal_full = R.random() < 0.4
    tank_x = R.uniform(0.25, 0.75)
    ac = R.random() < 0.5
    antena = R.random() < 0.4
    yaw = R.uniform(-2.5, -0.6)
    muro_kind = R.choice([kind, "cinza", "branco", "muro_pichado"])
    muro_h = R.uniform(1.4, 1.9)

    if D:
        recuo = min(recuo, max(0.0, D - 7.0))
        bd = max(7.0, D - recuo)
    D = recuo + bd
    x0, x1 = -W / 2 + gaps[0], W / 2 - gaps[1]
    rect = (x0, x1, recuo, recuo + bd)
    bw = x1 - x0
    kinds = [kind] + [kind_up] * (F - 1)
    H.body(rect, F, fh, kind, lod1_front=[("f1_%s_t" % kind)] + ["f1_%s_a" % kind_up] * (F - 1), kinds=kinds)
    zt = F * fh
    if roof_laje:
        ov = (min(0.25, gaps[0]), min(0.25, gaps[1]), 0.25, 0.25)
        zl = H.slab(rect, zt, 0.15, ov, "laje_borda")
        outer = (x0 - ov[0], x1 + ov[1], recuo - 0.25, recuo + bd + 0.25)
        H.parapet(outer, zl, 0.8, 0.12, kind_up, "FBLR")
        H.water_tank(x0 + 1.0 + (bw - 2.0) * tank_x, recuo + bd * 0.7, zl)
        if antena:
            H.antenna(x0 + 0.8, recuo + 1.0, zl, yaw)
    else:
        _roof_telha(H, hip, rect, zt, slope, over, kind_up, gaps)
    # terreo
    if garage_in and bw >= 6.0:
        items = [(2.6, 2.3, 0.0, "portao_garagem"), _door(door), _win(win)]
    else:
        items = [_win(win), _door(door), _win(win)] if bw >= 6.6 else [_door(door), _win(win)]
    placed = _front(H, rect, "F", 0.0, items, 0.5)
    door_a = next((a for a, it in placed if it[3] == door), bw / 2)
    # andares de cima: sacada com porta de vidro + janela
    for i in range(1, F):
        z = i * fh
        if bal_full and bw > 5.0:
            a0, a1 = 0.4, bw - 0.4
            H.balcony(rect, "F", a0, a1, z, 1.0, kind_up)
            _front(H, rect, "F", z, [(1.6, 2.15, 0.0, "porta_sacada"), _win(win)], 0.8)
        else:
            pl = _front(H, rect, "F", z, [(1.6, 2.15, 0.0, "porta_sacada"), _win(win)], 0.8)
            a = pl[0][0]
            H.balcony(rect, "F", a - 1.1, a + 1.1, z, 0.9, kind_up)
    _side_windows(H, rect, F, fh, gaps, win, skip_side=side)
    if stairs:
        wall = Wall(rect, side)
        run = fh / 0.62
        if side == "R":
            a_lo, a_hi = 0.5, 0.5 + run
        else:
            a_lo, a_hi = wall.len - 0.5, wall.len - 0.5 - run
        H.stairs(rect, side, a_lo, a_hi, fh, 1.0, kind)
        land = 1.0 if a_hi > a_lo else -1.0
        H.opening(rect, side, a_hi + land * 0.5, fh, 0.85, 2.1, "porta_ferro")
        # janela no terreo embaixo do patamar nao; uma basculante perto dos fundos
        H.opening(rect, side, a_hi + land * 2.0 if 0 < a_hi + land * 2.0 < wall.len else wall.len / 2,
                  1.55, 0.6, 0.6, "jan_basculante")
    if ac:
        H.ac(rect, "F", min(bw - 0.6, door_a + 1.4), fh + 2.2)
    if has_muro:
        dx = x0 + door_a
        _muro(H, W, 0.0, muro_h, muro_kind, dx, None)
    return W, D


def sobrado_comercio(R, H, W, D, F):
    w_ = R.uniform(6.5, 10.0)
    W = W or w_
    F = F or 2
    fh = R.uniform(2.9, 3.1)
    bd = R.uniform(9.0, 12.0)
    gaps = (0.0, 0.0) if R.random() < 0.7 else (0.0, R.uniform(1.0, 1.4))
    tipo = R.choice(list(atlas.SIGNS))
    kind_up = R.choice(atlas.REBOCO)
    kind = R.choice([kind_up, "branco", "amarelo", "cinza"]) if tipo != "bar" else R.choice(["amarelo", kind_up])
    win = R.choice(["jan_grade_preta", "jan_basculante", "jan_grade_branca", "jan_correr"])
    two = R.random() < 0.6
    awning = R.random() < 0.75
    awn = {"bar": "toldo_vermelho", "padaria": "toldo_verde", "mercadinho": "toldo_azul",
           "oficina": "toldo_azul"}[tipo] if R.random() < 0.6 else R.choice(atlas.AWNINGS)
    roof_laje = R.random() < 0.75
    slope = R.uniform(0.40, 0.46)
    over = R.uniform(0.4, 0.6)
    tank_x = R.uniform(0.2, 0.8)
    ac = R.random() < 0.6
    bal = R.random() < 0.35
    antena = R.random() < 0.5
    yaw = R.uniform(-2.5, -0.6)

    if D:
        bd = max(6.0, D)
    D = bd
    x0, x1 = -W / 2 + gaps[0], W / 2 - gaps[1]
    rect = (x0, x1, 0.0, bd)
    bw = x1 - x0
    kinds = [kind] + [kind_up] * (F - 1)
    H.body(rect, F, fh, kind, lod1_front=["f1_loja_" + tipo] + ["f1_%s_a" % kind_up] * (F - 1), kinds=kinds)
    zt = F * fh
    if roof_laje:
        zl = H.slab(rect, zt, 0.15, 0.0, "laje_borda")
        outer = rect
        H.parapet(outer, zl, 0.9, 0.12, kind_up, "FBLR")
        H.water_tank(x0 + 1.0 + (bw - 2.0) * tank_x, bd * 0.7, zl)
        if antena:
            H.antenna(x0 + 0.8, 1.2, zl, yaw)
    else:
        H.parapet((x0, x1, -0.0, bd), zt, 1.2, 0.15, kind_up, "F")
        H.roof_shed((x0, x1, 0.15, bd), zt, 0.12, 0.0, "fibro", kind_up, front_high=True)
    # loja no terreo
    door_w = 0.9
    shop_h = 2.6
    if two and bw >= 7.5:
        sw = (bw - door_w - 1.4) / 2
        items = [(sw, shop_h, 0.0, "loja"), (sw, shop_h, 0.0, "porta_enrolar" if R.random() < 2 else "loja"),
                 (door_w, 2.1, 0.0, "porta_ferro")]
    else:
        sw = min(3.6, bw - door_w - 1.2)
        items = [(sw, shop_h, 0.0, "loja"), (door_w, 2.1, 0.0, "porta_ferro")]
    placed = _front(H, rect, "F", 0.0, items, 0.3)
    shops = [(a, it) for a, it in placed if it[3] in ("loja", "porta_enrolar")]
    if shops:
        a0 = min(a - it[0] / 2 for a, it in shops) - 0.15
        a1 = max(a + it[0] / 2 for a, it in shops) + 0.15
        if awning:
            H.awning(rect, "F", a0, a1, shop_h + 0.35, 1.2, 0.45, awn)
        H.sign(rect, "F", a0 + 0.1, a1 - 0.1, shop_h + 0.5 if awning else shop_h + 0.15,
               shop_h + 1.05 if awning else shop_h + 0.75, "placa_" + tipo)
    for i in range(1, F):
        z = i * fh
        pl = _front(H, rect, "F", z, [_win(win), _win(win)] if not bal else [(1.6, 2.15, 0.0, "porta_sacada"), _win(win)], 0.8)
        if bal:
            a = pl[0][0]
            H.balcony(rect, "F", a - 1.1, a + 1.1, z, 0.8, kind_up)
        if ac and i == 1:
            H.ac(rect, "F", pl[-1][0] + 1.2 if pl[-1][0] + 1.6 < bw else pl[-1][0] - 1.4, z + 2.15)
    _side_windows(H, rect, F, fh, gaps, "jan_basculante")
    return W, D


def puxadinho(R, H, W, D, F):
    w_ = R.uniform(5.5, 8.0)
    W = W or w_
    F = F or 2
    fh = R.uniform(2.6, 2.8)
    bd = R.uniform(7.0, 9.5)
    gaps = _side_gaps(R, W)
    r = R.random()
    kind = R.choice(atlas.REBOCO) if r < 0.6 else ("cinza" if r < 0.85 else "baiano")
    win = R.choice(["jan_grade_preta", "jan_basculante", "jan_grade_branca"])
    door = R.choice(["porta_ferro", "porta_ferro", "porta_madeira"])
    frac = R.uniform(0.5, 0.75)
    shed = R.random() < 0.55
    over = 0.25
    stairs = R.random() < 0.6
    varal = R.random() < 0.6
    garage = R.random() < 0.4
    installed = R.random() < 0.4
    tank_x = R.uniform(0.25, 0.75)
    ang = R.uniform(0, 6.28)
    door_first = R.random() < 0.5

    if D:
        bd = max(5.0, D)
    D = bd
    x0, x1 = -W / 2 + gaps[0], W / 2 - gaps[1]
    rect = (x0, x1, 0.0, bd)
    bw = x1 - x0
    # terreo(s) acabados
    fin = F - 1
    H.body(rect, fin, fh, kind, lod1_front=_lod1(kind, fin))
    zt = fin * fh
    if garage and bw >= 6.0:
        items = [(2.6, 2.3, 0.0, "portao_garagem"), _door(door), _basc()]
    else:
        items = [_door(door), _win(win)] if door_first else [_win(win), _door(door)]
        if bw > 6.5:
            items.append(_basc())
    _front(H, rect, "F", 0.0, items, 0.5)
    for i in range(1, fin):
        _front(H, rect, "F", i * fh, [_win(win), _win(win)], 0.8)
    _side_windows(H, rect, fin, fh, gaps, win)
    # laje com o andar inacabado na frente
    ov = (min(over, gaps[0]), min(over, gaps[1]), over, over)
    up = (x0, x1, 0.0, bd * frac)
    zl = H.slab(rect, zt, 0.15, ov, "laje_borda", hole=up)
    H.body(up, 1, fh, "baiano", z0=zl, lod1_front=["f1_baiano_a"])
    pl = _front(H, up, "F", zl, [(1.1, 1.1, 1.0, "jan_basculante" if installed else "jan_vao"),
                                 (1.1, 1.1, 1.0, "jan_vao")], 0.9)
    H.opening(up, "B", (x1 - x0) * 0.3, zl, 0.8, 2.1, "jan_vao")
    zt2 = zl + fh
    if shed:
        H.roof_shed((x0, x1, 0.0, bd * frac), zt2, 0.10, 0.2, "fibro", "baiano", front_high=True)
        zr = zt2 + bd * frac * 0.10
    else:
        zr = H.slab(up, zt2, 0.12, 0.0, "laje_borda")
    for k, (px, py) in enumerate(((x0 + 0.13, 0.13), (x1 - 0.13, 0.13), (x0 + 0.13, bd * frac - 0.13),
                                  (x1 - 0.13, bd * frac - 0.13))):
        if shed:
            H.rebar(px, py, zt2 + (bd * frac - py) * 0.10 + 0.02 - 0.2, ang + k, 3)
        else:
            H.rebar(px, py, zr, ang + k, 3)
    # laje aberta atras: caixa d'agua e varal
    ty = bd * frac + (bd * (1 - frac)) * 0.55
    tx = x0 + 0.9 + (bw - 1.8) * tank_x
    H.water_tank(tx, ty, zl)
    if varal and bw > 4.5:
        vx = x0 + 0.5 if tx > (x0 + x1) / 2 else x1 - 3.3
        vy = bd * frac + 0.9
        if vy < bd - 0.3:
            H.clothesline((vx, vy), (vx + 2.8, vy), zl)
    if stairs:
        side = "L" if gaps[0] >= 1.0 else ("R" if gaps[1] >= 1.0 else None)
        if side:
            wall = Wall(rect, side)
            run = zl / 0.65
            if side == "R":
                a_lo = max(0.3, wall.len - 0.4 - run - 1.0)
                a_hi = a_lo + run
            else:
                a_lo = min(wall.len - 0.3, 0.4 + run + 1.0)
                a_hi = a_lo - run
            H.stairs(rect, side, a_lo, a_hi, zl, 0.9, "cinza", rail=False)
    return W, D


def tijolo_aparente(R, H, W, D, F):
    return terrea_colonial(R, H, W, D, F, brick=True)


def predinho(R, H, W, D, F):
    w_ = R.uniform(8.0, 10.0)
    W = W or w_
    f_ = R.choice([3, 3, 4])
    F = F or f_
    fh = R.uniform(2.8, 2.9)
    bd = R.uniform(10.0, 13.0)
    kind = R.choice(atlas.REBOCO)
    two_tone = R.random() < 0.45
    kind0 = R.choice(["cinza", "branco", R.choice(atlas.REBOCO)]) if two_tone else kind
    win = R.choice(["jan_correr", "jan_grade_branca", "jan_correr", "jan_grade_preta"])
    ground_shop = R.random() < 0.5
    tipo = R.choice(list(atlas.SIGNS))
    bal_floor = [R.random() < 0.35 for _ in range(8)]
    acs = [(R.random() < 0.45, R.random() < 0.3) for _ in range(8)]
    side_win = R.random() < 0.6
    antena = R.random() < 0.6
    yaw = R.uniform(-2.5, -0.6)
    awning = R.random() < 0.6

    if D:
        bd = max(8.0, D)
    D = bd
    x0, x1 = -W / 2, W / 2
    rect = (x0, x1, 0.0, bd)
    bw = x1 - x0
    kinds = [kind0] + [kind] * (F - 1)
    ground_cell = ("f1_loja_" + tipo) if ground_shop else "f1_%s_t" % kind0
    H.body(rect, F, fh, kind, lod1_front=[ground_cell] + ["f1_%s_a" % kind] * (F - 1), kinds=kinds)
    zt = F * fh
    # terreo
    if ground_shop:
        items = [(3.4, 2.6, 0.0, "loja"), (1.0, 2.2, 0.0, "portao_social"), (1.2, 1.2, 1.0, win)]
    else:
        items = [(2.6, 2.3, 0.0, "portao_garagem"), (1.0, 2.2, 0.0, "portao_social"), _win(win)]
    placed = _front(H, rect, "F", 0.0, items, 0.4)
    if ground_shop:
        a, it = placed[0]
        if awning:
            H.awning(rect, "F", a - it[0] / 2 - 0.1, a + it[0] / 2 + 0.1, 2.95, 1.1, 0.4, "toldo_vermelho")
        H.sign(rect, "F", a - it[0] / 2, a + it[0] / 2, 3.05 if awning else 2.7, 3.5 if awning else 3.2,
               "placa_" + tipo)
    for i in range(1, F):
        z = i * fh
        if bal_floor[i]:
            items = [_win(win), (1.5, 2.15, 0.0, "porta_sacada"), _win(win)]
        else:
            items = [_win(win), _win(win), _win(win)]
        pl = _front(H, rect, "F", z, items, 0.5)
        if bal_floor[i] and len(pl) > 1:
            a = pl[1][0]
            H.balcony(rect, "F", a - 1.0, a + 1.0, z, 0.8, kind)
        for k, (has, _) in enumerate(acs[i:i + 1]):
            if has and len(pl) > 1:
                a = (pl[0][0] + pl[1][0]) / 2
                H.ac(rect, "F", a, z + 2.1)
        if side_win:
            _front(H, rect, "R", z, [_basc(), _win(win)], 2.0)
        _front(H, rect, "B", z, [_win(win), _basc()], 1.0)
    # cobertura: laje, platibanda, caixas d'agua sobre a casa de bombas
    zl = H.slab(rect, zt, 0.18, 0.0, "laje_borda")
    H.parapet(rect, zl, 0.9, 0.12, kind, "FBLR")
    bx, by = x0 + bw * 0.62, bd * 0.62
    zb = H.tank_base(bx, by, zl, 2.6, 1.2, kind)
    H.water_tank(bx - 0.62, by, zb)
    H.water_tank(bx + 0.62, by, zb)
    if antena:
        H.antenna(x0 + 1.2, 1.4, zl, yaw)
    return W, D


def muro_alto(R, H, W, D, F):
    w_ = R.uniform(7.0, 10.0)
    W = W or w_
    f_ = 1 if R.random() < 0.55 else 2
    F = F or f_
    fh = R.uniform(2.8, 2.95)
    recuo = R.uniform(3.5, 5.0)
    bd = R.uniform(8.0, 10.0)
    gaps = _side_gaps(R, W)
    kind = R.choice(atlas.REBOCO)
    r = R.random()
    muro_kind = R.choice(atlas.REBOCO) if r < 0.45 else ("cinza" if r < 0.65 else "muro_pichado")
    muro_h = R.uniform(2.4, 2.8)
    win = R.choice(["jan_grade_preta", "jan_grade_branca", "jan_correr"])
    door = R.choice(["porta_madeira", "porta_ferro"])
    roof_laje = R.random() < 0.4
    hip = R.random() < 0.6
    slope = R.uniform(0.40, 0.46)
    over = R.uniform(0.5, 0.7)
    tank_x = R.uniform(0.25, 0.75)
    garage_left = R.random() < 0.5
    antena = R.random() < 0.35
    yaw = R.uniform(-2.5, -0.6)

    if D:
        recuo = min(recuo, max(2.0, D - 6.0))
        bd = max(5.0, D - recuo)
    D = recuo + bd
    x0, x1 = -W / 2 + gaps[0], W / 2 - gaps[1]
    rect = (x0, x1, recuo, recuo + bd)
    bw = x1 - x0
    H.body(rect, F, fh, kind, lod1_front=_lod1(kind, F))
    zt = F * fh
    if roof_laje:
        ov = (min(0.25, gaps[0]), min(0.25, gaps[1]), 0.25, 0.25)
        zl = H.slab(rect, zt, 0.15, ov, "laje_borda")
        H.water_tank(x0 + 1.0 + (bw - 2.0) * tank_x, recuo + bd * 0.65, zl)
        if antena:
            H.antenna(x0 + 0.8, recuo + 1.0, zl, yaw)
    else:
        _roof_telha(H, hip, rect, zt, slope, over, kind, gaps)
    placed = _front(H, rect, "F", 0.0, [_win(win), _door(door), _win(win)] if bw > 6.6 else [_door(door), _win(win)], 0.6)
    for i in range(1, F):
        _front(H, rect, "F", i * fh, [_win(win), _win(win)], 0.8)
    _side_windows(H, rect, F, fh, gaps, win)
    gx = (-W / 2 + 1.8) if garage_left else (W / 2 - 1.8)
    dx = (W / 2 - 1.0) if garage_left else (-W / 2 + 1.0)
    _muro(H, W, 0.0, muro_h, muro_kind, dx, gx, 3.0, gate_h=min(muro_h - 0.1, 2.35), t=0.18)
    side_kind = muro_kind if muro_kind != "muro_pichado" else "cinza"
    H.wall_side(-W / 2, 0.18, recuo + (bd if gaps[0] > 0.5 else 0.0), muro_h, 0.15, side_kind)
    H.wall_side(W / 2 - 0.15, 0.18, recuo + (bd if gaps[1] > 0.5 else 0.0), muro_h, 0.15, side_kind)
    return W, D


STYLE_FUNCS = {
    "terrea_colonial": terrea_colonial,
    "terrea_laje": terrea_laje,
    "sobrado_sacada": sobrado_sacada,
    "sobrado_comercio": sobrado_comercio,
    "puxadinho": puxadinho,
    "tijolo_aparente": tijolo_aparente,
    "predinho": predinho,
    "muro_alto": muro_alto,
}

LABELS = {
    "terrea_colonial": ("Single-Storey, Clay Tile Roof", "Single-storey house with orange clay tile roof (2 or 4 slopes), "
                        "low front wall and gate"),
    "terrea_laje": ("Single-Storey, Flat Slab", "Flat concrete slab roof with blue water tank, clothesline, dish"),
    "sobrado_sacada": ("Two-Storey with Balcony", "Two-storey house with balcony and railing, side stairs on some seeds"),
    "sobrado_comercio": ("Shop + Home (Two-Storey)", "Shop on the ground floor (bar, bakery, grocery, garage), "
                         "rolling steel door, awning and sign"),
    "puxadinho": ("Unfinished Extension (Puxadinho)", "Slab with an unfinished upper floor in bare clay block, "
                  "rebar out of the pillars"),
    "tijolo_aparente": ("Exposed Brick House", "Exposed red brick walls, wooden windows, clay tile roof"),
    "predinho": ("Small Apartment Block", "3-4 floors, balconies, AC units, water tanks on the roof"),
    "muro_alto": ("High Wall and Garage Gate", "House behind a high front wall with steel garage gate"),
}
