"""Teste do gerador de casas brasileiras (range_buildings).

Uso: AnastacioEngine.exe -b --python tools/debug/buildings/test_buildings.py [-- --no-render]
Confere orcamento de triangulos, faces sem area, UV em [0,1] e material unico;
renderiza prints (Blender Internal, sem fog) em artifacts/buildings/.
"""
import math
import os
import sys

import bpy
from mathutils import Vector, Matrix

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "source", "release", "scripts", "modules"))
for k in [m for m in sys.modules if m.startswith("range_buildings")]:
    del sys.modules[k]
import range_buildings as rb  # noqa: E402

OUT = os.path.join(ROOT, "artifacts", "buildings")
os.makedirs(OUT, exist_ok=True)
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
RENDER = "--no-render" not in argv
SEEDS = range(5)
BUDGET0 = {"predinho": 500}
errors = []
report = []


def area(vs):
    a = Vector((0, 0, 0))
    for i in range(1, len(vs) - 1):
        a += (Vector(vs[i]) - Vector(vs[0])).cross(Vector(vs[i + 1]) - Vector(vs[0]))
    return a.length / 2


sc = bpy.context.scene
for o in list(sc.objects):
    bpy.data.objects.remove(o, do_unlink=True)

for st in rb.STYLES:
    mx = [0, 0]
    for s in SEEDS:
        for lod in (0, 1):
            b = rb.build(st, s, lod=lod)
            t = rb.triangles(b)
            mx[lod] = max(mx[lod], t)
            lim = BUDGET0.get(st, 300) if lod == 0 else 40
            if t > lim:
                errors.append("%s seed %d LOD%d: %d tris > %d" % (st, s, lod, t, lim))
            for f, uv in zip(b["faces"], b["uvs"]):
                if area([b["verts"][i] for i in f]) < 1e-5:
                    errors.append("%s seed %d LOD%d: face com area zero" % (st, s, lod))
                    break
                if len(uv) != len(f) or any(not (0 <= u <= 1 and 0 <= v <= 1) for u, v in uv):
                    errors.append("%s seed %d LOD%d: UV fora de [0,1]" % (st, s, lod))
                    break
            if min(v[2] for v in b["verts"]) < -1e-6:
                errors.append("%s seed %d LOD%d: abaixo do chao sem foundation" % (st, s, lod))
    report.append("%-18s LOD0 max %3d  LOD1 max %2d" % (st, mx[0], mx[1]))
    # com alicerce
    b = rb.build(st, 3, foundation=1.5)
    if abs(min(v[2] for v in b["verts"]) + 1.5) > 1e-4:
        errors.append("%s: foundation nao chegou a -1.5" % st)

# objetos na cena: todos com o mesmo material
objs = []
for i, st in enumerate(rb.STYLES):
    for s in SEEDS:
        for lod in (0, 1):
            objs.append(rb.add_house(sc, st, s, (s * 14.0 + lod * 80, i * 20.0, 0), 0.0, lod))
mats = {m.name for o in objs for m in o.data.materials}
if mats != {"Casas_Atlas"}:
    errors.append("materiais: %s" % mats)

print("\n".join(report))
with open(os.path.join(OUT, "relatorio.txt"), "w") as f:
    f.write("\n".join(report) + "\n" + ("\n".join(errors) or "OK") + "\n")
print("ERROS:" if errors else "TUDO OK", *errors, sep="\n")

