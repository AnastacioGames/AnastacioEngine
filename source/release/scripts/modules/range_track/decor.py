# Track Tool: decoração por regra (RangeTrackRule) e âncoras (RangeTrackAnchor).
#
# Contrato em docs/plano-track-tool.md ("Contrato entre módulos"):
#   generate_decor(scene, track_obj, frames, edges) -> [objetos]
#   update_anchors(scene, track_obj, frames, edges)
#   default_rules(track_obj, theme)  -> regras dos temas "bairro" e "serra" (equivalentes ao protótipo)
#
# Base: D:\ProjetoRolimaRacer\Tools\gerar_cenario_pista.py.
#
# Regras (campos de RangeTrackRule: kind, band, side, spacing, density, offset, source_group,
# source_scene, name_prefix, curve_min_deg, seed, enabled):
#   band     faixa (nome ou tipo) depois de cuja borda externa a prop vai; vazio = última faixa de
#            estrada do lado (calçada/borda). offset = metros além dessa borda.
#   side     LEFT / RIGHT / BOTH.  spacing = metros entre tentativas ao longo de s.
#   density  chance (0..1) de cada tentativa virar prop (TREES: multiplica a quantidade).
#   HOUSES   frente (-Y local) para a rua; em curva mais fechada que curve_min_deg só no lado de fora.
#            Usa range_buildings (atlas próprio, 1 material por bloco) quando o módulo importa; senão
#            a casa procedural da paleta. name_prefix aceita uma lista de estilos de
#            range_buildings.STYLES separada por vírgula (vazio = todos). Estilos de comércio têm mais
#            chance perto da largada/chegada. foundation cobre o declive; LOD1 a mais de 120 m da pista.
#   TREES    objetos de source_group, ou da cena source_scene com o prefixo name_prefix (padrão
#            "Kits" + "Arvore_tipo_"); espalhadas na área do terreno, a partir da faixa `band`.
#            Juntadas por bloco de 200 m preservando materiais, UV e imagem por face.
#   POLES    postes a cada `spacing` com fios entre postes vizinhos.
#   SIGNS    placas de chevron no lado de fora quando a curva (giro em 24 m de pista) passa de
#            curve_min_deg; depois de uma curva pula `spacing` metros.
#   KERBS    no-op: a zebra é da estrada (RangeTrackBand.kerb_on_curves, sweep.py).
#   PEOPLE   público perto da largada e da chegada + os portais de largada/chegada.
#   CUSTOM   objetos de source_group / source_scene + name_prefix a cada `spacing` com `density`.
# Determinístico por seed. Nada invade a pista: cada prop confere edges.dist_to_edge com folga.
# Geometria procedural num atlas de paleta (1 material), juntada por bloco de 200 m, sem física.
import bisect
import math
import os
import random

import bpy
from mathutils import Matrix, Vector

CHUNK = 200.0

# ---------------------------------------------------------------- paleta (atlas 4x4 com degradê)
PALETA = [
    ("concreto", (0.62, 0.61, 0.58)), ("branco", (0.92, 0.91, 0.88)),
    ("vermelho", (0.78, 0.12, 0.10)), ("telha", (0.72, 0.33, 0.18)),
    ("tijolo", (0.66, 0.36, 0.25)), ("amarelo", (0.95, 0.76, 0.22)),
    ("azul", (0.30, 0.52, 0.78)), ("verde_casa", (0.47, 0.70, 0.52)),
    ("rosa", (0.88, 0.58, 0.62)), ("tronco", (0.36, 0.24, 0.15)),
    ("folha", (0.24, 0.50, 0.20)), ("folha2", (0.16, 0.38, 0.17)),
    ("preto", (0.08, 0.08, 0.09)), ("madeira", (0.55, 0.38, 0.22)),
    ("morro", (0.50, 0.62, 0.66)), ("vidro", (0.20, 0.27, 0.33)),
]
COR = {n: i for i, (n, _) in enumerate(PALETA)}
CEL, NCOL = 16, 4
PALETTE_NAME = "RangeTrack_Paleta"

# relatório da última geração (testes e painel): contagens e props colocadas
last_report = {}


def store_image(img, filename):
    """Salva a imagem gerada em //textures/ quando o .range tem pasta; senão empacota no arquivo."""
    if bpy.data.filepath and not img.packed_file:
        rel = "//textures/" + filename
        path = bpy.path.abspath(rel)
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            img.filepath_raw = path
            img.file_format = 'PNG'
            img.save()
            img.filepath = rel
            return
        except Exception as ex:          # pasta sem permissão etc.: cai para o pack
            print("range_track: não salvou %s (%s); empacotando" % (rel, ex))
    img.pack(as_png=True)


