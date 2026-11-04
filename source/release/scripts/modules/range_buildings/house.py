# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
# ##### END GPL LICENSE BLOCK #####

"""Pecas de casa (paredes, telhados, laje, muro, caixa d'agua...) que ja sabem o LOD.

Regra: nenhuma peca sorteia nada aqui. Os sorteios ficam nos estilos, antes de montar,
para o LOD0 e o LOD1 da mesma seed terem exatamente as mesmas medidas.

LOD1 (longe): so a caixa do corpo com a fachada pintada (celulas f1_*), telhado
sem beiral por baixo, laje sem borda e caixa d'agua como caixa. Detalhes somem.
"""

import math

from . import atlas
from .geom import Built, Wall, wall_quad, wall_box, add, sub, mul, cross, dot, norm, length

CLEAN = 0.30   # fracao do miolo da celula de parede acima da mancha de umidade
OFF = 0.04     # afastamento de janelas/portas da parede (evita z-fight)


def wall_cell(kind):
    return "w_" + kind


class House:
    def __init__(self, lod=0, foundation=0.0):
        self.b = Built()
        self.lod = lod
        self.f = max(0.0, float(foundation))

    # ------------------------------------------------------------------ corpo
    def _wall_sub(self, kind, z0, z1, ground):
        mu, mv = atlas.METERS[wall_cell(kind)]
        h = (z1 - z0) / mv
        if kind in atlas.BRICKS:
            return (0.0, 0.0, 1.0, min(1.0, h))
        if ground:
            return (0.0, 0.0, 1.0, min(1.0, h))
        return (0.0, CLEAN, 1.0, min(1.0, CLEAN + h * (1 - CLEAN)))

    def wall_face(self, wall, a0, a1, z0, z1, kind, ground=True):
        """Trecho de parede; tijolo e baiano sao repartidos para manter a escala."""
        cell = wall_cell(kind)
        mu, mv = atlas.METERS[cell]
        L = a1 - a0
        if L <= 1e-4 or z1 - z0 <= 1e-4:
            return
        n = int(math.ceil(L / (mu * 1.05))) if (kind in atlas.BRICKS and self.lod == 0) else 1
        s = self._wall_sub(kind, z0, z1, ground)
        for k in range(n):
            wa = a0 + L * k / n
            wb = a0 + L * (k + 1) / n
            us = min(1.0, (wb - wa) / mu) if kind in atlas.BRICKS else 1.0
            wall_quad(self.b, wall, wa, wb, z0, z1, cell, 0.0, (0.0, s[1], us, s[3]))
        if ground and z0 <= 1e-6 and self.f > 0:
            wall_quad(self.b, wall, a0, a1, -self.f, 0.0, "fundacao", 0.0,
                      (0.0, 0.0, 1.0, min(1.0, self.f / 3.0)))

    def body(self, rect, floors, fh, kind, z0=0.0, sides="FBLR", lod1_front=None, kinds=None):
        """Caixa de paredes por andar (sem base e sem topo). kinds = material por andar."""
        kinds = kinds or [kind] * floors
        for s in sides:
            wall = Wall(rect, s)
            if self.lod == 1 and not (s == "F" and lod1_front):
                k = kinds[0]
                zb = z0 - (self.f if z0 <= 1e-6 else 0.0)
                cell = wall_cell(k)
                sub_ = (0.0, CLEAN, 1.0, 1.0) if k not in atlas.BRICKS else (0.0, 0.0, 1.0, 1.0)
                wall_quad(self.b, wall, 0.0, wall.len, zb, z0 + floors * fh, cell, 0.0, sub_)
                continue
            for i in range(floors):
                za = z0 + i * fh
                zb = za + fh
                if self.lod == 1:
                    lo = za - (self.f if (i == 0 and z0 <= 1e-6) else 0.0)
                    wall_quad(self.b, wall, 0.0, wall.len, lo, zb, lod1_front[i], 0.0)
                else:
                    self.wall_face(wall, 0.0, wall.len, za, zb, kinds[i], ground=(i == 0 and z0 <= 1e-6))

    def gable_tri(self, rect, side, zt, zr, kind):
        """Oitao (triangulo de parede acima do topo) na parede L ou R, cumeeira em X."""
        x0, x1, y0, y1 = rect
        ym = (y0 + y1) / 2
        cell = wall_cell(kind)
        s = (0.0, 0.0, 1.0, 1.0) if kind in atlas.BRICKS else (0.0, CLEAN, 1.0, 1.0)
        mu, mv = atlas.METERS[cell]
        if side == "L":
            pts = [(x0, y1, zt), (x0, y0, zt), (x0, ym, zr)]
            self.b.planar(pts, cell, (0, -1, 0), (0, 0, 1), (mu, mv * (s[3] - s[1])), s)
        else:
            pts = [(x1, y0, zt), (x1, y1, zt), (x1, ym, zr)]
            self.b.planar(pts, cell, (0, 1, 0), (0, 0, 1), (mu, mv * (s[3] - s[1])), s)

    # --------------------------------------------------------------- aberturas
    def opening(self, rect, side, a, z, w, h, cell, off=OFF):
        """Janela/porta como quad afastado da parede, centrado em a."""
        if self.lod:
            return
        wall = Wall(rect, side)
        wall_quad(self.b, wall, a - w / 2, a + w / 2, z, z + h, cell, off)

    def spread(self, length_, items, margin=0.5):
        """Distribui itens (w, ...) ao longo da parede. Devolve [(a_centro, item)]."""
        items = list(items)
        while items:
            tot = sum(it[0] for it in items)
            gap = (length_ - 2 * margin - tot) / (len(items) + 1)
            if gap >= 0.35 or len(items) == 1:
                break
            items.pop()
        out = []
        a = margin
        for it in items:
            a += max(gap, 0.1)
            out.append((a + it[0] / 2, it))
            a += it[0]
        return out

    def ac(self, rect, side, a, z):
        if self.lod:
            return
        wall = Wall(rect, side)
        wall_box(self.b, wall, a - 0.42, a + 0.42, z, z + 0.58, 0.32, "branco", "ac_frente")

    def sign(self, rect, side, a0, a1, z0, z1, cell):
        if self.lod:
            return
        wall = Wall(rect, side)
        wall_box(self.b, wall, a0, a1, z0, z1, 0.10, "placa_lado", cell)

    def awning(self, rect, side, a0, a1, z_top, depth, drop, cell):
        if self.lod:
            return
        b = self.b
        wall = Wall(rect, side)
        zl = z_top - drop
        U = wall.U(a1 - a0)
        V = add(wall.N(-depth), (0.0, 0.0, drop))
        main = (0.0, 0.30, 1.0, 1.0)
        b.quad(wall.at(a0, zl, depth), U, V, cell, main)
        b.quad(add(wall.at(a1, zl, depth), (0, 0, -0.02)), wall.U(-(a1 - a0)), V, cell, (1.0, 0.30, 0.0, 1.0))
        val = (0.0, 0.0, 1.0, 0.24)
        b.quad(wall.at(a0, zl - 0.28, depth), U, (0, 0, 0.28), cell, val)
        b.quad(wall.at(a1, zl - 0.28, depth - 0.015), wall.U(-(a1 - a0)), (0, 0, 0.28), cell, (1.0, 0.0, 0.0, 0.24))
        for a, sgn in ((a0, 1), (a1, -1)):
            A = wall.at(a, zl, 0.0)
            B = wall.at(a, zl, depth)
            C = wall.at(a, z_top, 0.0)
            e = wall.U(0.012 * sgn)
            A2, B2, C2 = add(A, e), add(B, e), add(C, e)
            if sgn > 0:
                b.tri(A, B, C, cell, sub_=main)
                b.tri(A2, C2, B2, cell, sub_=main)
            else:
                b.tri(A, C, B, cell, sub_=main)
                b.tri(A2, B2, C2, cell, sub_=main)

    def balcony(self, rect, side, a0, a1, zf, depth, kind):
        """Sacada: laje em balanco + guarda-corpo de alvenaria (1 m)."""
        if self.lod:
            return
        b = self.b
        wall = Wall(rect, side)
        wall_box(b, wall, a0, a1, zf - 0.14, zf, depth, "laje_borda", faces="FLRD")
        cell = wall_cell(kind)
        s = (0.0, CLEAN, 1.0, 0.62) if kind not in atlas.BRICKS else (0.0, 0.0, 1.0, 0.33)
        h, t = 1.0, 0.10
        up = (0.0, 0.0, h)
        top = (0.0, 0.0, 1.0, 1.0)
        # frente
        b.quad(wall.at(a0, zf - 0.14, depth), wall.U(a1 - a0), (0, 0, h + 0.14), cell, s)
        b.quad(wall.at(a1, zf, depth - t), wall.U(-(a1 - a0)), up, cell, s)
        b.quad(wall.at(a0, zf + h, depth), wall.U(a1 - a0), wall.N(-t), "laje_borda", top)
        # lados
        b.quad(wall.at(a0, zf - 0.14, 0.0), wall.N(depth), (0, 0, h + 0.14), cell, s)
        b.quad(wall.at(a0 + t, zf, depth - t), wall.N(-(depth - t)), up, cell, s)
        b.quad(wall.at(a0, zf + h, 0.0), wall.N(depth - t), wall.U(t), "laje_borda", top)
        b.quad(wall.at(a1, zf - 0.14, depth), wall.N(-depth), (0, 0, h + 0.14), cell, s)
        b.quad(wall.at(a1 - t, zf, 0.0), wall.N(depth - t), up, cell, s)
        b.quad(wall.at(a1 - t, zf + h, 0.0), wall.N(depth - t), wall.U(t), "laje_borda", top)
        # piso da sacada (entre os parapeitos)
        b.quad(wall.at(a0 + t, zf, depth - t), wall.U(a1 - a0 - 2 * t), wall.N(-(depth - t)), "laje")

    # -------------------------------------------------------------- telhados
    def roof_gable(self, rect, zt, slope, over, cell, kind, cap=True, ol=None, orr=None):
        """Duas aguas, cumeeira em X (paralela a rua). Inclui oitoes nas paredes L e R."""
        b = self.b
        x0, x1, y0, y1 = rect
        o = over
        ol = o if ol is None else ol
        orr = o if orr is None else orr
        X0, X1, Y0, Y1 = x0 - ol, x1 + orr, y0 - o, y1 + o
        ym = (y0 + y1) / 2
        zr = zt + (ym - y0) * slope
        ze = zt - o * slope
        mu, mv = atlas.METERS[cell]
        L = math.hypot(ym - Y0, zr - ze)
        s_ = (0.0, 0.0, min(1.0, (X1 - X0) / mu), min(1.0, L / mv))
        b.quad((X0, Y0, ze), (X1 - X0, 0, 0), (0, ym - Y0, zr - ze), cell, s_)
        b.quad((X1, Y1, ze), (X0 - X1, 0, 0), (0, ym - Y1, zr - ze), cell, s_)
        self.gable_tri(rect, "L", zt, zr, kind)
        self.gable_tri(rect, "R", zt, zr, kind)
        if self.lod:
            return zr
        under = "beiral"
        b.quad((X1, Y0, ze), (X0 - X1, 0, 0), (0, y0 - Y0, zt - ze), under)
        b.quad((X0, Y1, ze), (X1 - X0, 0, 0), (0, y1 - Y1, zt - ze), under)
        for (xa, xb) in ((X0, x0), (x1, X1)):
            b.quad((xb, y0, zt), (xa - xb, 0, 0), (0, ym - y0, zr - zt), under)
            b.quad((xa, y1, zt), (xb - xa, 0, 0), (0, ym - y1, zr - zt), under)
        ft = 0.16
        b.quad((X0, Y0, ze - ft), (X1 - X0, 0, 0), (0, 0, ft), "madeira")
        b.quad((X1, Y1, ze - ft), (X0 - X1, 0, 0), (0, 0, ft), "madeira")
        if ol > 0.01:
            b.quad((X0, ym, zr - ft), (0, Y0 - ym, ze - zr), (0, 0, ft), "madeira")
            b.quad((X0, Y1, ze - ft), (0, ym - Y1, zr - ze), (0, 0, ft), "madeira")
        if orr > 0.01:
            b.quad((X1, Y0, ze - ft), (0, ym - Y0, zr - ze), (0, 0, ft), "madeira")
            b.quad((X1, ym, zr - ft), (0, Y1 - ym, ze - zr), (0, 0, ft), "madeira")
        if cap:
            c = 0.16
            zl = zr - c * slope + 0.03
            zc = zr + 0.09
            capc = "cumeeira" if cell == "telha" else "concreto"
            b.quad((X0, ym - c, zl), (X1 - X0, 0, 0), (0, c, zc - zl), capc)
            b.quad((X1, ym + c, zl), (X0 - X1, 0, 0), (0, -c, zc - zl), capc)
        return zr

    def roof_hip(self, rect, zt, slope, over, cell, cap=True):
        """Quatro aguas. Cumeeira no eixo mais comprido."""
        x0, x1, y0, y1 = rect
        if (y1 - y0) > (x1 - x0):
            # monta girado 90 graus (cumeeira em Y) e gira de volta
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            hw, hd = (x1 - x0) / 2, (y1 - y0) / 2
            tmp = House(self.lod, 0.0)
            zr = tmp.roof_hip((-hd, hd, -hw, hw), zt, slope, over, cell, cap)
            # local (x, y) -> mundo: x_m = cx - y, y_m = cy + x (rotacao de +90 graus)
            off = len(self.b.verts)
            self.b.verts.extend((cx - v[1], cy + v[0], v[2]) for v in tmp.b.verts)
            self.b.faces.extend(tuple(k + off for k in f) for f in tmp.b.faces)
            self.b.uvs.extend(tmp.b.uvs)
            return zr
        b = self.b
        o = over
        X0, X1, Y0, Y1 = x0 - o, x1 + o, y0 - o, y1 + o
        ym = (y0 + y1) / 2
        run = (Y1 - Y0) / 2
        ze = zt - o * slope
        zr = ze + run * slope
        xa, xb = X0 + run, X1 - run
        if xb - xa < 0.05:
            xa = xb = (X0 + X1) / 2
        mu, mv = atlas.METERS[cell]
        sv = norm((0, run, zr - ze))
        sv_b = norm((0, -run, zr - ze))
        sl = norm((run, 0, zr - ze))
        sr = norm((-run, 0, zr - ze))
        if xb > xa:
            b.planar([(X0, Y0, ze), (X1, Y0, ze), (xb, ym, zr), (xa, ym, zr)], cell, (1, 0, 0), sv, (mu, mv))
            b.planar([(X1, Y1, ze), (X0, Y1, ze), (xa, ym, zr), (xb, ym, zr)], cell, (-1, 0, 0), sv_b, (mu, mv))
        else:
            b.planar([(X0, Y0, ze), (X1, Y0, ze), (xa, ym, zr)], cell, (1, 0, 0), sv, (mu, mv))
            b.planar([(X1, Y1, ze), (X0, Y1, ze), (xa, ym, zr)], cell, (-1, 0, 0), sv_b, (mu, mv))
        b.planar([(X0, Y1, ze), (X0, Y0, ze), (xa, ym, zr)], cell, (0, -1, 0), sl, (mu, mv))
        b.planar([(X1, Y0, ze), (X1, Y1, ze), (xb, ym, zr)], cell, (0, 1, 0), sr, (mu, mv))
        if self.lod:
            return zr
        under = "beiral"
        b.planar([(x0, y0, zt), (x1, y0, zt), (X1, Y0, ze), (X0, Y0, ze)], under, (1, 0, 0), (0, -1, 0), (2, 1))
        b.planar([(x1, y1, zt), (x0, y1, zt), (X0, Y1, ze), (X1, Y1, ze)], under, (-1, 0, 0), (0, 1, 0), (2, 1))
        b.planar([(x0, y1, zt), (x0, y0, zt), (X0, Y0, ze), (X0, Y1, ze)], under, (0, -1, 0), (-1, 0, 0), (2, 1))
        b.planar([(x1, y0, zt), (x1, y1, zt), (X1, Y1, ze), (X1, Y0, ze)], under, (0, 1, 0), (1, 0, 0), (2, 1))
        ft = 0.16
        b.quad((X0, Y0, ze - ft), (X1 - X0, 0, 0), (0, 0, ft), "madeira")
        b.quad((X1, Y1, ze - ft), (X0 - X1, 0, 0), (0, 0, ft), "madeira")
        b.quad((X0, Y1, ze - ft), (0, Y0 - Y1, 0), (0, 0, ft), "madeira")
        b.quad((X1, Y0, ze - ft), (0, Y1 - Y0, 0), (0, 0, ft), "madeira")
        if cap and xb > xa:
            c = 0.16
            zl = zr - c * slope + 0.03
            zc = zr + 0.09
            capc = "cumeeira" if cell == "telha" else "concreto"
            b.quad((xa, ym - c, zl), (xb - xa, 0, 0), (0, c, zc - zl), capc)
            b.quad((xb, ym + c, zl), (xa - xb, 0, 0), (0, -c, zc - zl), capc)
        return zr

    def roof_shed(self, rect, zt, slope, over, cell, kind, front_high=True):
        """Uma agua (meia-agua): cai para tras (front_high) ou para a frente.
        Fecha com faixa de parede e triangulos laterais."""
        b = self.b
        x0, x1, y0, y1 = rect
        o = over
        D = y1 - y0
        rise = D * slope
        zh = zt + rise
        X0, X1, Y0, Y1 = x0 - o, x1 + o, y0 - o, y1 + o
        if front_high:
            zf, zb = zh + o * slope, zt - o * slope
        else:
            zf, zb = zt - o * slope, zh + o * slope
        mu, mv = atlas.METERS[cell]
        L = math.hypot(Y1 - Y0, zf - zb)
        s_ = (0.0, 0.0, min(1.0, (X1 - X0) / mu), min(1.0, L / mv))
        if front_high:
            b.quad((X1, Y1, zb), (X0 - X1, 0, 0), (0, Y0 - Y1, zf - zb), cell, s_)
        else:
            b.quad((X0, Y0, zf), (X1 - X0, 0, 0), (0, Y1 - Y0, zb - zf), cell, s_)
        wc = wall_cell(kind)
        ws = (0.0, CLEAN, 1.0, 1.0) if kind not in atlas.BRICKS else (0.0, 0.0, 1.0, 1.0)
        mw = atlas.METERS[wc]
        if front_high:
            b.quad((x0, y0, zt), (x1 - x0, 0, 0), (0, 0, rise), wc, (0.0, ws[1], 1.0, min(1.0, ws[1] + rise / 3)))
            b.planar([(x0, y1, zt), (x0, y0, zt), (x0, y0, zh)], wc, (0, -1, 0), (0, 0, 1), mw, ws)
            b.planar([(x1, y0, zt), (x1, y1, zt), (x1, y0, zh)], wc, (0, 1, 0), (0, 0, 1), mw, ws)
        else:
            b.quad((x1, y1, zt), (x0 - x1, 0, 0), (0, 0, rise), wc, (0.0, ws[1], 1.0, min(1.0, ws[1] + rise / 3)))
            b.planar([(x0, y1, zt), (x0, y0, zt), (x0, y1, zh)], wc, (0, -1, 0), (0, 0, 1), mw, ws)
            b.planar([(x1, y0, zt), (x1, y1, zt), (x1, y1, zh)], wc, (0, 1, 0), (0, 0, 1), mw, ws)
        if self.lod:
            return max(zf, zb)

        if o < 1e-3:
            return max(zf, zb)

        def zat(y):
            return zf + (zb - zf) * (y - Y0) / (Y1 - Y0)
        under = "beiral" if cell == "telha" else "concreto"
        b.planar([(x0, y0, zat(y0)), (x1, y0, zat(y0)), (X1, Y0, zat(Y0)), (X0, Y0, zat(Y0))], under, (1, 0, 0), (0, -1, 0))
        b.planar([(x1, y1, zat(y1)), (x0, y1, zat(y1)), (X0, Y1, zat(Y1)), (X1, Y1, zat(Y1))], under, (-1, 0, 0), (0, 1, 0))
        # beiral lateral (faixas X0..x0 e x1..X1 entre y0 e y1), virado para baixo
        for xa, xb in ((X0, x0), (x1, X1)):
            if xb - xa < 1e-3:
                continue
            pts = [(xb, y0, zat(y0)), (xa, y0, zat(y0)), (xa, y1, zat(y1)), (xb, y1, zat(y1))]
            self._poly_dir(pts, under, (0, 0, -1))
        ft = 0.12
        edge = "madeira" if cell == "telha" else "concreto"
        b.quad((X0, Y0, zf - ft), (X1 - X0, 0, 0), (0, 0, ft), edge)
        b.quad((X1, Y1, zb - ft), (X0 - X1, 0, 0), (0, 0, ft), edge)
        return max(zf, zb)

    def _poly_dir(self, pts, cell, want, meters=None):
        n = cross(sub(pts[1], pts[0]), sub(pts[2], pts[0]))
        if dot(n, want) < 0:
            pts = pts[::-1]
            n = mul(n, -1)
        nn = norm(n)
        au = norm(cross((0, 0, 1), nn)) if abs(nn[2]) < 0.95 else (1.0, 0.0, 0.0)
        av = cross(nn, au)
        self.b.planar(pts, cell, au, av, meters)

    def slab(self, rect, zt, thick, over, edge_cell, hole=None, top_cell="laje", top=True):
        """Laje: topo (menos o furo onde sobe o andar de cima), bordas e beiral por baixo."""
        b = self.b
        x0, x1, y0, y1 = rect
        ov = over if isinstance(over, (tuple, list)) else (over,) * 4
        o = max(ov)
        outer = (x0 - ov[0], x1 + ov[1], y0 - ov[2], y1 + ov[3])
        z1 = zt + thick
        if top:
            b.ring_top(outer, hole, z1, top_cell, atlas.METERS.get(top_cell))
        if self.lod:
            return z1
        X0, X1, Y0, Y1 = outer
        b.box(X0, X1, Y0, Y1, zt, z1, edge_cell, "FBLR")
        if o > 1e-3 and not self.lod:
            b.ring_bottom(outer, rect, zt, edge_cell)
        return z1

    def parapet(self, outer, z, h, t, kind, sides="FBLR"):
        """Platibanda sobre a laje (alvenaria), nas bordas do retangulo outer."""
        if self.lod:
            return
        b = self.b
        X0, X1, Y0, Y1 = outer
        cell = wall_cell(kind)
        s = (0.0, CLEAN, 1.0, min(1.0, CLEAN + h / 3 * (1 - CLEAN))) if kind not in atlas.BRICKS else (0, 0, 1, h / 3)
        inner = (X0 + t, X1 - t, Y0 + t, Y1 - t)
        if sides == "FBLR":
            b.box(X0, X1, Y0, Y1, z, z + h, cell, "FBLR", s)
            if self.lod:
                b.ring_top(outer, inner, z + h, "laje_borda")
                return
            x0, x1, y0, y1 = inner
            b.quad((x1, y0, z), (x0 - x1, 0, 0), (0, 0, h), cell, s)
            b.quad((x0, y1, z), (x1 - x0, 0, 0), (0, 0, h), cell, s)
            b.quad((x0, y0, z), (0, y1 - y0, 0), (0, 0, h), cell, s)
            b.quad((x1, y1, z), (0, y0 - y1, 0), (0, 0, h), cell, s)
            b.ring_top(outer, inner, z + h, "laje_borda")
        else:  # so a frente (fachada de platibanda)
            b.box(X0, X1, Y0, Y0 + t, z, z + h, cell, "FBLR" if not self.lod else "FB", s)
            b.quad((X0, Y0, z + h), (X1 - X0, 0, 0), (0, t, 0), "laje_borda")

    # ------------------------------------------------------------- acessorios
    def water_tank(self, cx, cy, z, big=1.0):
        """Caixa d'agua de polietileno azul (tronco de cone + tampa)."""
        b = self.b
        r0, r1, h = 0.56 * big, 0.70 * big, 0.80 * big
        if self.lod:
            b.box(cx - r1 * 0.85, cx + r1 * 0.85, cy - r1 * 0.85, cy + r1 * 0.85, z, z + h + 0.12, "caixa_azul", "FBLRT")
            return z + h
        b.cylinder(cx, cy, z, z + h, r0, r1, 8, "caixa_azul", phase=math.pi / 8)
        b.cylinder(cx, cy, z + h, z + h + 0.07, r1 + 0.03, r1 + 0.03, 8, "caixa_tampa", phase=math.pi / 8)
        b.cone(cx, cy, z + h + 0.07, r1 + 0.03, 0.20 * big, 8, "caixa_tampa", phase=math.pi / 8)
        return z + h + 0.27 * big

    def tank_base(self, cx, cy, z, size, h, kind):
        """Base de alvenaria da caixa d'agua (torre baixa)."""
        if self.lod:
            return z
        b = self.b
        s = size / 2
        cell = wall_cell(kind)
        sub_ = (0.0, CLEAN, 1.0, 0.6) if kind not in atlas.BRICKS else (0, 0, 0.4, 0.4)
        b.box(cx - s, cx + s, cy - s, cy + s, z, z + h, cell, "FBLR", sub_)
        b.box(cx - s, cx + s, cy - s, cy + s, z, z + h, "laje", "T")
        return z + h

    def antenna(self, cx, cy, z, yaw):
        if self.lod:
            return
        b = self.b
        top = (cx, cy, z + 0.9)
        b.prism((cx, cy, z), top, 0.035, "metal")
        el = math.radians(55)
        A = (math.cos(yaw) * math.cos(el), math.sin(yaw) * math.cos(el), math.sin(el))
        e1 = norm(cross(A, (0, 0, 1)))
        e2 = cross(A, e1)
        c = add(top, mul(A, 0.12))
        apex = sub(c, mul(A, 0.14))
        r = 0.42
        rim = [add(c, add(mul(e1, r * math.cos(2 * math.pi * k / 6)), mul(e2, r * math.sin(2 * math.pi * k / 6))))
               for k in range(6)]
        for k in range(6):
            p, q = rim[k], rim[(k + 1) % 6]
            b.tri(apex, p, q, "antena_prato")
            bk = mul(A, -0.012)
            b.tri(add(apex, bk), add(q, bk), add(p, bk), "parabolica")
        b.prism(rim[4], add(c, mul(A, 0.45)), 0.015, "metal")

    def clothesline(self, p0, p1, z):
        """Varal: dois postes e uma fileira de roupas (visivel dos dois lados)."""
        if self.lod:
            return
        b = self.b
        b.prism((p0[0], p0[1], z), (p0[0], p0[1], z + 1.85), 0.03, "metal")
        b.prism((p1[0], p1[1], z), (p1[0], p1[1], z + 1.85), 0.03, "metal")
        U = (p1[0] - p0[0], p1[1] - p0[1], 0.0)
        b.quad2((p0[0], p0[1], z + 1.05), U, (0, 0, 0.75), "roupas")

    def rebar(self, x, y, z, seed_ang, n=3):
        """Pilar inacabado: toco de concreto e vergalhoes saindo (esperando a proxima laje)."""
        if self.lod:
            return
        b = self.b
        s = 0.13
        b.box(x - s, x + s, y - s, y + s, z, z + 0.25, "concreto", "FBLRT")
        for k in range(n):
            a = seed_ang + k * 2.1
            ox, oy = math.cos(a) * 0.07, math.sin(a) * 0.07
            tip = (x + ox * 2.2 + 0.05 * math.cos(a * 3), y + oy * 2.2, z + 0.25 + 0.75 + 0.12 * math.sin(a * 5))
            b.prism((x + ox, y + oy, z + 0.2), tip, 0.018, "ferrugem")

    def pillar(self, x, y, z0, z1, s=0.12, cell="concreto"):
        zb = z0 - self.f if z0 <= 1e-6 else z0
        self.b.box(x - s, x + s, y - s, y + s, zb, z1, cell, "FBLR")

    def wall_low(self, x0, x1, y, h, t, kind, gates=(), ends="LR"):
        """Muro na frente do lote (face externa em -Y). gates: [(a_centro, w, h, cell)]."""
        b = self.b
        cell = kind if kind.startswith("muro") or kind.startswith("f1") else wall_cell(kind)
        if self.lod:
            zb = -self.f
            b.quad((x0, y, zb), (x1 - x0, 0, 0), (0, 0, h - zb), "f1_muro_pichado" if kind == "muro_pichado"
                   else ("f1_muro" if h > 2.0 else cell), (0, 0, 1, 1) if h > 2.0 else (0.0, 0.0, 1.0, min(1, h / 3)))
            b.quad((x1, y + t, zb), (x0 - x1, 0, 0), (0, 0, h - zb), cell, (0.0, CLEAN, 1.0, 1.0))
            b.quad((x0, y, h), (x1 - x0, 0, 0), (0, t, 0), "laje_borda")
            return
        mu, mv = atlas.METERS.get(cell, (3.0, 3.0))
        L = x1 - x0
        n = int(math.ceil(L / (mu * 1.05))) if cell in ("muro_pichado", "w_tijolo", "w_baiano") else 1
        for k in range(n):
            xa = x0 + L * k / n
            xb = x0 + L * (k + 1) / n
            us = min(1.0, (xb - xa) / mu) if n > 1 or cell in ("muro_pichado", "w_tijolo", "w_baiano") else 1.0
            b.quad((xa, y, 0), (xb - xa, 0, 0), (0, 0, h), cell, (0.0, 0.0, us, min(1.0, h / mv)))
        b.quad((x1, y + t, 0), (x0 - x1, 0, 0), (0, 0, h), cell, (0.0, CLEAN, 1.0, min(1.0, CLEAN + h / mv)))
        b.quad((x0, y, h), (x1 - x0, 0, 0), (0, t, 0), "laje_borda")
        if "L" in ends:
            b.quad((x0, y + t, 0), (0, -t, 0), (0, 0, h), cell, (0, 0, 0.05, min(1.0, h / mv)))
        if "R" in ends:
            b.quad((x1, y, 0), (0, t, 0), (0, 0, h), cell, (0, 0, 0.05, min(1.0, h / mv)))
        if self.f > 0:
            b.quad((x0, y, -self.f), (x1 - x0, 0, 0), (0, 0, self.f), "fundacao", (0, 0, 1, min(1, self.f / 3)))
            b.quad((x1, y + t, -self.f), (x0 - x1, 0, 0), (0, 0, self.f), "fundacao", (0, 0, 1, min(1, self.f / 3)))
        for (a, gw, gh, gcell) in gates:
            b.quad((x0 + a - gw / 2, y - 0.03, 0), (gw, 0, 0), (0, 0, gh), gcell)

    def wall_side(self, x, y0, y1, h, t, kind):
        """Muro lateral do lote (do muro da frente ate a casa), sem pontas."""
        if self.lod or y1 - y0 < 0.2:
            return
        b = self.b
        cell = wall_cell(kind) if not kind.startswith("muro") else kind
        mu, mv = atlas.METERS.get(cell, (3.0, 3.0))
        s = (0.0, 0.0, min(1.0, (y1 - y0) / mu), min(1.0, h / mv))
        b.quad((x, y1, 0), (0, y0 - y1, 0), (0, 0, h), cell, s)
        b.quad((x + t, y0, 0), (0, y1 - y0, 0), (0, 0, h), cell, s)
        b.quad((x, y0, h), (t, 0, 0), (0, y1 - y0, 0), "laje_borda")

    def stairs(self, rect, side, a_lo, a_hi, zf, width, kind, rail=True):
        """Escada externa de alvenaria encostada na parede (sobe de a_lo para a_hi),
        com patamar de 1 m no alto. Fechada por baixo (sem vao)."""
        if self.lod:
            return
        b = self.b
        wall = Wall(rect, side)
        land = 1.0 if a_hi > a_lo else -1.0
        a_end = a_hi + land
        P = lambda a, z, d: wall.at(a, z, d)
        cell = wall_cell(kind)
        # rampa (degraus pintados) e patamar
        ramp = [P(a_lo, 0, 0), P(a_lo, 0, width), P(a_hi, zf, width), P(a_hi, zf, 0)]
        self._poly_dir_uv(ramp, "escada", (0, 0, 1), wall.N(1), sub(P(a_hi, zf, 0), P(a_lo, 0, 0)))
        self._poly_dir_uv([P(a_hi, zf, 0), P(a_hi, zf, width), P(a_end, zf, width), P(a_end, zf, 0)], "laje",
                          (0, 0, 1), wall.N(1), wall.U(1))
        # lateral externa (trapezio) e frente do patamar
        side_pts = [P(a_lo, -self.f, width), P(a_end, -self.f, width), P(a_end, zf, width), P(a_hi, zf, width)]
        if self.f > 0:
            side_pts.append(P(a_lo, 0, width))
        self._poly_dir(side_pts, cell, wall.N(1), atlas.METERS[cell])
        end = [P(a_end, -self.f, 0), P(a_end, -self.f, width), P(a_end, zf, width), P(a_end, zf, 0)]
        self._poly_dir(end, cell, wall.U(land), atlas.METERS[cell])
        if rail:
            r = 0.02
            p0 = add(P(a_lo, 0, width - 0.05), (0, 0, 0.95))
            p1 = add(P(a_hi, zf, width - 0.05), (0, 0, 0.95))
            p2 = add(P(a_end, zf, width - 0.05), (0, 0, 0.95))
            b.prism(p0, p1, r, "grade")
            b.prism(p1, p2, r, "grade")
            b.prism(P(a_lo, 0, width - 0.05), p0, r, "grade")
            b.prism(P(a_end, zf, width - 0.05), p2, r, "grade")

    def _poly_dir_uv(self, pts, cell, want, au, av):
        n = cross(sub(pts[1], pts[0]), sub(pts[2], pts[0]))
        if dot(n, want) < 0:
            pts = pts[::-1]
        self.b.planar(pts, cell, norm(au), norm(av))

    def carport(self, x0, x1, y0, y1, z, kind_cell="fibro"):
        """Cobertura de garagem: meia-agua em 2 postes na frente, presa na casa atras."""
        if self.lod:
            return
        b = self.b
        slope = 0.12
        zf = z - (y1 - y0) * slope
        mu, mv = atlas.METERS[kind_cell]
        s_ = (0.0, 0.0, min(1.0, (x1 - x0) / mu), min(1.0, (y1 - y0) / mv))
        b.quad((x0, y0, zf), (x1 - x0, 0, 0), (0, y1 - y0, z - zf), kind_cell, s_)
        b.quad((x1, y0, zf), (x0 - x1, 0, 0), (0, y1 - y0, z - zf), "concreto")
        b.quad((x0, y0, zf - 0.12), (x1 - x0, 0, 0), (0, 0, 0.12), "metal")
        for x in (x0 + 0.15, x1 - 0.15):
            b.prism((x, y0 + 0.15, -self.f), (x, y0 + 0.15, zf), 0.06, "metal", 4)

    def porch(self, x0, x1, y_wall, depth, z_top, slope, cell):
        """Varanda: meia-agua encostada na frente da casa, em pilares."""
        b = self.b
        zf = z_top - depth * slope
        y0 = y_wall - depth
        mu, mv = atlas.METERS[cell]
        s_ = (0.0, 0.0, min(1.0, (x1 - x0) / mu), min(1.0, depth / mv))
        b.quad((x0, y0, zf), (x1 - x0, 0, 0), (0, depth, z_top - zf), cell, s_)
        if self.lod:
            return
        b.quad((x1, y0, zf), (x0 - x1, 0, 0), (0, depth, z_top - zf), "beiral")
        b.quad((x0, y0, zf - 0.15), (x1 - x0, 0, 0), (0, 0, 0.15), "madeira")
        n = 3 if x1 - x0 > 6.0 else 2
        for k in range(n):
            x = x0 + 0.2 + (x1 - x0 - 0.4) * k / (n - 1)
            self.pillar(x, y0 + 0.25, 0.0, zf - 0.15, 0.1, "branco")
