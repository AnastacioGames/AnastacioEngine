# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
# ##### END GPL LICENSE BLOCK #####

"""Gerador de casas brasileiras low poly (Track Tool / decoracao).

API:
    STYLES                       nomes dos estilos
    build(style, seed, width=None, depth=None, floors=None, lod=0, foundation=0.0)
        -> {"verts", "faces", "uvs", "size": (w, d, h), "style", "seed", "lod"}
        Origem no chao, centro da frente do lote; frente para -Y; lote em
        x [-w/2, w/2], y [0, d]. foundation (m) desce paredes e muros abaixo do chao.
    atlas_material()             Material "Casas_Atlas" (uma textura, um material)
    to_mesh(name, built)         bpy Mesh
    add_house(scene, style, seed, location, rotation_z, lod=0, name=None, **kw) -> Object
    merge([(built, matrix4x4), ...]) -> dict no mesmo formato
    sidewalk(length, width=2.0, curb=0.15) -> dict (calcada com meio-fio, frente em -Y)

Filtro: no jogo a filtragem e global (linear + mipmap pelas preferencias), entao o
atlas tem margem de 4 px por celula e UV so no miolo; ver atlas.py.
"""

import random
import zlib

from . import atlas
from .styles import STYLE_FUNCS, LABELS
from .house import House
from .geom import Built

STYLES = list(STYLE_FUNCS)
ATLAS_NAME = "Casas_Atlas"


def _seed(style, seed):
    return (zlib.crc32(style.encode("utf-8")) * 1000003 + int(seed)) & 0x7FFFFFFF


def build(style, seed, width=None, depth=None, floors=None, lod=0, foundation=0.0):
    if style not in STYLE_FUNCS:
        raise ValueError("estilo desconhecido: %r (use um de %s)" % (style, STYLES))
    R = random.Random(_seed(style, seed))
    H = House(1 if lod else 0, foundation)
    W, D = STYLE_FUNCS[style](R, H, width or None, depth or None, int(floors) if floors else None)
    b = H.b
    h = max(v[2] for v in b.verts) if b.verts else 0.0
    return {"verts": b.verts, "faces": b.faces, "uvs": b.uvs, "size": (W, D, h),
            "style": style, "seed": seed, "lod": 1 if lod else 0}


def triangles(built):
    return sum(len(f) - 2 for f in built["faces"])


def sidewalk(length, width=2.0, curb=0.15):
    """Calcada de x -length/2..length/2, y -width..0, topo em z=0 e meio-fio ate -curb."""
    b = Built()
    x0, x1 = -length / 2, length / 2
    b.ring_top((x0, x1, -width, 0.0), None, 0.0, "calcada", atlas.METERS["calcada"])
    b.quad((x0, -width, -curb), (length, 0, 0), (0, 0, curb), "meio_fio")
    return {"verts": b.verts, "faces": b.faces, "uvs": b.uvs, "size": (length, width, 0.0)}


def _mat_rows(m):
    try:
        return [[float(m[r][c]) for c in range(4)] for r in range(4)]
    except Exception:
        return [list(map(float, row)) for row in m]