def palette_material():
    """Material único com o atlas de paleta. Repinta a imagem sempre (cores podem ter mudado)."""
    lado = CEL * NCOL
    img = bpy.data.images.get(PALETTE_NAME)
    if img is None or tuple(img.size) != (lado, lado):
        if img is not None:
            img.name = PALETTE_NAME + "_velho"
        img = bpy.data.images.new(PALETTE_NAME, lado, lado, alpha=False)
    px = [0.0] * (lado * lado * 4)
    for i, (_, c) in enumerate(PALETA):
        cx, cy = (i % NCOL) * CEL, (i // NCOL) * CEL
        for yy in range(CEL):
            f = 0.72 + 0.28 * yy / float(CEL - 1)   # degradê: base mais escura
            for xx in range(CEL):
                k = ((cy + yy) * lado + cx + xx) * 4
                px[k:k + 4] = [c[0] * f, c[1] * f, c[2] * f, 1.0]
    img.pixels = px
    store_image(img, PALETTE_NAME + ".png")
    mat = bpy.data.materials.get(PALETTE_NAME)
    if mat is None:
        mat = bpy.data.materials.new(PALETTE_NAME)
    mat.diffuse_color = (1, 1, 1)
    mat.specular_intensity = 0.1
    tex = bpy.data.textures.get(PALETTE_NAME)
    if tex is None or tex.type != 'IMAGE':
        tex = bpy.data.textures.new(PALETTE_NAME, 'IMAGE')
    tex.image = img
    tex.use_interpolation = False
    tex.use_mipmap = False
    tex.filter_type = 'BOX'
    slot = mat.texture_slots[0] if mat.texture_slots[0] else mat.texture_slots.add()
    slot.texture = tex
    slot.texture_coords = 'UV'
    return mat


# ---------------------------------------------------------------- geometria (listas, sem bmesh)
class Geo:
    """Acumula vértices/faces com cor por face (índice da paleta) e altura relativa por vértice."""

    def __init__(self):
        self.v, self.t, self.f, self.c = [], [], [], []

    def add(self, verts, faces, cor, t=None):
        b = len(self.v)
        self.v.extend(verts)
        if t is None:
            zs = [p.z for p in verts]
            z0, z1 = min(zs), max(zs)
            t = [(p.z - z0) / (z1 - z0) if z1 > z0 else 0.5 for p in verts]
        self.t.extend(t)
        for fc in faces:
            self.f.append(tuple(b + i for i in fc))
            self.c.append(COR[cor] if isinstance(cor, str) else cor)

    def merge(self, other, xf):
        """xf: função Vector -> Vector (posição no mundo)."""
        b = len(self.v)
        self.v.extend(xf(p) for p in other.v)
        self.t.extend(other.t)
        self.f.extend(tuple(b + i for i in fc) for fc in other.f)
        self.c.extend(other.c)


def caixa(g, c, s, cor):
    x, y, z = c
    hx, hy, hz = s[0] / 2, s[1] / 2, s[2] / 2
    vs = [Vector((x + a * hx, y + b * hy, z + d * hz)) for d in (-1, 1) for b in (-1, 1) for a in (-1, 1)]
    fs = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]
    g.add(vs, fs, cor)


def telhado(g, c, w, d, h, cor):
    """Telhado de duas águas: cumeeira no eixo X."""
    x, y, z = c
    vs = [Vector(p) for p in ((x - w / 2, y - d / 2, z), (x + w / 2, y - d / 2, z), (x + w / 2, y + d / 2, z),
                              (x - w / 2, y + d / 2, z), (x - w / 2, y, z + h), (x + w / 2, y, z + h))]
    g.add(vs, [(0, 1, 5, 4), (2, 3, 4, 5), (0, 4, 3), (1, 2, 5), (0, 3, 2, 1)], cor)


def cilindro(g, c, r, h, cor, n=6, r2=None):
    x, y, z = c
    r2 = r if r2 is None else r2
    vs = [Vector((x + r * math.cos(2 * math.pi * k / n), y + r * math.sin(2 * math.pi * k / n), z)) for k in range(n)]
    vs += [Vector((x + r2 * math.cos(2 * math.pi * k / n), y + r2 * math.sin(2 * math.pi * k / n), z + h)) for k in range(n)]
    fs = [(k, (k + 1) % n, n + (k + 1) % n, n + k) for k in range(n)]
    fs.append(tuple(range(n - 1, -1, -1)))
    fs.append(tuple(range(n, 2 * n)))
    g.add(vs, fs, cor)


def cone(g, c, r, h, cor, n=7):
    x, y, z = c
    vs = [Vector((x + r * math.cos(2 * math.pi * k / n), y + r * math.sin(2 * math.pi * k / n), z)) for k in range(n)]
    vs.append(Vector((x, y, z + h)))
    fs = [(k, (k + 1) % n, n) for k in range(n)] + [tuple(range(n - 1, -1, -1))]
    g.add(vs, fs, cor)


def copa(g, c, r, h, cor):
    """Copa low poly: bipirâmide hexagonal achatada."""
    x, y, z = c
    n = 6
    meio = [Vector((x + r * math.cos(2 * math.pi * k / n + 0.3), y + r * math.sin(2 * math.pi * k / n + 0.3),
                    z + h * 0.45)) for k in range(n)]
    vs = meio + [Vector((x, y, z)), Vector((x, y, z + h))]
    fs = [(k, n + 1, (k + 1) % n) for k in range(n)] + [((k + 1) % n, n, k) for k in range(n)]
    g.add(vs, fs, cor)


# ---------------------------------------------------------------- protótipos (origem no chão, frente -Y)
def proto_casa(rnd, estilo, cor):
    g = Geo()
    w, d = rnd.uniform(6, 9), rnd.uniform(6, 8)
    andares = 1 if estilo < 2 else 2
    h = 3.0 * andares
    caixa(g, (0, 0, h / 2 - 2.0), (w, d, h + 4.0), cor)          # alicerce enterrado 4 m
    if estilo % 2 == 0:
        telhado(g, (0, 0, h), w + 0.6, d + 0.8, 1.8, "telha")
    else:
        caixa(g, (0, 0, h + 0.15), (w + 0.2, d + 0.2, 0.3), "concreto")   # laje
        cilindro(g, (w * 0.25, d * 0.2, h + 0.3), 0.7, 1.1, "azul", 8)    # caixa d'água
    for a in range(andares):
        zj = 1.4 + 3.0 * a
        for xj in (-w * 0.28, w * 0.28):
            caixa(g, (xj, -d / 2 - 0.03, zj), (1.2, 0.08, 1.1), "vidro")
    caixa(g, (0, -d / 2 - 0.03, 1.05), (1.0, 0.08, 2.1), "madeira")
    if estilo != 3:
        caixa(g, (0, -d / 2 - 2.0, 0.6), (w + 1.0, 0.25, 1.2), "branco")   # muro da frente
    g.body = (w, d)                                          # corpo da casa (para o alicerce extra)
    g.size = (w + 1.0, d + (4.0 if estilo != 3 else 0.0))   # pegada (o muro fica 2 m à frente)
    g.front = d / 2 + (2.0 if estilo != 3 else 0.0)          # da origem até a frente
    return g


