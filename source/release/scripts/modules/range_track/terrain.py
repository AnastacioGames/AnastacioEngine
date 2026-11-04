# Track Tool: terreno em volta do traçado (faixas SLOPE e HILL, grade longe da pista, horizonte).
#
# Contrato em docs/plano-track-tool.md ("Contrato entre módulos"):
#   generate_terrain(scene, track_obj, frames, edges) -> [objetos]
#
# Base: D:\ProjetoRolimaRacer\Tools\gerar_cenario_pista.py (altura_terreno / base_global).
# Diferenças: IDW mais local (potência 4) e pista estendida além das pontas abertas no fundo.
#
# Como a altura é montada (TerrainField.height):
#   - "longe": altura de fundo = IDW das alturas da pista numa grade grossa de 25 m (encosta suave),
#     + subida leve com a distância + morros (noise fractal, hill_height / hill_scale);
#   - perto da pista, cada lado de cada amostra tem uma borda (a última faixa de estrada: asfalto, guia,
#     calçada, borda ou malha). Se o lado tem faixa SLOPE, o talude sai dessa borda com a inclinação
#     slope_deg e sobe ou desce até encontrar o "longe" (cone limitado pela largura da faixa); depois
#     o terreno vai da ponta do talude até o "longe" em ~30 m. Sem SLOPE, o terreno encosta na borda
#     um pouco abaixo dela (como o protótipo) e uma saia curta cobre a fresta;
#   - faixa HILL troca a altura (height) e a distância em que os morros chegam ao máximo (width).
# A grade (terrain_cell) amostra essa função; depois cada vértice da grade é rebaixado abaixo dos
# pontos da estrada e do talude que caem na sua célula (só rebaixa, nunca sobe). Assim nenhum ponto da
# estrada fica sob o terreno. Faces da grade que ficam inteiras sob a estrada/talude são removidas.
#
# Sem física em nada daqui (decoração e morros são NO_COLLISION).
import math

import bpy
from mathutils import Vector, noise, kdtree

from . import decor as _decor

ROAD_KINDS = {'ASPHALT', 'CURB', 'SIDEWALK', 'BORDER', 'MESH'}
CLEAR_ROAD = 0.35      # folga da grade abaixo de qualquer ponto da estrada
CLEAR_SLOPE = 0.12     # folga da grade abaixo do talude (o talude é uma malha própria por cima)
DROP_WALL = 1.1        # sem talude, com mureta: terreno 1.1 m abaixo da borda (protótipo)
DROP_OPEN = 0.25       # sem talude e sem mureta: quase rente à borda (a saia cobre a fresta)
UV_SCALE = 7.0         # grama: UV = mundo / 7 m (igual no talude e na grade, costura invisível)
TILE_CELLS = 64        # grade dividida em blocos de 64 x 64 células (culling)
STRIP_BLOCK = 200.0    # talude/saia em blocos de 200 m de pista

_FIELD_CACHE = {}


def smooth(a, b, x):
    if x <= a:
        return 0.0
    if x >= b:
        return 1.0
    t = (x - a) / (b - a)
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------------- perfil e faixas
def profile_of(scene, track_obj):
    """Perfil do traçado (props.find_profile: primeiro na cena dada, depois nas outras)."""
    try:
        from . import props
        return props.find_profile(track_obj.range_track.profile, scene)
    except Exception:
        return None


def road_edge(edges, i, side):
    """(off, z, BandEdge) da borda externa da última faixa de estrada (ASPHALT, CURB, SIDEWALK,
    BORDER, MESH) antes do primeiro SLOPE/HILL, já com inclinação e trechos (layout.py)."""
    last = None
    for be in edges.bands(i, side):
        if be.kind in ROAD_KINDS:
            last = be
        else:
            break
    if last is None:
        f = edges.frames
        return 0.0, f.pos[f.wrap(i)].z, None
    return last.off_out, last.z_out, last


def first_band(edges, i, side, kind):
    """Primeira BandEdge do tipo (depois dos trechos) no lado, ou None."""
    for be in edges.bands(i, side):
        if be.kind == kind:
            return be
    return None