def merge(items):
    verts, faces, uvs = [], [], []
    for built, m in items:
        M = _mat_rows(m)
        det = (M[0][0] * (M[1][1] * M[2][2] - M[1][2] * M[2][1])
               - M[0][1] * (M[1][0] * M[2][2] - M[1][2] * M[2][0])
               + M[0][2] * (M[1][0] * M[2][1] - M[1][1] * M[2][0]))
        off = len(verts)
        for x, y, z in built["verts"]:
            verts.append(tuple(M[r][0] * x + M[r][1] * y + M[r][2] * z + M[r][3] for r in range(3)))
        for f, uv in zip(built["faces"], built["uvs"]):
            if det < 0:
                f, uv = f[::-1], uv[::-1]
            faces.append(tuple(k + off for k in f))
            uvs.append(list(uv))
    if verts:
        xs, ys, zs = zip(*verts)
        size = (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
    else:
        size = (0.0, 0.0, 0.0)
    return {"verts": verts, "faces": faces, "uvs": uvs, "size": size}


# ------------------------------------------------------------------------ bpy

_painted = set()


def atlas_image(force=False):
    import bpy
    import os
    img = bpy.data.images.get(ATLAS_NAME)
    if img is not None and tuple(img.size) != (atlas.W, atlas.H):
        img.scale(atlas.W, atlas.H)
    if img is None:
        img = bpy.data.images.new(ATLAS_NAME, atlas.W, atlas.H, alpha=False)
    key = img.as_pointer()
    if force or key not in _painted or img.get("range_buildings") != atlas.VERSION:
        img.pixels = atlas.paint().ravel().tolist()
        img["range_buildings"] = atlas.VERSION
        saved = False
        if bpy.data.filepath:
            try:
                d = os.path.join(os.path.dirname(bpy.data.filepath), "textures")
                os.makedirs(d, exist_ok=True)
                path = os.path.join(d, ATLAS_NAME + ".png")
                img.file_format = 'PNG'
                img.save_render(path)
                if img.packed_file:
                    img.unpack(method='USE_ORIGINAL')
                img.source = 'FILE'
                img.filepath = "//textures/%s.png" % ATLAS_NAME
                img.reload()
                saved = os.path.isfile(path)
                saved = True
            except Exception as ex:
                print("range_buildings: nao salvou o atlas (%s); empacotando" % ex)
        if not saved:
            img.pack(as_png=True)
        _painted.add(img.as_pointer())
    return img


def atlas_material():
    """Cria ou reaproveita o material e repinta o atlas (uma vez por sessao)."""
    import bpy
    img = atlas_image()
    tex = bpy.data.textures.get(ATLAS_NAME) or bpy.data.textures.new(ATLAS_NAME, 'IMAGE')
    if tex.type != 'IMAGE':
        tex.type = 'IMAGE'
        tex = bpy.data.textures[ATLAS_NAME]
    tex.image = img
    tex.use_interpolation = True
    tex.use_mipmap = True
    tex.filter_type = 'BOX'
    mat = bpy.data.materials.get(ATLAS_NAME) or bpy.data.materials.new(ATLAS_NAME)
    mat.diffuse_color = (1.0, 1.0, 1.0)
    mat.diffuse_intensity = 1.0
    mat.specular_intensity = 0.05
    if not mat.texture_slots[0] or mat.texture_slots[0].texture != tex:
        mat.texture_slots.clear(0) if mat.texture_slots[0] else None
        slot = mat.texture_slots.create(0)
        slot.texture = tex
    slot = mat.texture_slots[0]
    slot.texture_coords = 'UV'
    slot.uv_layer = "UVMap"
    return mat


def to_mesh(name, built):
    import bpy
    me = bpy.data.meshes.new(name)
    me.from_pydata(built["verts"], [], built["faces"])
    me.update(calc_edges=True)
    mat = atlas_material()
    me.materials.append(mat)
    uvt = me.uv_textures.new("UVMap")
    lay = me.uv_layers[uvt.name]
    img = mat.texture_slots[0].texture.image
    k = 0
    for p, uv in zip(me.polygons, built["uvs"]):
        p.use_smooth = False
        for li, c in zip(p.loop_indices, uv):
            lay.data[li].uv = c
        uvt.data[p.index].image = img
        k += 1
    return me


def add_house(scene, style, seed, location=(0, 0, 0), rotation_z=0.0, lod=0, name=None, collision=False, **kw):
    import bpy
    built = build(style, seed, lod=lod, **kw)
    name = name or "Casa_%s_%d%s" % (style, seed, "_LOD1" if lod else "")
    ob = bpy.data.objects.new(name, to_mesh(name, built))
    scene.objects.link(ob)
    ob.location = location
    ob.rotation_euler = (0.0, 0.0, rotation_z)
    ob["range_buildings"] = "%s:%d" % (style, seed)
    if collision:
        ob.game.physics_type = 'STATIC'
        ob.game.use_collision_bounds = True
        ob.game.collision_bounds_type = 'BOX'
    else:
        ob.game.physics_type = 'NO_COLLISION'
    return ob