def proto_arvore(rnd, tipo):
    g = Geo()
    if tipo == 0:
        hs = rnd.uniform(2.0, 3.0)
        cilindro(g, (0, 0, -0.5), 0.25, hs + 0.6, "tronco", 5, 0.18)
        copa(g, (0, 0, hs - 0.4), rnd.uniform(2.2, 3.2), rnd.uniform(3.5, 5.0), "folha")
    elif tipo == 1:
        hs = rnd.uniform(1.0, 1.6)
        cilindro(g, (0, 0, -0.5), 0.22, hs + 0.6, "tronco", 5)
        cone(g, (0, 0, hs), 2.4, 4.0, "folha2")
        cone(g, (0, 0, hs + 2.4), 1.8, 3.6, "folha2")
    else:
        copa(g, (0, 0, -0.3), rnd.uniform(1.0, 1.6), rnd.uniform(1.2, 1.8), "folha")
    return g


def proto_poste():
    g = Geo()
    cilindro(g, (0, 0, -0.3), 0.14, 8.3, "concreto", 5, 0.1)
    caixa(g, (0, 0, 7.4), (0.12, 1.6, 0.12), "madeira")
    caixa(g, (0, -0.9, 7.6), (0.15, 0.6, 0.12), "preto")      # luminária (para o lado da rua)
    return g


def proto_placa():
    g = Geo()
    caixa(g, (0, 0, 0.6), (0.1, 0.1, 1.4), "concreto")
    caixa(g, (0, -0.06, 1.55), (1.0, 0.06, 0.8), "amarelo")
    caixa(g, (-0.12, -0.1, 1.55), (0.14, 0.02, 0.55), "preto")   # chevron
    caixa(g, (0.14, -0.1, 1.55), (0.14, 0.02, 0.55), "preto")
    return g


def proto_pessoa(rnd):
    g = Geo()
    cor = rnd.choice(["vermelho", "azul", "amarelo", "verde_casa", "rosa", "branco"])
    caixa(g, (0, 0, 0.45), (0.35, 0.25, 0.9), "preto")
    caixa(g, (0, 0, 1.25), (0.45, 0.28, 0.7), cor)
    caixa(g, (0, 0, 1.75), (0.24, 0.24, 0.26), "tijolo")
    return g


# ---------------------------------------------------------------- objetos
def make_object(scene, track_obj, name, me, physics=False):
    o = bpy.data.objects.new(name, me)
    scene.objects.link(o)
    o.layers = list(track_obj.layers)
    if physics:
        o.game.physics_type = 'STATIC'
        o.game.use_collision_bounds = True
        o.game.collision_bounds_type = 'TRIANGLE_MESH'
    else:
        o.game.physics_type = 'NO_COLLISION'
    if hasattr(o, "range_track_owner"):
        o.range_track_owner = track_obj.name
    return o