def _h(v):
    """Vetor horizontal unitário."""
    w = Vector((v.x, v.y, 0.0))
    return w.normalized() if w.length > 1e-9 else Vector((1.0, 0.0, 0.0))


# ---------------------------------------------------------------- campo de altura
class TerrainField:
    """Altura do terreno em volta do traçado. Usado pela grade, pelo talude e pela decoração
    (decor.py coloca props no chão com `ground`, que interpola a grade como a malha)."""

    def __init__(self, scene, track_obj, frames, edges):
        st = track_obj.range_track
        self.settings = st
        self.frames = frames
        self.edges = edges
        self.profile = profile_of(scene, track_obj)
        self.cell = max(1.0, float(getattr(st, "terrain_cell", 5.0)))
        self.margin = max(20.0, float(getattr(st, "terrain_margin", 260.0)))
        self.hill_h = float(getattr(st, "hill_height", 28.0))
        self.hill_s = max(1.0, float(getattr(st, "hill_scale", 220.0)))
        P = [Vector(p) for p in frames.pos]
        N = len(P)
        self.N = N
        self.P = P
        self.T = [_h(t) for t in frames.tan]
        self.L = [_h(l) for l in frames.lat]                  # esquerda horizontal
        self.S = list(frames.s)
        self.length = float(frames.length)
        self.cyclic = bool(frames.cyclic)

        # bordas da estrada e parâmetros de talude/morro por amostra e lado (BandEdge do layout,
        # já com os trechos: largura, inclinação e troca de tipo)
        self.eo, self.ez = {}, {}
        self.sw, self.stn, self.hh, self.hw, self.h0 = {}, {}, {}, {}, {}
        self.wall = {}
        for side in (1, -1):
            eo, ez, sw, stn, hh, hw, h0 = [], [], [], [], [], [], []
            walls = 0
            for i in range(N):
                off, z, last = road_edge(edges, i, side)
                eo.append(float(off))
                ez.append(float(z))
                if last is not None and last.kind == 'BORDER' and last.border_type != 'NONE':
                    walls += 1
                slope = first_band(edges, i, side, 'SLOPE')
                if slope is not None and slope.width > 0.05:
                    sw.append(float(slope.width))
                    # o sinal de slope_deg não importa aqui: o talude sobe ou desce até o terreno
                    a = abs(slope.slope_deg) or 33.0
                    stn.append(math.tan(math.radians(min(80.0, max(5.0, a)))))
                else:
                    sw.append(0.0)
                    stn.append(1.0)
                hill = first_band(edges, i, side, 'HILL')
                if hill is not None:
                    hh.append(float(hill.height))
                    hw.append(max(20.0, float(hill.width)))
                    h0.append(max(30.0, float(hill.off_in)))
                else:
                    hh.append(self.hill_h)
                    hw.append(130.0)
                    h0.append(30.0)
            self.wall[side] = walls > N // 2
            self.eo[side], self.ez[side], self.sw[side], self.stn[side] = eo, ez, sw, stn
            self.hh[side], self.hw[side], self.h0[side] = hh, hw, h0
        self.zroad = [(self.ez[1][i] + self.ez[-1][i]) * 0.5 for i in range(N)]
        self._limit_slopes()

        self.kd = kdtree.KDTree(N)
        for i, p in enumerate(P):
            self.kd.insert(Vector((p.x, p.y, 0.0)), i)
        self.kd.balance()

        xs = [p.x for p in P]
        ys = [p.y for p in P]
        M = self.margin
        c = self.cell
        self.x0, self.y0 = math.floor((min(xs) - M) / c) * c, math.floor((min(ys) - M) / c) * c
        self.nx = int(math.ceil((max(xs) + M - self.x0) / c)) + 1
        self.ny = int(math.ceil((max(ys) + M - self.y0) / c)) + 1
        self.x1 = self.x0 + (self.nx - 1) * c
        self.y1 = self.y0 + (self.ny - 1) * c
        self._base_grid()
        self._lattice = None

    # talude não pode dobrar no miolo de curva fechada nem cair sobre outro trecho da pista
    def _limit_slopes(self):
        N = self.N
        for side in (1, -1):
            sw = self.sw[side]
            for i in range(N):
                if sw[i] <= 0:
                    continue
                a, b = self.T[max(0, i - 2)], self.T[min(N - 1, i + 2)]
                ds = max(1e-3, self.S[min(N - 1, i + 2)] - self.S[max(0, i - 2)])
                ang = math.atan2(a.x * b.y - a.y * b.x, a.dot(b))
                if ang * side > 1e-4:                       # este lado é o de dentro da curva
                    R = ds / ang * side
                    sw[i] = min(sw[i], max(0.0, (R - self.eo[side][i]) * 0.7))
                # outro trecho mais perto que a própria borda: corta o talude antes dele
                w, ok = sw[i], 0.0
                for f in (0.25, 0.5, 0.75, 1.0):
                    d = w * f
                    p = self.P[i] + self.L[i] * (side * (self.eo[side][i] + d))
                    if self.edges.dist_to_edge(p.x, p.y) < d - 1.0:
                        break
                    ok = d
                sw[i] = ok

    def _base_grid(self):
        gc = 25.0
        self.gc = gc
        self.gx0, self.gy0 = self.x0 - gc, self.y0 - gc
        self.gnx = int((self.x1 - self.x0) / gc) + 4
        self.gny = int((self.y1 - self.y0) / gc) + 4
        stride = max(1, self.N // 400)
        pts = [(self.P[j].x, self.P[j].y, self.zroad[j]) for j in range(0, self.N, stride)]
        if not self.cyclic and self.N > 4:
            # pista aberta: estende a pista (virtual) além das pontas com o greide dos últimos 40 m,
            # senão a média puxa o fundo para a altura do resto da pista (buraco/morro na ponta)
            for end, sg in ((0, -1), (self.N - 1, 1)):
                k = min(self.N - 1, max(0, end - sg * max(1, int(40.0 / max(0.1, self.frames.step)))))
                ds = abs(self.S[end] - self.S[k])
                g = (self.zroad[end] - self.zroad[k]) / ds * sg if ds > 1e-3 else 0.0
                g = max(-0.12, min(0.12, g))
                p, t = self.P[end], self.T[end]
                for dist in range(10, 260, 10):
                    q = p + t * (sg * dist)
                    pts.append((q.x, q.y, self.zroad[end] + g * dist * sg))   # g = greide para a frente
        g = []
        for gj in range(self.gny):
            gy = self.gy0 + gj * gc
            for gi in range(self.gnx):
                gx = self.gx0 + gi * gc
                soma = pw = 0.0
                for px, py, pz in pts:
                    dx, dy = gx - px, gy - py
                    # IDW potência 4: a pista perto manda (com 1/(d²+3600) do protótipo os
                    # trechos longe somados puxavam o fundo dezenas de metros nas pontas)
                    q = dx * dx + dy * dy + 900.0
                    w = 1.0 / (q * q)
                    soma += pz * w
                    pw += w
                g.append(soma / pw)
        self.bgrid = g

    def base(self, x, y):
        fx, fy = (x - self.gx0) / self.gc, (y - self.gy0) / self.gc
        gi = min(self.gnx - 2, max(0, int(fx)))
        gj = min(self.gny - 2, max(0, int(fy)))
        tx, ty = min(1.0, max(0.0, fx - gi)), min(1.0, max(0.0, fy - gj))
        g, n = self.bgrid, self.gnx
        a = g[gj * n + gi] * (1 - tx) + g[gj * n + gi + 1] * tx
        b = g[(gj + 1) * n + gi] * (1 - tx) + g[(gj + 1) * n + gi + 1] * tx
        return a * (1 - ty) + b * ty

    def far(self, x, y, d, side, i):
        """Terreno "longe" (sem a influência da borda): fundo + subida + morros."""
        h0 = self.h0[side][i]
        amp = smooth(h0, h0 + self.hw[side][i], d)
        hh = self.hh[side][i]
        s = self.hill_s
        z = self.base(x, y) + d * 0.10 * smooth(20.0, 200.0, d)
        if amp > 0 and hh != 0:
            z += noise.fractal(Vector((x / s, y / s, 0.37)), 0.5, 2.0, 4) * hh * amp
            z += abs(noise.noise(Vector((x / (s * 0.41), y / (s * 0.41), 1.7)))) * hh * 0.36 * amp
        return z

    def slope_z(self, i, side, dd):
        """Altura do talude a dd metros da borda (0 <= dd <= largura)."""
        ze = self.ez[side][i]
        if dd <= 0:
            return ze
        off = self.eo[side][i] + dd
        p = self.P[i] + self.L[i] * (side * off)
        target = self.far(p.x, p.y, off, side, i)
        lim = dd * self.stn[side][i]
        return ze + max(-lim, min(lim, target - ze))

    def locate(self, x, y):
        """(i, side, sl, d): amostra mais perto, lado, deslocamento lateral, distância ao centro."""
        _, i, d = self.kd.find(Vector((x, y, 0.0)))
        p = self.P[i]
        sl = (x - p.x) * self.L[i].x + (y - p.y) * self.L[i].y
        return i, (1 if sl >= 0 else -1), sl, d

    def height(self, x, y, info=None):
        """Altura contínua (sem o rebaixo sob a estrada). info (dict) recebe 'zone':
        ROAD (sob a estrada), SLOPE (sob o talude) ou OPEN."""
        i, side, sl, d = self.locate(x, y)
        a = abs(sl)
        eo, ez = self.eo[side][i], self.ez[side][i]
        # pontas do traçado aberto: além do início/fim conta também a distância ao longo
        beyond = 0.0
        if not self.cyclic and i in (0, self.N - 1):
            p = self.P[i]
            al = (x - p.x) * self.T[i].x + (y - p.y) * self.T[i].y
            if (i == 0 and al < 0) or (i == self.N - 1 and al > 0):
                beyond = abs(al)
        if a <= eo and beyond < 0.5:
            if info is not None:
                info['zone'] = 'ROAD'
                depth = eo - a
                if not self.cyclic:      # perto das pontas não esconde faces (a ponta fica aberta)
                    depth = min(depth, self.S[i] - 8.0, self.length - self.S[i] - 8.0)
                info['depth'] = depth
            # dentro da estrada: altura da borda do lado, mistura linear até o outro lado
            el, er = self.eo[1][i], self.eo[-1][i]
            t = (sl + er) / max(1e-6, el + er)
            return self.ez[-1][i] + (self.ez[1][i] - self.ez[-1][i]) * t - DROP_WALL
        dd = math.hypot(max(0.0, a - eo), beyond)
        longe = self.far(x, y, d, side, i)
        w = self.sw[side][i]
        if w > 0:
            if dd <= w:
                if info is not None:
                    # além da ponta não há talude por cima: a grade fica visível ali
                    info['zone'] = 'SLOPE' if beyond < 0.5 else 'OPEN'
                    info['depth'] = w - dd
                return self.slope_z(i, side, dd) - CLEAR_SLOPE
            if info is not None:
                info['zone'] = 'OPEN'
            zw = self.slope_z(i, side, w)
            t = smooth(0.0, 30.0, dd - w)
            return zw - CLEAR_SLOPE * (1.0 - t) + (longe - zw) * t
        if info is not None:
            info['zone'] = 'OPEN'
        perto = ez - (DROP_WALL if self.wall[side] else DROP_OPEN)
        return perto + (longe - perto) * smooth(3.0, 45.0, dd)

    # ------------------------------------------------ grade (a mesma da malha)
    def lattice(self):
        """Alturas da grade já rebaixadas sob estrada e talude (lista nx*ny) + zonas."""
        if self._lattice is not None:
            return self._lattice
        nx, ny, c = self.nx, self.ny, self.cell
        z = [0.0] * (nx * ny)
        hidden = [False] * (nx * ny)
        info = {}
        for j in range(ny):
            y = self.y0 + j * c
            for i in range(nx):
                x = self.x0 + i * c
                info.clear()
                k = j * nx + i
                z[k] = self.height(x, y, info)
                zone = info.get('zone')
                if zone in ('ROAD', 'SLOPE') and info.get('depth', 0.0) > 0.6:
                    hidden[k] = True
        # rebaixo: cada ponto da estrada/talude puxa para baixo os 4 cantos da célula onde cai
        for x, y, zz in self.surface_points():
            ci, cj = int((x - self.x0) / c), int((y - self.y0) / c)
            for jj in (cj, cj + 1):
                if 0 <= jj < ny:
                    for ii in (ci, ci + 1):
                        if 0 <= ii < nx:
                            k = jj * nx + ii
                            if z[k] > zz:
                                z[k] = zz
        self._lattice = (z, hidden)
        return self._lattice

    def surface_points(self):
        """Pontos (x, y, z_limite) que a grade não pode ultrapassar: estrada inteira (todas as faixas
        de estrada, ~a cada 1,5 m na lateral) e o talude. Também o meio entre amostras."""
        out = []
        N = self.N
        for i in range(N):
            P, L = self.P[i], self.L[i]
            for side in (1, -1):
                off_e = self.eo[side][i]
                n = max(2, int(math.ceil(off_e / 1.5)))
                for k in range(n + 1):
                    off = off_e * k / n
                    zz = self._road_z(i, side, off)
                    p = P + L * (side * off)
                    out.append((p.x, p.y, zz - CLEAR_ROAD))
                w = self.sw[side][i]
                if w > 0:
                    m = max(1, int(math.ceil(w / 1.5)))
                    for k in range(1, m + 1):
                        dd = w * k / m
                        p = P + L * (side * (off_e + dd))
                        out.append((p.x, p.y, self.slope_z(i, side, dd) - CLEAR_SLOPE))
        # meio do passo entre amostras (curvas: a corda fica fora do ponto da amostra)
        for i in range(N - 1 + (1 if self.cyclic else 0)):
            j = (i + 1) % N
            for side in (1, -1):
                for off_f in (0.0, 0.5, 1.0):
                    oa = self.eo[side][i] * off_f
                    ob = self.eo[side][j] * off_f
                    pa = self.P[i] + self.L[i] * (side * oa)
                    pb = self.P[j] + self.L[j] * (side * ob)
                    za = self._road_z(i, side, oa)
                    zb = self._road_z(j, side, ob)
                    q = (pa + pb) * 0.5
                    out.append((q.x, q.y, min(za, zb) - CLEAR_ROAD))
        return out

    def _road_z(self, i, side, off):
        """Altura mais baixa da superfície da estrada no deslocamento `off` (>= 0) do lado: nos
        degraus (guia) vale a de baixo; seção MESH pela envoltória do layout."""
        best = None
        for be in self.edges.bands(i, side):
            if be.kind not in ROAD_KINDS:
                break
            lo, hi = be.off_in, be.off_out
            if lo - 1e-4 <= off <= hi + 1e-4:
                if be.kind == 'MESH' and be.section is not None:
                    zz = self.edges.surface_z(i, side, min(max(off, lo), hi))
                else:
                    t = 0.0 if hi - lo < 1e-6 else (off - lo) / (hi - lo)
                    zz = be.z_in + (be.z_out - be.z_in) * min(1.0, max(0.0, t))
                best = zz if best is None else min(best, zz)
        if best is None:
            return min(self.P[i].z, self.ez[side][i])
        return best

    def ground(self, x, y):
        """Altura da malha da grade em (x, y): os mesmos triângulos da malha (diagonal a -> a+nx+1)."""
        z, _ = self.lattice()
        c = self.cell
        fx, fy = (x - self.x0) / c, (y - self.y0) / c
        i = min(self.nx - 2, max(0, int(fx)))
        j = min(self.ny - 2, max(0, int(fy)))
        tx, ty = min(1.0, max(0.0, fx - i)), min(1.0, max(0.0, fy - j))
        n = self.nx
        z00, z10 = z[j * n + i], z[j * n + i + 1]
        z01, z11 = z[(j + 1) * n + i], z[(j + 1) * n + i + 1]
        if tx >= ty:   # triângulo (a, a+1, a+nx+1)
            return z00 + (z10 - z00) * tx + (z11 - z10) * ty
        return z00 + (z11 - z01) * tx + (z01 - z00) * ty


def get_field(scene, track_obj, frames, edges):
    """Campo de altura com cache por (traçado, frames, edges): terreno e decoração usam o mesmo."""
    key = (track_obj.name, id(frames), id(edges))
    f = _FIELD_CACHE.get(key)
    if f is None:
        _FIELD_CACHE.clear()
        f = TerrainField(scene, track_obj, frames, edges)
        _FIELD_CACHE[key] = f
    return f


# ---------------------------------------------------------------- textura de grama
def grass_material(name="RangeTrack_Grama"):
    """Material de grama com textura tileável gerada (128 px). Salva em //textures/ quando o .range
    tem pasta; senão empacota no arquivo. Sempre repinta a imagem (dado reaproveitado pelo nome)."""
    lado = 128
    img = bpy.data.images.get(name)
    if img is None or tuple(img.size) != (lado, lado):
        if img is not None:
            img.name = name + "_velho"
        img = bpy.data.images.new(name, lado, lado, alpha=False)
    px = [0.0] * (lado * lado * 4)
    for yy in range(lado):
        b = 2 * math.pi * yy / lado
        for xx in range(lado):
            a = 2 * math.pi * xx / lado
            # ruído periódico (tileável): amostra num toro
            q = Vector((math.cos(a) * 1.3, math.sin(a) * 1.3, math.cos(b) * 1.3 + math.sin(b) * 0.7))
            n1 = noise.noise(q * 2.0) * 0.5 + 0.5
            n2 = noise.noise(q * 9.0 + Vector((3, 1, 2))) * 0.5 + 0.5
            f = 0.75 + 0.35 * n1 + 0.15 * n2
            terra = smooth(0.62, 0.78, n1 * 0.7 + n2 * 0.3)
            k = (yy * lado + xx) * 4
            px[k] = (0.20 * (1 - terra) + 0.42 * terra) * f
            px[k + 1] = (0.42 * (1 - terra) + 0.36 * terra) * f
            px[k + 2] = (0.14 * (1 - terra) + 0.22 * terra) * f
            px[k + 3] = 1.0
    img.pixels = px
    _decor.store_image(img, name + ".png")
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
    mat.diffuse_color = (1, 1, 1)
    mat.specular_intensity = 0.05
    tex = bpy.data.textures.get(name)
    if tex is None or tex.type != 'IMAGE':
        tex = bpy.data.textures.new(name, 'IMAGE')
    tex.image = img
    slot = mat.texture_slots[0] if mat.texture_slots[0] else mat.texture_slots.add()
    slot.texture = tex
    slot.texture_coords = 'UV'
    return mat


# ---------------------------------------------------------------- malhas
def _mesh_world_uv(scene, track_obj, name, verts, faces, mat, smooth_shade=True):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.uv_textures.new("UVMap")
    lay = me.uv_layers[0].data
    loops = me.loops
    for li in range(len(loops)):
        co = verts[loops[li].vertex_index]
        lay[li].uv = (co[0] / UV_SCALE, co[1] / UV_SCALE)
    me.materials.append(mat)
    img = mat.texture_slots[0].texture.image if mat.texture_slots[0] else None
    if img is not None:
        for uvf in me.uv_textures[0].data:
            uvf.image = img
    if smooth_shade:
        for poly in me.polygons:
            poly.use_smooth = True
    me.validate()
    me.update(calc_edges=True)
    return _decor.make_object(scene, track_obj, name, me, physics=False)


def _build_grid(scene, track_obj, F, mat):
    z, hidden = F.lattice()
    nx, ny, c = F.nx, F.ny, F.cell
    objs = []
    base = track_obj.name
    for tj in range(0, ny - 1, TILE_CELLS):
        for ti in range(0, nx - 1, TILE_CELLS):
            i1, j1 = min(nx - 1, ti + TILE_CELLS), min(ny - 1, tj + TILE_CELLS)
            vmap, verts, faces = {}, [], []
            for j in range(tj, j1):
                for i in range(ti, i1):
                    a = j * nx + i
                    q = (a, a + 1, a + nx + 1, a + nx)
                    if hidden[q[0]] and hidden[q[1]] and hidden[q[2]] and hidden[q[3]]:
                        continue
                    # dois triângulos com a diagonal a -> a+nx+1 (a mesma do TerrainField.ground)
                    for tri in ((q[0], q[1], q[2]), (q[0], q[2], q[3])):
                        f = []
                        for k in tri:
                            v = vmap.get(k)
                            if v is None:
                                v = vmap[k] = len(verts)
                                ii, jj = k % nx, k // nx
                                verts.append((F.x0 + ii * c, F.y0 + jj * c, z[k]))
                            f.append(v)
                        faces.append(tuple(f))
            if faces:
                nm = "%s_Terrain_%d_%d" % (base, ti // TILE_CELLS, tj // TILE_CELLS)
                objs.append(_mesh_world_uv(scene, track_obj, nm, verts, faces, mat))
    return objs


def _build_strips(scene, track_obj, F, mat_by_side):
    """Talude (faixa SLOPE) e saia (lado sem talude) varridos da borda da estrada para fora."""
    N = F.N
    objs = []
    base = track_obj.name
    nseg = N if F.cyclic else N - 1
    blocks = {}
    for side in (1, -1):
        for i in range(nseg):
            j = (i + 1) % N
            blk = int(F.S[i] // STRIP_BLOCK)
            key = (blk, side if mat_by_side[1] is not mat_by_side[-1] else 0)
            g = blocks.setdefault(key, ([], []))
            verts, faces = g
            ring = []
            for k_ in (i, j):
                w = F.sw[side][k_]
                P, L = F.P[k_], F.L[k_]
                eo, ez = F.eo[side][k_], F.ez[side][k_]
                r = []
                if w > 0.05:
                    m = max(2, int(math.ceil(w / 3.0)))
                    for q in range(m + 1):
                        dd = w * q / m
                        p = P + L * (side * (eo + dd))
                        zz = F.slope_z(k_, side, dd)
                        # dobra no miolo de curva fechada: vértice caindo sobre a pista afunda
                        # (na borda, dd = 0, só quando o ponto cai dentro de outro trecho da pista)
                        de = F.edges.dist_to_edge(p.x, p.y)
                        if (de < 3.0) if dd > 0 else (de < -0.05):
                            zz -= 3.0
                        r.append((p.x, p.y, zz))
                else:
                    # saia: desce 1,5 m logo depois da borda (cobre a fresta até a grade)
                    for dd, dz in ((0.0, 0.0), (0.6, -1.5)):
                        p = P + L * (side * (eo + dd))
                        r.append((p.x, p.y, ez + dz))
                ring.append(r)
            ra, rb = ring
            if len(ra) != len(rb):          # muda o número de divisões: reamostra o menor
                n = max(len(ra), len(rb))
                ra, rb = _resample(ra, n), _resample(rb, n)
            b0 = len(verts)
            verts.extend(ra)
            verts.extend(rb)
            n = len(ra)
            for q in range(n - 1):
                a0, a1 = b0 + q, b0 + q + 1
                c0, c1 = b0 + n + q, b0 + n + q + 1
                # normal para cima: no lado esquerdo a lateral cresce para +lat
                if side > 0:
                    faces.append((a0, c0, c1, a1))
                else:
                    faces.append((a0, a1, c1, c0))
    for (blk, sk), (verts, faces) in sorted(blocks.items()):
        if not faces:
            continue
        verts, faces = _weld(verts, faces)
        side = sk if sk else 1
        nm = "%s_Slope_%02d" % (base, blk) if not sk else "%s_Slope_%s_%02d" % (base, "L" if sk > 0 else "R", blk)
        objs.append(_mesh_world_uv(scene, track_obj, nm, verts, faces, mat_by_side[side]))
    return objs


def _resample(r, n):
    if len(r) == n:
        return r
    out = []
    for q in range(n):
        t = q * (len(r) - 1) / float(n - 1)
        a = int(t)
        b = min(len(r) - 1, a + 1)
        f = t - a
        out.append(tuple(r[a][k] + (r[b][k] - r[a][k]) * f for k in range(3)))
    return out


def _weld(verts, faces):
    """Junta vértices iguais (anéis repetidos entre segmentos) para a malha ficar contínua."""
    idx, out, remap = {}, [], []
    for v in verts:
        key = (round(v[0], 4), round(v[1], 4), round(v[2], 4))
        k = idx.get(key)
        if k is None:
            k = idx[key] = len(out)
            out.append(v)
        remap.append(k)
    nf = []
    for f in faces:
        g = tuple(remap[k] for k in f)
        if len(set(g)) >= 3:
            nf.append(g)
    return out, nf


def _build_horizon(scene, track_obj, F):
    """Morros do horizonte: faixa contínua em volta (atlas de paleta, sem física)."""
    rnd = _decor.rng(track_obj, 9173)
    g = _decor.Geo()
    cx, cy = (F.x0 + F.x1) / 2, (F.y0 + F.y1) / 2
    R = math.hypot(F.x1 - F.x0, F.y1 - F.y0) * 0.5 + 90.0
    n = 120
    # altura de referência por direção: o fundo (IDW) na borda da grade naquela direção, suavizado
    ref = []
    for k in range(n):
        a = 2 * math.pi * k / n
        ex = min(F.x1, max(F.x0, cx + R * math.cos(a)))
        ey = min(F.y1, max(F.y0, cy + R * math.sin(a)))
        ref.append(F.base(ex, ey))
    ref = [(ref[k - 2] + ref[k - 1] * 2 + ref[k] * 3 + ref[(k + 1) % n] * 2 + ref[(k + 2) % n]) / 9.0
           for k in range(n)]
    baixo, alto = [], []
    for k in range(n):
        a = 2 * math.pi * k / n
        h = ref[k] + 40 + F.hill_h * 4.0 * (noise.noise(Vector((math.cos(a) * 2.5, math.sin(a) * 2.5, 0.5))) * 0.5 + 0.5) \
            + rnd.uniform(0, 35)
        baixo.append(Vector((cx + R * math.cos(a), cy + R * math.sin(a), ref[k] - 150)))
        alto.append(Vector((cx + (R + 120) * math.cos(a), cy + (R + 120) * math.sin(a), h)))
    for k in range(n):
        k2 = (k + 1) % n
        g.add([baixo[k], baixo[k2], alto[k2], alto[k]], [(0, 1, 2, 3)], "morro", [0, 0, 1, 1])
    return _decor.make_geo_object(scene, track_obj, track_obj.name + "_Horizon", g, _decor.palette_material())


def generate_terrain(scene, track_obj, frames, edges):
    """Gera talude/saia, a grade de terreno e o horizonte. Devolve os objetos criados (sem física).
    Com terrain_enabled desligado não gera nada."""
    st = track_obj.range_track
    if not getattr(st, "terrain_enabled", True):
        return []
    F = get_field(scene, track_obj, frames, edges)
    grass = grass_material()
    mats = {}
    for side in (1, -1):
        # talude com o material da faixa só se ele tiver textura; senão a grama (costura invisível)
        slope = next((first_band(edges, i, side, 'SLOPE') for i in range(F.N)
                      if first_band(edges, i, side, 'SLOPE') is not None), None)
        m = slope.material if slope is not None else None
        has_tex = m is not None and any(ts is not None and ts.texture is not None for ts in m.texture_slots)
        mats[side] = m if has_tex else grass
    objs = []
    objs += _build_strips(scene, track_obj, F, mats)
    objs += _build_grid(scene, track_obj, F, grass)
    if getattr(st, "horizon_enabled", True):
        objs.append(_build_horizon(scene, track_obj, F))
    return objs
