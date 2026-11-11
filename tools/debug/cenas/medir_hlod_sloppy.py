# Compara os dois métodos do Build HLOD (Decimate x Sloppy, docs/plano-opensource.md item 2b).
# Uso: AnastacioEngine.exe -b -P medir_hlod_sloppy.py
# Cena: uma célula de 40 m com 16 objetos (icosferas, toros, caixas e cilindros; 2 materiais, UV).
# Mede por método: tempo do build, triângulos do proxy, distância geométrica proxy<->original
# (média e máxima, amostrada nos vértices dos dois lados) e UVs fora da faixa da malha original.
import time
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from bl_operators import anastacio_hlod as hlod

RATIO = 0.1


def cena():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    mats = [bpy.data.materials.new("A"), bpy.data.materials.new("B")]
    for i in range(16):
        x, y = (i % 4) * 9.0 + 2.0, (i // 4) * 9.0 + 2.0
        kind = i % 4
        if kind == 0:
            bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=5, size=2.0, location=(x, y, 2))
        elif kind == 1:
            bpy.ops.mesh.primitive_torus_add(major_segments=96, minor_segments=24, location=(x, y, 1))
        elif kind == 2:
            bpy.ops.mesh.primitive_cube_add(radius=1.5, location=(x, y, 1.5))
            bpy.ops.object.modifier_add(type='SUBSURF')
            bpy.context.object.modifiers[0].levels = 3
            bpy.context.object.modifiers[0].subdivision_type = 'SIMPLE'
            bpy.ops.object.modifier_apply(modifier=bpy.context.object.modifiers[0].name)
        else:
            bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=1.0, depth=4.0, location=(x, y, 2))
        ob = bpy.context.object
        if not ob.data.uv_layers:
            bpy.ops.mesh.uv_texture_add()
        ob.data.materials.append(mats[i % 2])
        ob.data.materials.append(mats[(i + 1) % 2])
        if i == 0:
            ob.data.vertex_colors.new("Col")
        for p in ob.data.polygons:
            p.material_index = p.index % 7 == 0
        bpy.ops.object.shade_smooth()
    return scene, [o for o in scene.objects if o.type == 'MESH']


def bvh_de(ob):
    me = ob.to_mesh(bpy.context.scene, False, 'PREVIEW')
    me.transform(ob.matrix_world)
    verts = [v.co.copy() for v in me.vertices]
    tree = BVHTree.FromPolygons(verts, [tuple(p.vertices) for p in me.polygons])
    bpy.data.meshes.remove(me)
    return tree, verts


def distancias(a_verts, b_tree):
    d = [b_tree.find_nearest(v)[3] for v in a_verts]
    return sum(d) / len(d), max(d)


for metodo in ('DECIMATE', 'SLOPPY'):
    scene, objs = cena()
    orig = [bvh_de(o) for o in objs]
    tris_orig = sum(len(o.data.polygons) for o in objs)
    t0 = time.perf_counter()
    proxies, _ = hlod.build(scene, objs, cell_size=40.0, distance=80.0, ratio=RATIO, min_objects=4, method=metodo)
    dt = time.perf_counter() - t0
    p = proxies[0]
    ptree, pverts = bvh_de(p)
    tris = sum(len(f.vertices) - 2 for f in p.data.polygons)
    # proxy -> original mais próximo
    ida = [min(t.find_nearest(v)[3] for t, _ in orig) for v in pverts]
    volta = distancias([v for _, vs in orig for v in vs], ptree)
    uv = p.data.uv_layers[0].data if p.data.uv_layers else []
    fora = sum(1 for d in uv if not (-0.01 <= d.uv.x <= 1.01 and -0.01 <= d.uv.y <= 1.01))
    mats = sorted({f.material_index for f in p.data.polygons})
    print("HLOD %s: %.3f s, tris %d -> %d, proxy->orig media %.4f max %.4f, orig->proxy media %.4f max %.4f, "
          "uv fora %d/%d, materiais %s, cores %s" % (metodo, dt, tris_orig, tris, sum(ida) / len(ida), max(ida),
                                           volta[0], volta[1], fora, len(uv), mats, [c.name for c in p.data.vertex_colors]))