def make_geo_object(scene, track_obj, name, g, mat):
    me = bpy.data.meshes.new(name)
    me.from_pydata(g.v, [], g.f)
    me.uv_textures.new("UVMap")
    lay = me.uv_layers[0].data
    lado = CEL * NCOL
    loops = me.loops
    for poly, c in zip(me.polygons, g.c):
        u0, v0 = (c % NCOL) * CEL, (c // NCOL) * CEL
        for li in poly.loop_indices:
            t = g.t[loops[li].vertex_index]
            lay[li].uv = ((u0 + CEL * 0.5) / lado, (v0 + 1.5 + t * (CEL - 3)) / lado)
    me.materials.append(mat)
    img = mat.texture_slots[0].texture.image
    for uvf in me.uv_textures[0].data:
        uvf.image = img
    me.validate()
    me.update(calc_edges=True)
    return make_object(scene, track_obj, name, me)


def make_instances_object(scene, track_obj, name, insts):
    """Junta cópias de objetos-fonte numa malha só (materiais, UV e imagem por face preservados).
    insts: [(obj_fonte, base Vector, rot_z, escala)]. A rotação/escala do objeto-fonte é mantida."""
    vs, fs, fmat, fuv, fimg, mats = [], [], [], [], [], []
    for o, base, rot, esc in insts:
        me = o.data
        r3 = o.matrix_world.to_3x3()
        c, s = math.cos(rot), math.sin(rot)
        mi = {}
        for k_, m in enumerate(me.materials):
            if m not in mats:
                mats.append(m)
            mi[k_] = mats.index(m)
        b = len(vs)
        for v in me.vertices:
            p = r3 * v.co
            vs.append(base + Vector(((p.x * c - p.y * s) * esc, (p.x * s + p.y * c) * esc, p.z * esc)))
        uvl = me.uv_layers[0].data if me.uv_layers else None
        tf = me.uv_textures[0].data if me.uv_textures else None
        for poly in me.polygons:
            fs.append(tuple(b + me.loops[li].vertex_index for li in poly.loop_indices))
            fmat.append(mi.get(poly.material_index, 0))
            fuv.append([tuple(uvl[li].uv) for li in poly.loop_indices] if uvl else None)
            fimg.append(tf[poly.index].image if tf else None)
    me = bpy.data.meshes.new(name)
    me.from_pydata(vs, [], fs)
    for m in mats:
        me.materials.append(m)
    me.uv_textures.new("UVMap")
    lay = me.uv_layers[0].data
    tex = me.uv_textures[0].data
    for poly, mi_, uvp, img in zip(me.polygons, fmat, fuv, fimg):
        poly.material_index = mi_
        if uvp:
            for li, uv in zip(poly.loop_indices, uvp):
                lay[li].uv = uv
        if img:
            tex[poly.index].image = img
    me.validate()
    me.update(calc_edges=True)
    return make_object(scene, track_obj, name, me)


def make_buildings_object(scene, track_obj, name, rb, items):
    """Junta casas do range_buildings (atlas próprio) numa malha: items = [(built, Matrix4)]."""
    data = rb.merge(items)
    verts, faces, uvs = data["verts"], data["faces"], data.get("uvs")
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    me.uv_textures.new("UVMap")
    lay = me.uv_layers[0].data
    if uvs:
        if len(uvs) == len(faces) and len(uvs) and isinstance(uvs[0][0], (list, tuple)):
            # UV por canto de face: uma lista por face
            for poly, fu in zip(me.polygons, uvs):
                for li, uv in zip(poly.loop_indices, fu):
                    lay[li].uv = tuple(uv)
        else:
            for li, uv in enumerate(uvs):
                if li < len(lay):
                    lay[li].uv = tuple(uv)
    mat = rb.atlas_material()
    me.materials.append(mat)
    ts = mat.texture_slots[0] if len(mat.texture_slots) else None
    img = ts.texture.image if (ts and ts.texture and getattr(ts.texture, "image", None)) else None
    if img is not None:
        for uvf in me.uv_textures[0].data:
            uvf.image = img
    me.validate()
    me.update(calc_edges=True)
    return make_object(scene, track_obj, name, me)


# ---------------------------------------------------------------- utilidades
_KIND_SALT = {'HOUSES': 11, 'TREES': 23, 'POLES': 37, 'SIGNS': 41, 'KERBS': 53, 'PEOPLE': 67, 'CUSTOM': 79}


def rng(track_obj, salt):
    return random.Random(salt * 1000003 + sum(ord(c) * (k + 1) for k, c in enumerate(track_obj.name)))


def _rule_rng(rule, index):
    return random.Random(int(rule.seed) * 1000003 + _KIND_SALT.get(rule.kind, 97) * 7919 + index * 104729)


def _sides(rule_side):
    return {'LEFT': (1,), 'RIGHT': (-1,)}.get(rule_side, (1, -1))


def _buildings():
    """range_buildings (casas otimizadas, outro módulo). Import tolerante: None se faltar."""
    try:
        import range_buildings as rb
    except Exception as ex:
        print("range_track: range_buildings indisponível (%s); casas procedurais" % ex)
        return None
    if all(hasattr(rb, a) for a in ("build", "merge", "atlas_material", "STYLES")):
        return rb
    return None


_COMMERCE_WORDS = ("comerc", "loja", "bar", "padaria", "mercad", "venda", "boteco", "oficina", "shop",
                   "store", "posto", "farmac", "lanchon")


def _source_objects(rule, default_scene="", default_prefix=""):
    """Objetos-fonte (só MESH) da regra: source_group, ou cena + prefixo."""
    objs = []
    if rule.source_group:
        grp = bpy.data.groups.get(rule.source_group)
        if grp is not None:
            objs = [o for o in grp.objects if o.type == 'MESH']
    else:
        sc_name = rule.source_scene or default_scene
        prefix = rule.name_prefix or default_prefix
        if sc_name:
            sc = bpy.data.scenes.get(sc_name)
            pool = sc.objects if sc is not None else []
        else:
            pool = bpy.data.objects
        if prefix:
            objs = [o for o in pool if o.type == 'MESH' and o.name.startswith(prefix)]
    return sorted(objs, key=lambda o: o.name)


class _Occupancy:
    """Hash espacial de círculos ocupados (casas, postes...) para não sobrepor props."""

    def __init__(self, cell=20.0):
        self.cell = cell
        self.h = {}

    def free(self, x, y, r):
        c = self.cell
        ci, cj = int(math.floor(x / c)), int(math.floor(y / c))
        for i in (ci - 1, ci, ci + 1):
            for j in (cj - 1, cj, cj + 1):
                for (px, py, pr) in self.h.get((i, j), ()):
                    if (px - x) ** 2 + (py - y) ** 2 < (pr + r) ** 2:
                        return False
        return True

    def add(self, x, y, r):
        key = (int(math.floor(x / self.cell)), int(math.floor(y / self.cell)))
        self.h.setdefault(key, []).append((x, y, r))


class _Ctx:
    def __init__(self, scene, track_obj, frames, edges):
        from . import terrain
        self.terrain = terrain
        self.scene, self.track, self.frames, self.edges = scene, track_obj, frames, edges
        self.settings = track_obj.range_track
        self.field = terrain.get_field(scene, track_obj, frames, edges)
        F = self.field
        self.profile = F.profile
        self.N, self.P, self.T, self.L, self.S = F.N, F.P, F.T, F.L, F.S
        self.length, self.cyclic = F.length, F.cyclic
        self.blocks = {}          # paleta: chave -> Geo
        self.houses = {}          # range_buildings: chave -> [(built, Matrix)]
        self.inst = {}            # (prefixo, chave) -> [(obj, base, rot, esc)]
        self.occ = _Occupancy()
        self.placed = []          # (kind, x, y, folga, dist_to_edge)
        self.counts = {}

    # --- traçado
    def index_at(self, s):
        if self.cyclic and self.length > 0:
            s %= self.length
        i = bisect.bisect_left(self.S, s)
        if i <= 0:
            return 0
        if i >= self.N:
            return self.N - 1
        return i if self.S[i] - s < s - self.S[i - 1] else i - 1

    def turn(self, i):
        """frames.turn_deg: giro do rumo (graus, + = esquerda) em 24 m de pista (janela de +-12 m)."""
        return self.frames.turn_deg[i]

    def edge(self, i, side, band=""):
        """(off, z) da borda externa da faixa `band` (vazio = última faixa de estrada)."""
        if band:
            try:
                r = self.edges.band(i, side, band)
            except Exception:
                r = None
            if r is not None:
                return r[1], r[3]
        off, z, _ = self.terrain.road_edge(self.edges, i, side)
        return off, z

    def out(self, i, side, extra, band=""):
        off, z = self.edge(i, side, band)
        return self.P[i] + self.L[i] * (side * (off + extra)), z

    def facing_road(self, i, side):
        """Rotação Z para a frente (-Y local) olhar para a pista."""
        t = self.T[i]
        return math.atan2(t.y, t.x) + (0.0 if side > 0 else math.pi)

    def near_other(self, pos, i, radius, window=60.0):
        """Outro trecho da pista (longe em s) a menos de `radius` metros."""
        for _, j, _ in self.field.kd.find_range(Vector((pos.x, pos.y, 0.0)), radius):
            ds = abs(self.S[j] - self.S[i])
            if self.cyclic:
                ds = min(ds, self.length - ds)
            if ds > window:
                return True
        return False

    def dist_edge(self, x, y):
        return self.edges.dist_to_edge(x, y)

    def ground(self, x, y):
        return self.field.ground(x, y)

    # --- colocação
    def bkey(self, x, y):
        return int(math.floor(x / CHUNK)), int(math.floor(y / CHUNK))

    def put(self, kind, proto, pos, rot, z, folga, scale=1.0):
        de = self.dist_edge(pos.x, pos.y)
        if de < folga:
            return False
        c, s = math.cos(rot), math.sin(rot)
        base = Vector((pos.x, pos.y, z))
        g = self.blocks.setdefault(self.bkey(pos.x, pos.y), Geo())
        g.merge(proto, lambda v: base + Vector(((v.x * c - v.y * s) * scale, (v.x * s + v.y * c) * scale,
                                                v.z * scale)))
        self.placed.append((kind, pos.x, pos.y, folga, de))
        self.counts[kind] = self.counts.get(kind, 0) + 1
        return True

    def merge_at(self, geo, pos, rot, z):
        """Junta geometria extra (sem checagem; ex.: alicerce) no bloco da posição."""
        c, s = math.cos(rot), math.sin(rot)
        base = Vector((pos.x, pos.y, z))
        g = self.blocks.setdefault(self.bkey(pos.x, pos.y), Geo())
        g.merge(geo, lambda v: base + Vector((v.x * c - v.y * s, v.x * s + v.y * c, v.z)))

    def put_inst(self, kind, prefix, obj, pos, rot, z, folga, scale=1.0):
        de = self.dist_edge(pos.x, pos.y)
        if de < folga:
            return False
        self.inst.setdefault((prefix, self.bkey(pos.x, pos.y)), []).append(
            (obj, Vector((pos.x, pos.y, z)), rot, scale))
        self.placed.append((kind, pos.x, pos.y, folga, de))
        self.counts[kind] = self.counts.get(kind, 0) + 1
        return True

    def footprint_clear(self, pos, rot, w, d, front, folga):
        """Cantos da pegada (frente a `front` m da origem, para -Y local) longe da pista."""
        c, s = math.cos(rot), math.sin(rot)
        for lx, ly in ((-w / 2, -front), (w / 2, -front), (-w / 2, d - front), (w / 2, d - front)):
            x = pos.x + lx * c - ly * s
            y = pos.y + lx * s + ly * c
            if self.dist_edge(x, y) < folga:
                return False
        return True

    def corners_ground(self, pos, rot, w, d, front):
        c, s = math.cos(rot), math.sin(rot)
        zs = []
        for lx, ly in ((-w / 2, -front), (w / 2, -front), (-w / 2, d - front), (w / 2, d - front), (0, 0)):
            zs.append(self.ground(pos.x + lx * c - ly * s, pos.y + lx * s + ly * c))
        return min(zs), max(zs)


# ---------------------------------------------------------------- regras
def _rule_houses(ctx, rule, idx):
    rnd = _rule_rng(rule, idx)
    rb = _buildings()
    styles = []
    if rb is not None:
        all_styles = list(rb.STYLES)
        want = [x.strip() for x in (rule.name_prefix or "").split(",") if x.strip()]
        styles = [x for x in all_styles if x in want] if want else all_styles
        if not styles:
            styles = all_styles
        commerce = [x for x in styles if any(w in str(x).lower() for w in _COMMERCE_WORDS)]
    cores = ["branco", "amarelo", "azul", "verde_casa", "rosa", "tijolo", "concreto"]
    protos = [proto_casa(rnd, e, rnd.choice(cores)) for e in range(4) for _ in range(3)]
    spacing = max(4.0, rule.spacing or 12.0)
    dens = rule.density if rule.density > 0 else 0.75
    offset = rule.offset if rule.offset > 0 else 3.5
    curve_min = rule.curve_min_deg or 20.0
    s = 16.0
    end = ctx.length - 16.0
    while s < end:
        i = ctx.index_at(s)
        turn = ctx.turn(i)
        for side in _sides(rule.side):
            if rnd.random() > dens:
                continue
            if abs(turn) > curve_min and side * turn > 0:     # lado de dentro da curva fechada: aberto
                continue
            rot = ctx.facing_road(i, side)
            gap = offset + rnd.uniform(0.0, 2.0)
            off, ze = ctx.edge(i, side, rule.band)
            if rb is not None:
                near_start = ctx.S[i] < 150.0 or ctx.S[i] > ctx.length - 150.0
                pool = commerce if (commerce and near_start and rnd.random() < 0.7) else styles
                style = rnd.choice(pool)
                hseed = rnd.randint(0, 1 << 30)
                try:
                    probe = rb.build(style, hseed)
                    w, d = probe["size"][0], probe["size"][1]
                except Exception as ex:
                    print("range_track: range_buildings.build falhou (%s); casas procedurais" % ex)
                    rb = None
                    continue
                front = d / 2.0
            else:
                proto = rnd.choice(protos)
                w, d = proto.size
                front = proto.front
            dist_center = off + gap + front
            pos = ctx.P[i] + ctx.L[i] * (side * dist_center)
            if ctx.near_other(pos, i, 20.0 + d / 2):
                continue
            r = math.hypot(w, d) * 0.5
            if not ctx.occ.free(pos.x, pos.y, r * 0.85):
                continue
            if not ctx.footprint_clear(pos, rot, w, d, front, 0.8):
                continue
            if ctx.dist_edge(pos.x, pos.y) < 2.0 + front:
                continue
            zmin, zmax = ctx.corners_ground(pos, rot, w, d, front)
            z = min(zmax, ze + 1.0)
            if rb is not None:
                found = max(0.0, z - zmin) + 0.4
                lod = 1 if dist_center > 120.0 else 0
                try:
                    built = rb.build(style, hseed, lod=lod, foundation=found)
                except TypeError:
                    built = rb.build(style, hseed)
                mtx = Matrix.Translation(Vector((pos.x, pos.y, z))) * Matrix.Rotation(rot, 4, 'Z')
                ctx.houses.setdefault(ctx.bkey(pos.x, pos.y), []).append((built, mtx))
                de = ctx.dist_edge(pos.x, pos.y)
                ctx.placed.append(('HOUSES', pos.x, pos.y, 2.0 + front, de))
                ctx.counts['HOUSES'] = ctx.counts.get('HOUSES', 0) + 1
            else:
                if not ctx.put('HOUSES', proto, pos, rot, z, front):
                    continue
                if z - zmin > 3.5:
                    # chão cai mais que o alicerce de 4 m do protótipo: alicerce até o chão
                    fund = Geo()
                    bw, bd = proto.body
                    depth = z - zmin + 0.5
                    caixa(fund, (0, 0, -depth / 2.0), (bw * 0.98, bd * 0.98, depth), "tijolo")
                    ctx.merge_at(fund, pos, rot, z)
            ctx.occ.add(pos.x, pos.y, r)
        s += spacing * rnd.uniform(0.85, 1.2)


def _rule_poles(ctx, rule, idx):
    rnd = _rule_rng(rule, idx)
    poste = proto_poste()
    spacing = max(8.0, rule.spacing or 36.0)
    offset = rule.offset if rule.offset > 0 else 2.2
    dens = rule.density if rule.density > 0 else 1.0
    for side in _sides(rule.side or 'LEFT'):
        ultimo = None
        s = 12.0
        while s < ctx.length - 12.0:
            i = ctx.index_at(s)
            s += spacing
            if rnd.random() > dens:
                ultimo = None
                continue
            pos, ze = ctx.out(i, side, offset, rule.band)
            rot = ctx.facing_road(i, side)
            z = min(ze - 0.4, ctx.ground(pos.x, pos.y))
            if not ctx.occ.free(pos.x, pos.y, 0.6) or not ctx.put('POLES', poste, pos, rot, z, 0.9):
                ultimo = None
                continue
            ctx.occ.add(pos.x, pos.y, 0.6)
            topo = Vector((pos.x, pos.y, z + 7.35))
            if ultimo is not None and (topo - ultimo).length < spacing * 1.7:
                g = ctx.blocks.setdefault(ctx.bkey(topo.x, topo.y), Geo())
                d = topo - ultimo
                lat = Vector((-d.y, d.x, 0)).normalized() * 0.03
                for off in (-0.5, 0.5):
                    o = ctx.L[i] * off
                    meio = (topo + ultimo) / 2 + o + Vector((0, 0, -0.6))
                    a, b = ultimo + o, topo + o
                    g.add([a - lat, meio - lat, meio + lat, a + lat], [(0, 1, 2, 3)], "preto", [0.5] * 4)
                    g.add([meio - lat, b - lat, b + lat, meio + lat], [(0, 1, 2, 3)], "preto", [0.5] * 4)
            ultimo = topo


def _rule_signs(ctx, rule, idx):
    placa = proto_placa()
    curve_min = rule.curve_min_deg or 17.0
    offset = rule.offset if rule.offset > 0 else 1.3
    skip = max(10.0, rule.spacing or 50.0)
    s = 20.0
    while s < ctx.length - 20.0:
        i = ctx.index_at(s)
        turn = ctx.turn(i)
        if abs(turn) > curve_min:
            side = -1 if turn > 0 else 1                      # lado de fora da curva
            if side in _sides(rule.side):
                for ds in (-8.0, 0.0, 8.0):
                    j = ctx.index_at(s + ds)
                    pos, ze = ctx.out(j, side, offset, rule.band)
                    t = ctx.T[j]
                    rot = math.atan2(t.y, t.x) - math.pi / 2 + side * 0.35   # de frente para quem vem
                    z = min(ze - 0.4, ctx.ground(pos.x, pos.y))
                    ctx.put('SIGNS', placa, pos, rot, z, 0.9)
            s += skip
        else:
            s += 2.0


def _rule_people(ctx, rule, idx):
    rnd = _rule_rng(rule, idx)
    pessoas = [proto_pessoa(rnd) for _ in range(6)]
    step = max(0.8, rule.spacing or 2.0)
    dens = rule.density if rule.density > 0 else 0.55
    offset = rule.offset if rule.offset > 0 else 1.1
    L = ctx.length
    faixas = [(8.0, 56.0)] if ctx.cyclic else [(8.0, 56.0), (L - 56.0, L - 8.0)]
    for a, b in faixas:
        s = a
        while s <= b:
            i = ctx.index_at(s)
            for side in _sides(rule.side):
                if rnd.random() < dens:
                    pos, ze = ctx.out(i, side, offset + rnd.uniform(0.0, 2.5), rule.band)
                    pos = pos + ctx.T[i] * rnd.uniform(-0.8, 0.8)
                    rot = ctx.facing_road(i, side) + rnd.uniform(-0.4, 0.4)
                    if ctx.occ.free(pos.x, pos.y, 0.3):
                        z = max(ctx.ground(pos.x, pos.y), ze - 0.6)
                        if ctx.put('PEOPLE', rnd.choice(pessoas), pos, rot, z, 0.9):
                            ctx.occ.add(pos.x, pos.y, 0.3)
            s += step
    portals = [("Largada", 8.0)] if ctx.cyclic else [("Largada", 8.0), ("Chegada", L - 10.0)]
    for nome, s in portals:
        _portal(ctx, nome, ctx.index_at(s))


def _portal(ctx, nome, i):
    g = Geo()
    t = ctx.T[i]
    rot = math.atan2(t.y, t.x)
    (ol, zl), (orr, zr) = ctx.edge(i, 1), ctx.edge(i, -1)
    zt = max(zl, zr)
    meia = max(ol, orr) + 1.3
    for side, zb in ((1, zl), (-1, zr)):
        # pilar fora da pista: empurra para fora se a folga não bastar
        for extra in (0.0, 1.0, 2.0, 4.0):
            p = ctx.P[i] + ctx.L[i] * (side * (meia + extra))
            if ctx.dist_edge(p.x, p.y) >= 0.9:
                break
        meia = max(meia, (p - ctx.P[i]).length)
    larg = 2 * meia + 0.5
    for side, zb in ((1, zl), (-1, zr)):
        zg = min(zb, ctx.ground(*(ctx.P[i] + ctx.L[i] * (side * meia)).xy))
        hb = zt - zg + 7.0
        caixa(g, (0, side * meia, zg - zt + hb / 2 - 0.6), (0.5, 0.5, hb), "concreto")
        p = ctx.P[i] + ctx.L[i] * (side * meia)
        ctx.placed.append(('PORTAL', p.x, p.y, 0.9, ctx.dist_edge(p.x, p.y)))
    nq = max(1, int(larg))
    caixa(g, (0, 0, 5.6), (0.6, larg, 1.0), "preto")
    for q in range(nq):
        yq = -larg / 2 + 0.5 + q * larg / nq
        caixa(g, (0, yq, 5.85), (0.65, larg / nq, 0.5), "branco" if q % 2 == 0 else "preto")
        caixa(g, (0, yq, 5.35), (0.65, larg / nq, 0.5), "preto" if q % 2 == 0 else "branco")
    caixa(g, (0, 0, 6.6), (0.4, larg * 0.5, 0.9), "vermelho" if nome == "Largada" else "amarelo")
    base = Vector((ctx.P[i].x, ctx.P[i].y, zt))
    c, s = math.cos(rot), math.sin(rot)
    h = Geo()
    h.merge(g, lambda v: base + Vector((v.x * c - v.y * s, v.x * s + v.y * c, v.z)))
    ctx.portals = getattr(ctx, "portals", []) + [(nome, h)]
    ctx.counts['PORTALS'] = ctx.counts.get('PORTALS', 0) + 1


def _rule_trees(ctx, rule, idx):
    rnd = _rule_rng(rule, idx)
    fontes = _source_objects(rule, "Kits", "Arvore_tipo_")
    procs = [proto_arvore(rnd, t % 3) for t in range(9)] if not fontes else []
    F = ctx.field
    spacing = max(5.0, rule.spacing or 37.0)
    dens = rule.density if rule.density > 0 else 1.0
    folga = max(4.0, rule.offset or 4.0)
    x0, x1, y0, y1 = F.x0 + 20, F.x1 - 20, F.y0 + 20, F.y1 - 20
    alvo = int((x1 - x0) * (y1 - y0) / (spacing * spacing) * dens)
    sides = _sides(rule.side)
    n = tent = 0
    while n < alvo and tent < alvo * 4:
        tent += 1
        x, y = rnd.uniform(x0, x1), rnd.uniform(y0, y1)
        rot, esc = rnd.uniform(0, 6.28), rnd.uniform(0.75, 1.3)
        pick = rnd.random()
        i, side, sl, d = F.locate(x, y)
        if side not in sides:
            continue
        if d > 120 and rnd.random() < 0.5:
            continue
        off, _ = ctx.edge(i, side, rule.band)
        if abs(sl) < off + folga:
            continue
        if not ctx.occ.free(x, y, 3.0):
            continue
        pos = Vector((x, y, 0.0))
        z = ctx.ground(x, y) - 0.15
        if fontes:
            ok = ctx.put_inst('TREES', "Arvores", fontes[int(pick * len(fontes)) % len(fontes)],
                              pos, rot, z, folga, esc)
        else:
            ok = ctx.put('TREES', procs[int(pick * len(procs)) % len(procs)], pos, rot, z, folga, esc)
        if ok:
            n += 1
    ctx.counts['TREES_FROM_SOURCE'] = ctx.counts.get('TREES_FROM_SOURCE', 0) + (n if fontes else 0)


def _rule_custom(ctx, rule, idx):
    rnd = _rule_rng(rule, idx)
    fontes = _source_objects(rule)
    if not fontes:
        print("range_track: regra CUSTOM sem objetos-fonte (source_group / name_prefix)")
        return
    spacing = max(1.0, rule.spacing or 20.0)
    dens = rule.density if rule.density > 0 else 1.0
    offset = rule.offset if rule.offset > 0 else 2.0
    prefix = "Custom%d" % idx
    s = 8.0
    while s < ctx.length - 8.0:
        i = ctx.index_at(s)
        for side in _sides(rule.side):
            if rnd.random() > dens:
                continue
            pos, ze = ctx.out(i, side, offset, rule.band)
            if not ctx.occ.free(pos.x, pos.y, 1.0):
                continue
            z = ctx.ground(pos.x, pos.y)
            if ctx.put_inst('CUSTOM', prefix, rnd.choice(fontes), pos, ctx.facing_road(i, side), z, 0.9):
                ctx.occ.add(pos.x, pos.y, 1.0)
        s += spacing


_RULES = {'HOUSES': _rule_houses, 'POLES': _rule_poles, 'SIGNS': _rule_signs, 'PEOPLE': _rule_people,
          'TREES': _rule_trees, 'CUSTOM': _rule_custom, 'KERBS': None}
# ordem: o que ocupa espaço perto da rua antes das árvores
_ORDER = ('HOUSES', 'POLES', 'SIGNS', 'PEOPLE', 'CUSTOM', 'KERBS', 'TREES')


def generate_decor(scene, track_obj, frames, edges):
    """Aplica as regras ativas do traçado. Sem regras: não gera nada (quem cria regras é a UI/preset,
    ver default_rules). Devolve os objetos criados (blocos de 200 m, sem física)."""
    global last_report
    rules = [r for r in track_obj.range_track.rules if r.enabled]
    last_report = {'counts': {}, 'placed': [], 'objects': 0}
    if not rules:
        return []
    ctx = _Ctx(scene, track_obj, frames, edges)
    indexed = list(enumerate(track_obj.range_track.rules))
    for kind in _ORDER:
        for idx, rule in indexed:
            if rule.enabled and rule.kind == kind and _RULES.get(kind):
                _RULES[kind](ctx, rule, idx)
    objs = []
    base = track_obj.name
    mat = None
    if ctx.blocks or getattr(ctx, "portals", None):
        mat = palette_material()
    for key, g in sorted(ctx.blocks.items()):
        if g.f:
            objs.append(make_geo_object(scene, track_obj, "%s_Props_%d_%d" % ((base,) + key), g, mat))
    for nome, g in getattr(ctx, "portals", []):
        objs.append(make_geo_object(scene, track_obj, "%s_Portal_%s" % (base, nome), g, mat))
    if ctx.houses:
        rb = _buildings()
        for key, items in sorted(ctx.houses.items()):
            objs.append(make_buildings_object(scene, track_obj, "%s_Houses_%d_%d" % ((base,) + key), rb, items))
    for (prefix, key), insts in sorted(ctx.inst.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        objs.append(make_instances_object(scene, track_obj, "%s_%s_%d_%d" % ((base, prefix) + key), insts))
    last_report = {'counts': dict(ctx.counts), 'placed': list(ctx.placed), 'objects': len(objs)}
    return objs


# ---------------------------------------------------------------- âncoras
def update_anchors(scene, track_obj, frames, edges):
    """Reposiciona os objetos com range_track_anchor ligado e track == este traçado. Não apaga nem marca
    dono. Frente (-Y local) para a pista; follow_bank inclina junto com a pista. Devolve os objetos."""
    from . import terrain
    S = list(frames.s)
    N = len(S)
    moved = []
    for o in scene.objects:
        a = getattr(o, "range_track_anchor", None)
        if a is None or not a.enabled or a.track != track_obj.name:
            continue
        side = 1 if a.side >= 0 else -1
        s = a.s
        if frames.cyclic and frames.length > 0:
            s %= frames.length
        else:
            s = min(max(0.0, s), frames.length)
        pos, tan, lat, up, bank = frames.at(s)
        # borda da faixa: interpolada entre as amostras vizinhas
        k = min(N - 1, max(0, bisect.bisect_right(S, s) - 1))
        k2 = min(N - 1, k + 1)
        f = 0.0 if k2 == k or S[k2] == S[k] else (s - S[k]) / (S[k2] - S[k])

        def edge_at(i):
            if a.band:
                try:
                    r = edges.band(i, side, a.band)
                except Exception:
                    r = None
                if r is not None:
                    return r[1], r[3]
            off_, z_, _ = terrain.road_edge(edges, i, side)
            return off_, z_
        (o1, z1), (o2, z2) = edge_at(k), edge_at(k2)
        off = o1 + (o2 - o1) * f
        ze = z1 + (z2 - z1) * f
        lat_h = Vector((lat.x, lat.y, 0.0))
        lat_h = lat_h.normalized() if lat_h.length > 1e-9 else Vector((0, 1, 0))
        p = Vector(pos) + lat_h * (side * (off + a.offset))
        p.z = ze + a.height
        t = Vector((tan.x, tan.y, 0.0)).normalized()
        yaw = math.atan2(t.y, t.x) + (0.0 if side > 0 else math.pi)
        rot = Matrix.Rotation(yaw, 4, 'Z')
        if a.follow_bank:
            rot = Matrix.Rotation(bank, 4, Vector((t.x, t.y, 0.0))) * rot
        sc = o.matrix_world.to_scale()
        o.matrix_world = Matrix.Translation(p) * rot * Matrix.Scale(sc.x, 4, (1, 0, 0)) * \
            Matrix.Scale(sc.y, 4, (0, 1, 0)) * Matrix.Scale(sc.z, 4, (0, 0, 1))
        moved.append(o)
    return moved


# ---------------------------------------------------------------- regras padrão (temas)
_THEMES = {
    "bairro": [
        dict(kind='HOUSES', side='BOTH', spacing=12.0, density=0.75, offset=3.5, curve_min_deg=20.0, seed=4),
        dict(kind='POLES', side='LEFT', spacing=36.0, density=1.0, offset=2.2, seed=4),
        dict(kind='SIGNS', side='BOTH', spacing=50.0, density=1.0, offset=1.3, curve_min_deg=17.0, seed=4),
        dict(kind='PEOPLE', side='BOTH', spacing=2.0, density=0.55, offset=1.1, seed=4),
        dict(kind='TREES', side='BOTH', spacing=37.4, density=1.0, offset=4.0, source_scene="Kits",
             name_prefix="Arvore_tipo_", seed=4),
    ],
    "serra": [
        dict(kind='HOUSES', side='BOTH', spacing=12.0, density=0.12, offset=3.5, curve_min_deg=20.0, seed=5),
        dict(kind='POLES', side='LEFT', spacing=36.0, density=1.0, offset=2.2, seed=5),
        dict(kind='SIGNS', side='BOTH', spacing=50.0, density=1.0, offset=1.3, curve_min_deg=17.0, seed=5),
        dict(kind='PEOPLE', side='BOTH', spacing=2.0, density=0.55, offset=1.1, seed=5),
        dict(kind='TREES', side='BOTH', spacing=30.0, density=1.0, offset=4.0, source_scene="Kits",
             name_prefix="Arvore_tipo_", seed=5),
    ],
}


def default_rules(track_obj, theme="bairro", replace=True):
    """Preenche track_obj.range_track.rules com as regras do tema ("bairro" ou "serra", equivalentes
    ao protótipo do RolimaRacer). replace=True apaga as regras atuais antes. Devolve as regras."""
    rules = track_obj.range_track.rules
    if replace:
        rules.clear()
    out = []
    for d in _THEMES.get(theme, _THEMES["bairro"]):
        r = rules.add()
        for k, v in d.items():
            if hasattr(r, k):
                setattr(r, k, v)
        r.enabled = True
        out.append(r)
    return out
