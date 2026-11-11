"""Mede o empacotamento da UV de lightmap (xatlas x Lightmap Pack) em cena controlada.

Uso (sem janela):
  build/bin/AnastacioEngine.exe -b --factory-startup --python tools/debug/cenas/medir_lightmap_uv.py

Casos: esfera e toro (curvos), sala de caixas (retângulos grandes), n-gon côncavo e face degenerada.
Imprime o empacotador escolhido (log "UV packer used"), área coberta, sobreposição entre triângulos
(rasterizada numa grade do tamanho do atlas) e a menor distância em texels entre ilhas diferentes.
"""
import bpy
import bmesh
import numpy as np
from bl_operators import anastacio_lightmap as lm

SIZE = 512
MARGIN = 4


def clear():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)


def add_concave_ngon(scene):
    me = bpy.data.meshes.new("ngon")
    bm = bmesh.new()
    pts = [(0, 0), (4, 0), (4, 4), (3, 4), (3, 1), (1, 1), (1, 4), (0, 4)]  # "U"
    vs = [bm.verts.new((x, y, 0)) for x, y in pts]
    bm.faces.new(vs)
    # face degenerada (três pontos alinhados) colada ao lado
    a, b, c = bm.verts.new((5, 0, 0)), bm.verts.new((6, 0, 0)), bm.verts.new((7, 0, 0))
    bm.faces.new((a, b, c))
    bm.to_mesh(me)
    ob = bpy.data.objects.new("ngon", me)
    scene.objects.link(ob)
    return ob


def build(scene):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, location=(0, 0, 0))
    bpy.ops.mesh.primitive_torus_add(location=(4, 0, 0))
    for i in range(6):
        bpy.ops.mesh.primitive_cube_add(location=(-6 + i * 2.5, 6, 0))
        bpy.context.object.scale = (1.0, 1.0 + i * 0.5, 0.3)
    add_concave_ngon(scene)
    return [ob for ob in scene.objects if ob.type == 'MESH']


def triangles(objects):
    """(uv triangle, island id) por objeto/polígono; ilha = polígonos ligados por aresta com mesma UV."""
    out = []
    island = 0
    for ob in objects:
        me = ob.data
        uv = me.uv_layers[lm.UV_NAME].data
        bm = bmesh.new()
        bm.from_mesh(me)
        layer = bm.loops.layers.uv[lm.UV_NAME]
        bm.faces.ensure_lookup_table()
        seen = {}
        for f in bm.faces:
            if f.index in seen:
                continue
            stack = [f]
            seen[f.index] = island
            while stack:
                g = stack.pop()
                for l in g.loops:
                    for e_l in l.edge.link_loops:
                        h = e_l.face
                        if h.index in seen:
                            continue
                        # mesma UV nos dois lados da aresta -> mesma ilha
                        a1, a2 = l[layer].uv, l.link_loop_next[layer].uv
                        b1, b2 = e_l.link_loop_next[layer].uv, e_l[layer].uv
                        if (a1 - b1).length < 1e-6 and (a2 - b2).length < 1e-6:
                            seen[h.index] = island
                            stack.append(h)
            island += 1
        # triangulação correta (ear clipping), não leque: n-gon côncavo em leque cobre fora do polígono
        for tri in bm.calc_tessface():
            out.append((tuple(tuple(l[layer].uv) for l in tri), seen[tri[0].face.index], ob.name))
        bm.free()
    return out


def raster(tris):
    owner = np.full((SIZE, SIZE), -1, dtype=np.int64)
    overlap = 0
    pairs = {}
    owner_name = {}
    ys, xs = np.mgrid[0:SIZE, 0:SIZE]
    px = (xs + 0.5) / SIZE
    py = (ys + 0.5) / SIZE
    for (a, b, c), isl, name in tris:
        x0 = int(max(0, min(a[0], b[0], c[0]) * SIZE)); x1 = int(min(SIZE - 1, max(a[0], b[0], c[0]) * SIZE + 1))
        y0 = int(max(0, min(a[1], b[1], c[1]) * SIZE)); y1 = int(min(SIZE - 1, max(a[1], b[1], c[1]) * SIZE + 1))
        if x1 < x0 or y1 < y0:
            continue
        X = px[y0:y1 + 1, x0:x1 + 1]; Y = py[y0:y1 + 1, x0:x1 + 1]
        d = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(d) < 1e-12:
            continue
        w0 = ((b[1] - c[1]) * (X - c[0]) + (c[0] - b[0]) * (Y - c[1])) / d
        w1 = ((c[1] - a[1]) * (X - c[0]) + (a[0] - c[0]) * (Y - c[1])) / d
        inside = (w0 > 1e-4) & (w1 > 1e-4) & (1 - w0 - w1 > 1e-4)
        sub = owner[y0:y1 + 1, x0:x1 + 1]
        hit = inside & (sub >= 0) & (sub != isl)
        if hit.any():
            others = {owner_name[i] for i in np.unique(sub[hit])}
            for o in others:
                pairs[(name, o)] = pairs.get((name, o), 0) + int(np.count_nonzero(hit))
        overlap += int(np.count_nonzero(hit))
        owner_name[isl] = name
        sub[inside] = isl
    return owner, overlap, pairs


def min_gap(owner):
    """Menor distância (texels, Chebyshev) entre pixels de ilhas diferentes, até 2*MARGIN+2."""
    limit = 2 * MARGIN + 2
    for r in range(1, limit + 1):
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if max(abs(dx), abs(dy)) != r:
                    continue
                a = owner[max(0, dy):SIZE + min(0, dy), max(0, dx):SIZE + min(0, dx)]
                b = owner[max(0, -dy):SIZE + min(0, -dy), max(0, -dx):SIZE + min(0, -dx)]
                if np.any((a >= 0) & (b >= 0) & (a != b)):
                    return r
    return limit + 1


def main():
    scene = bpy.context.scene
    clear()
    objects = build(scene)
    lm.make_lightmap_uvs(scene, objects, SIZE, MARGIN)
    tris = triangles(objects)
    owner, overlap, pairs = raster(tris)
    for k, v in sorted(pairs.items(), key=lambda kv: -kv[1])[:10]:
        print('MEDIR_LM sobrepoe', k, v)
    covered = np.count_nonzero(owner >= 0) / float(SIZE * SIZE)
    print("MEDIR_LM objetos=%d triangulos=%d ilhas=%d" % (len(objects), len(tris), len({t[1] for t in tris})))
    print("MEDIR_LM cobertura=%.1f%% sobreposicao_px=%d menor_vao_texels=%d (margem pedida %d -> esperado >= %d)"
          % (100 * covered, overlap, min_gap(owner), MARGIN, 2 * MARGIN))


main()
