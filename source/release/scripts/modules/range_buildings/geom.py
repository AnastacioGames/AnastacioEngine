# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
# ##### END GPL LICENSE BLOCK #####

"""Primitivas de malha com UV no atlas (Python puro, sem bpy).

Convencao dos quads: quad(o, U, V) gera o, o+U, o+U+V, o+V. A normal e U x V, entao
U e "a direita de quem olha a face de fora" e V e "para cima". O UV segue o mesmo
sentido: u cresce com U e v com V (texto de placa fica legivel).
"""

import math

from . import atlas


def add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def mul(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def length(a):
    return math.sqrt(dot(a, a))


def norm(a):
    n = length(a)
    return (a[0] / n, a[1] / n, a[2] / n) if n > 1e-12 else (0.0, 0.0, 0.0)


class Built:
    """Malha em construcao: verts, faces e UV por canto de cada face."""

    def __init__(self):
        self.verts = []
        self.faces = []
        self.uvs = []

    def poly(self, pts, uvs):
        i = len(self.verts)
        self.verts.extend((float(p[0]), float(p[1]), float(p[2])) for p in pts)
        self.faces.append(tuple(range(i, i + len(pts))))
        self.uvs.append([(float(u), float(v)) for u, v in uvs])

    def quad(self, o, U, V, cell, sub_=(0.0, 0.0, 1.0, 1.0)):
        if length(U) < 1e-6 or length(V) < 1e-6:
            return
        u0, v0, u1, v1 = atlas.uv_rect(cell, sub_)
        p1 = add(o, U)
        self.poly([o, p1, add(p1, V), add(o, V)], [(u0, v0), (u1, v0), (u1, v1), (u0, v1)])

    def quad2(self, o, U, V, cell, sub_=(0.0, 0.0, 1.0, 1.0)):
        """Quad visivel dos dois lados (duas faces opostas)."""
        self.quad(o, U, V, cell, sub_)
        u0, v0, u1, v1 = sub_
        n = mul(norm(cross(U, V)), -0.01)  # verso afastado 1 cm (sem z-fight onde nao ha culling)
        self.quad(add(add(o, U), n), mul(U, -1), V, cell, (u1, v0, u0, v1))

    def planar(self, pts, cell, au, av, meters=None, sub_=(0.0, 0.0, 1.0, 1.0)):
        """Poligono com UV por projecao nos eixos au (u) e av (v).

        meters = (mu, mv): tamanho real do miolo da celula; o UV mantem a escala ate
        caber na celula (acima disso estica). Sem meters, estica para caber."""
        s = [dot(p, au) for p in pts]
        t = [dot(p, av) for p in pts]
        s0, t0 = min(s), min(t)
        ds = max(s) - s0
        dt = max(t) - t0
        if meters:
            ds = max(ds, meters[0])
            dt = max(dt, meters[1])
        ds = ds or 1.0
        dt = dt or 1.0
        u0, v0, u1, v1 = atlas.uv_rect(cell, sub_)
        uvs = [(u0 + (u1 - u0) * (a - s0) / ds, v0 + (v1 - v0) * (b - t0) / dt) for a, b in zip(s, t)]
        self.poly(pts, uvs)

    def tri(self, a, b, c, cell, au=None, av=None, sub_=(0.0, 0.0, 1.0, 1.0)):
        n = cross(sub(b, a), sub(c, a))
        if length(n) < 1e-9:
            return
        if au is None:
            au = norm(sub(b, a))
            av = norm(cross(norm(n), au))
        self.planar([a, b, c], cell, au, av, None, sub_)

    # ------------------------------------------------------------- solidos
    def box(self, x0, x1, y0, y1, z0, z1, cell, faces="FBLRT", sub_=(0.0, 0.0, 1.0, 1.0)):
        dx, dy, dz = x1 - x0, y1 - y0, z1 - z0
        if "F" in faces:
            self.quad((x0, y0, z0), (dx, 0, 0), (0, 0, dz), cell, sub_)
        if "B" in faces:
            self.quad((x1, y1, z0), (-dx, 0, 0), (0, 0, dz), cell, sub_)
        if "R" in faces:
            self.quad((x1, y0, z0), (0, dy, 0), (0, 0, dz), cell, sub_)
        if "L" in faces:
            self.quad((x0, y1, z0), (0, -dy, 0), (0, 0, dz), cell, sub_)
        if "T" in faces:
            self.quad((x0, y0, z1), (dx, 0, 0), (0, dy, 0), cell, sub_)
        if "D" in faces:
            self.quad((x0, y1, z0), (dx, 0, 0), (0, -dy, 0), cell, sub_)

    def prism(self, p0, p1, r, cell, sides=3):
        """Barra fina (vergalhao, fio, poste) ao redor do segmento p0-p1, sem tampas."""
        d = norm(sub(p1, p0))
        a = (1.0, 0.0, 0.0) if abs(d[0]) < 0.9 else (0.0, 1.0, 0.0)
        e1 = norm(cross(d, a))
        e2 = cross(d, e1)
        ring = []
        for k in range(sides):
            ang = 2 * math.pi * k / sides
            ring.append(add(mul(e1, r * math.cos(ang)), mul(e2, r * math.sin(ang))))
        for k in range(sides):
            a0, a1 = ring[k], ring[(k + 1) % sides]
            q = [add(p0, a0), add(p0, a1), add(p1, a1), add(p1, a0)]
            # normal para fora: (a1-a0) x d deve apontar como a0+a1
            n = cross(sub(a1, a0), d)
            if dot(n, add(a0, a1)) < 0:
                q = [q[1], q[0], q[3], q[2]]
            u0, v0, u1, v1 = atlas.uv_rect(cell)
            self.poly(q, [(u0, v0), (u1, v0), (u1, v1), (u0, v1)])

    def cylinder(self, cx, cy, z0, z1, r0, r1, n, cell, sub_=(0.0, 0.0, 1.0, 1.0), phase=0.0):
        u0, v0, u1, v1 = atlas.uv_rect(cell, sub_)
        for k in range(n):
            a0 = phase + 2 * math.pi * k / n
            a1 = phase + 2 * math.pi * (k + 1) / n
            p = [(cx + r0 * math.cos(a0), cy + r0 * math.sin(a0), z0),
                 (cx + r0 * math.cos(a1), cy + r0 * math.sin(a1), z0),
                 (cx + r1 * math.cos(a1), cy + r1 * math.sin(a1), z1),
                 (cx + r1 * math.cos(a0), cy + r1 * math.sin(a0), z1)]
            ua = u0 + (u1 - u0) * k / n
            ub = u0 + (u1 - u0) * (k + 1) / n
            self.poly(p, [(ua, v0), (ub, v0), (ub, v1), (ua, v1)])

    def cone(self, cx, cy, z0, r, hc, n, cell, phase=0.0):
        """Tampa conica (aponta para cima), sem fundo."""
        u0, v0, u1, v1 = atlas.uv_rect(cell)
        top = (cx, cy, z0 + hc)
        for k in range(n):
            a0 = phase + 2 * math.pi * k / n
            a1 = phase + 2 * math.pi * (k + 1) / n
            p = [(cx + r * math.cos(a0), cy + r * math.sin(a0), z0),
                 (cx + r * math.cos(a1), cy + r * math.sin(a1), z0), top]
            self.poly(p, [(u0, v0), (u1, v0), ((u0 + u1) / 2, v1)])

    def ring_top(self, outer, inner, z, cell, meters=None):
        """Face de cima (+Z) do retangulo outer menos o retangulo inner (x0, x1, y0, y1).
        inner = None gera o retangulo inteiro. Ate 4 quads, sem faces de area zero."""
        X0, X1, Y0, Y1 = outer
        rects = []
        if inner is None:
            rects.append((X0, X1, Y0, Y1))
        else:
            x0, x1, y0, y1 = inner
            rects += [(X0, X1, Y0, y0), (X0, X1, y1, Y1), (X0, x0, y0, y1), (x1, X1, y0, y1)]
        for a, b, c, d in rects:
            if b - a > 1e-4 and d - c > 1e-4:
                pts = [(a, c, z), (b, c, z), (b, d, z), (a, d, z)]
                self.planar(pts, cell, (1, 0, 0), (0, 1, 0), meters)

    def ring_bottom(self, outer, inner, z, cell):
        """Face de baixo (-Z) de outer menos inner (beiral de laje)."""
        X0, X1, Y0, Y1 = outer
        x0, x1, y0, y1 = inner
        for a, b, c, d in ((X0, X1, Y0, y0), (X0, X1, y1, Y1), (X0, x0, y0, y1), (x1, X1, y0, y1)):
            if b - a > 1e-4 and d - c > 1e-4:
                pts = [(a, d, z), (b, d, z), (b, c, z), (a, c, z)]
                self.planar(pts, cell, (1, 0, 0), (0, -1, 0))

    def extend(self, other, offset=(0.0, 0.0, 0.0)):
        i = len(self.verts)
        self.verts.extend(add(v, offset) for v in other.verts)
        self.faces.extend(tuple(k + i for k in f) for f in other.faces)
        self.uvs.extend(list(u) for u in other.uvs)

    def tris(self):
        return sum(len(f) - 2 for f in self.faces)


# ---------------------------------------------------------------- paredes

class Wall:
    """Uma face de parede do retangulo (x0, x1, y0, y1): F (frente, -Y), B, L (-X), R (+X).
    Coordenada a = distancia ao longo da parede, da esquerda de quem olha de fora."""

    def __init__(self, rect, side):
        x0, x1, y0, y1 = rect
        if side == "F":
            self.start, self.u, self.n, self.len = (x0, y0), (1, 0), (0, -1), x1 - x0
        elif side == "R":
            self.start, self.u, self.n, self.len = (x1, y0), (0, 1), (1, 0), y1 - y0
        elif side == "B":
            self.start, self.u, self.n, self.len = (x1, y1), (-1, 0), (0, 1), x1 - x0
        else:
            self.start, self.u, self.n, self.len = (x0, y1), (0, -1), (-1, 0), y1 - y0
        self.side = side

    def at(self, a, z, off=0.0):
        return (self.start[0] + self.u[0] * a + self.n[0] * off,
                self.start[1] + self.u[1] * a + self.n[1] * off, z)

    def U(self, w):
        return (self.u[0] * w, self.u[1] * w, 0.0)

    def N(self, d):
        return (self.n[0] * d, self.n[1] * d, 0.0)


def wall_quad(b, wall, a0, a1, z0, z1, cell, off=0.0, sub_=(0.0, 0.0, 1.0, 1.0)):
    b.quad(wall.at(a0, z0, off), wall.U(a1 - a0), (0, 0, z1 - z0), cell, sub_)


def wall_box(b, wall, a0, a1, z0, z1, depth, cell, front_cell=None, faces="FLRTD", sub_=(0, 0, 1, 1)):
    """Caixa saindo da parede (ar-condicionado, placa, peitoril): sem a face encostada."""
    o = wall.at(a0, z0, depth)
    U = wall.U(a1 - a0)
    V = (0.0, 0.0, z1 - z0)
    D = wall.N(-depth)  # volta para a parede
    if "F" in faces:
        b.quad(o, U, V, front_cell or cell, sub_)
    if "L" in faces:
        b.quad(add(o, D), mul(D, -1), V, cell)
    if "R" in faces:
        b.quad(add(o, U), D, V, cell)
    if "T" in faces:
        b.quad(add(o, V), U, D, cell)
    if "D" in faces:
        b.quad(add(o, D), U, mul(D, -1), cell)