if RENDER:
    for o in list(sc.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    sc.render.engine = 'BLENDER_RENDER'
    w = sc.world or bpy.data.worlds.new("W")
    sc.world = w
    w.mist_settings.use_mist = False
    w.horizon_color = (0.62, 0.75, 0.9)
    w.zenith_color = (0.3, 0.5, 0.85)
    w.use_sky_blend = True
    w.light_settings.use_environment_light = True
    w.light_settings.environment_energy = 0.55
    w.light_settings.gather_method = 'APPROXIMATE'
    sun = bpy.data.objects.new("sun", bpy.data.lamps.new("sun", 'SUN'))
    sun.data.energy = 1.15
    sun.rotation_euler = (math.radians(50), 0, math.radians(35))
    sc.objects.link(sun)
    fill = bpy.data.objects.new("fill", bpy.data.lamps.new("fill", 'SUN'))
    fill.data.energy = 0.35
    fill.rotation_euler = (math.radians(60), 0, math.radians(200))
    sc.objects.link(fill)
    gm = bpy.data.materials.new("chao")
    gm.diffuse_color = (0.33, 0.32, 0.30)
    gme = bpy.data.meshes.new("chao")
    gme.from_pydata([(-300, -40, -0.16), (300, -40, -0.16), (300, 300, -0.16), (-300, 300, -0.16)], [], [(0, 1, 2, 3)])
    gme.materials.append(gm)
    sc.objects.link(bpy.data.objects.new("chao", gme))
    sc.render.resolution_x, sc.render.resolution_y = 1280, 720
    sc.render.resolution_percentage = 100
    sc.render.use_antialiasing = True
    sc.render.use_shadows = True
    sc.render.use_raytrace = True
    sun.data.shadow_method = 'RAY_SHADOW'
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    cam.data.clip_end = 2000
    sc.objects.link(cam)
    sc.camera = cam

    def shot(name, pos, alvo, lens=28):
        cam.data.lens = lens
        cam.location = pos
        cam.rotation_euler = (Vector(alvo) - Vector(pos)).to_track_quat('-Z', 'Y').to_euler()
        sc.render.filepath = os.path.join(OUT, name + ".png")
        bpy.ops.render.render(write_still=True)

    # rua: fileira variada com calcada (um objeto so)
    import random
    R = random.Random(7)
    items, x = [], 0.0
    for k in range(12):
        st = rb.STYLES[k % len(rb.STYLES)] if k < 8 else R.choice(rb.STYLES)
        b = rb.build(st, 100 + k)
        wd = b["size"][0]
        items.append((b, Matrix.Translation((x + wd / 2, 0, 0))))
        x += wd
    items.append((rb.sidewalk(x, 2.5), Matrix.Translation((x / 2, 0, 0))))
    rua = rb.merge(items)
    ob = bpy.data.objects.new("rua", rb.to_mesh("rua", rua))
    sc.objects.link(ob)
    # outro lado da rua (girado 180), em LOD1 ao fundo
    items2, x2 = [], 0.0
    for k in range(12):
        b = rb.build(rb.STYLES[(k * 3) % 8], 200 + k, lod=1)
        wd = b["size"][0]
        items2.append((b, Matrix.Translation((x2 + wd / 2, 26, 0)) * Matrix.Rotation(math.pi, 4, 'Z')))
        x2 += wd
    ob2 = bpy.data.objects.new("rua2", rb.to_mesh("rua2", rb.merge(items2)))
    sc.objects.link(ob2)
    shot("rua_01", (x * 0.15, -16, 4.0), (x * 0.45, 4, 3.0), 24)
    shot("rua_02", (x * 0.85, -14, 9.0), (x * 0.5, 6, 2.0), 24)
    shot("rua_03_alto", (x * 0.5, -45, 35), (x * 0.5, 8, 0), 28)
    shot("rua_04_lod1", (x * 0.5, 2, 3.5), (x * 0.5, 26, 4), 24)
    sc.objects.unlink(ob)
    sc.objects.unlink(ob2)
    # closes por estilo (4 seeds lado a lado)
    for st in rb.STYLES:
        objs, x = [], 0.0
        for s in range(4):
            b = rb.build(st, s)
            o = bpy.data.objects.new("c", rb.to_mesh("c", b))
            o.location = (x + b["size"][0] / 2, 0, 0)
            sc.objects.link(o)
            objs.append(o)
            x += b["size"][0] + 2.0
        shot("close_" + st, (x * 0.5 - 4, -24, 9), (x * 0.5, 4, 3), 30)
        for o in objs:
            sc.objects.unlink(o)
