"""Mede a qualidade do modificador Decimate (Collapse) em formas de referencia.

Uso:
  AnastacioEngine.exe -b --factory-startup --python tools/debug/cenas/medir_decimate.py -- <saida.txt> <antigo|novo> [cena.range]

"antigo" mede o Collapse original; "novo" liga a opcao High Quality (use_collapse_quality).

Cada forma tem superficie e UV analiticas, entao o resultado decimado e comparado com a forma ideal:
  desvio  distancia dos pontos da malha decimada ate a superficie ideal (max e RMS)
  volume  erro percentual de volume contra a malha original
  uv      diferenca entre a UV guardada e a UV ideal na posicao do vertice (max e RMS)
  ang     menor angulo de triangulo e quantos triangulos tem angulo abaixo de 5 graus
  virad   triangulos com a normal apontando para dentro
Com um terceiro argumento salva a cena com os objetos lado a lado para conferir no editor.
"""

import math
import sys
import time

import bpy
from mathutils import Vector

RATIOS = (1.0, 0.5, 0.2, 0.1, 0.05, 0.02)
TWO_PI = 2.0 * math.pi


# ---------------------------------------------------------------- formas

def wave_height(x, y):
    return 0.15 * math.sin(3.0 * x) * math.cos(3.0 * y)


def build_box(n):
    verts = []
    index = {}
    faces = []

    def vert(co):
        key = tuple(round(c, 6) for c in co)
        if key not in index:
            index[key] = len(verts)
            verts.append(key)
        return index[key]

    for axis in range(3):
        for side in (-1.0, 1.0):
            a, b = [i for i in range(3) if i != axis]
            for i in range(n):
                for j in range(n):
                    quad = []
                    for di, dj in ((0, 0), (1, 0), (1, 1), (0, 1)):
                        co = [0.0, 0.0, 0.0]
                        co[axis] = side
                        co[a] = -1.0 + 2.0 * (i + di) / n
                        co[b] = -1.0 + 2.0 * (j + dj) / n
                        quad.append(vert(co))
                    faces.append(quad)
    return verts, faces


def build_round_box(n):
    verts, faces = build_box(n)
    out = []
    for co in verts:
        core = Vector([max(-0.7, min(0.7, c)) for c in co])
        offset = Vector(co) - core
        if offset.length > 1e-9:
            offset = offset.normalized() * 0.3
        out.append(tuple(core + offset))
    return out, faces


def build_cylinder(seg, rings):
    verts = []
    faces = []
    for r in range(rings + 1):
        z = -1.0 + 2.0 * r / rings
        for s in range(seg):
            ang = TWO_PI * s / seg
            verts.append((math.cos(ang), math.sin(ang), z))
    for r in range(rings):
        for s in range(seg):
            s2 = (s + 1) % seg
            faces.append([r * seg + s, r * seg + s2, (r + 1) * seg + s2, (r + 1) * seg + s])
    bottom = len(verts)
    verts.append((0.0, 0.0, -1.0))
    top = len(verts)
    verts.append((0.0, 0.0, 1.0))
    for s in range(seg):
        s2 = (s + 1) % seg
        faces.append([bottom, s2, s])
        faces.append([top, rings * seg + s, rings * seg + s2])
    return verts, faces


def build_sphere(seg, rings):
    verts = [(0.0, 0.0, 1.0)]
    faces = []
    for r in range(1, rings):
        theta = math.pi * r / rings
        for s in range(seg):
            phi = TWO_PI * s / seg
            verts.append((math.sin(theta) * math.cos(phi), math.sin(theta) * math.sin(phi), math.cos(theta)))
    south = len(verts)
    verts.append((0.0, 0.0, -1.0))

    def ring(r, s):
        return 1 + (r - 1) * seg + (s % seg)

    for s in range(seg):
        faces.append([0, ring(1, s), ring(1, s + 1)])
        faces.append([south, ring(rings - 1, s + 1), ring(rings - 1, s)])
    for r in range(1, rings - 1):
        for s in range(seg):
            faces.append([ring(r, s), ring(r + 1, s), ring(r + 1, s + 1), ring(r, s + 1)])
    return verts, faces


def build_wave(n):
    verts = []
    faces = []
    for i in range(n + 1):
        for j in range(n + 1):
            x = -1.0 + 2.0 * i / n
            y = -1.0 + 2.0 * j / n
            verts.append((x, y, wave_height(x, y)))
    for i in range(n):
        for j in range(n):
            faces.append([i * (n + 1) + j, (i + 1) * (n + 1) + j, (i + 1) * (n + 1) + j + 1, i * (n + 1) + j + 1])
    return verts, faces


# ---------------------------------------------------------------- superficie e UV ideais

def dist_box(p):
    q = Vector((abs(p.x) - 1.0, abs(p.y) - 1.0, abs(p.z) - 1.0))
    outside = Vector((max(q.x, 0.0), max(q.y, 0.0), max(q.z, 0.0))).length
    inside = min(max(q.x, q.y, q.z), 0.0)
    return abs(outside + inside)


def dist_round_box(p):
    q = Vector((abs(p.x) - 0.7, abs(p.y) - 0.7, abs(p.z) - 0.7))
    outside = Vector((max(q.x, 0.0), max(q.y, 0.0), max(q.z, 0.0))).length
    inside = min(max(q.x, q.y, q.z), 0.0)
    return abs(outside + inside - 0.3)


def dist_cylinder(p):
    dr = math.hypot(p.x, p.y) - 1.0
    dz = abs(p.z) - 1.0
    outside = math.hypot(max(dr, 0.0), max(dz, 0.0))
    inside = min(max(dr, dz), 0.0)
    return abs(outside + inside)


def dist_sphere(p):
    return abs(p.length - 1.0)


def dist_wave(p):
    return abs(p.z - wave_height(p.x, p.y))


def wrap_near(u, ref):
    return u - round(u - ref)


def uv_box(p, normal, center):
    axis = max(range(3), key=lambda i: abs(normal[i]))
    a, b = [i for i in range(3) if i != axis]
    return (p[a] * 0.5 + 0.5, p[b] * 0.5 + 0.5), 1.0


def uv_cylinder(p, normal, center):
    if abs(normal.z) > 0.7:
        return (p.x * 0.5 + 0.5, p.y * 0.5 + 0.5), 1.0
    ref = math.atan2(center.y, center.x) / TWO_PI
    u = wrap_near(math.atan2(p.y, p.x) / TWO_PI, ref)
    return (u, p.z * 0.5 + 0.5), 1.0


def uv_sphere(p, normal, center):
    length = max(p.length, 1e-9)
    v = math.acos(max(-1.0, min(1.0, p.z / length))) / math.pi
    sin_theta = math.hypot(p.x, p.y) / length
    ref = math.atan2(center.y, center.x) / TWO_PI
    if sin_theta < 1e-4:
        return (ref, v), 0.0
    u = wrap_near(math.atan2(p.y, p.x) / TWO_PI, ref)
    return (u, v), sin_theta


def uv_wave(p, normal, center):
    return (p.x * 0.5 + 0.5, p.y * 0.5 + 0.5), 1.0


SHAPES = (
    # nome, construtor, distancia, uv, fechada, u periodico
    ("cubo", lambda: build_box(12), dist_box, uv_box, True, False),
    ("cubo_arr", lambda: build_round_box(20), dist_round_box, uv_sphere, True, True),
    ("cilindro", lambda: build_cylinder(48, 24), dist_cylinder, uv_cylinder, True, True),
    ("esfera", lambda: build_sphere(48, 24), dist_sphere, uv_sphere, True, True),
    ("onda", lambda: build_wave(40), dist_wave, uv_wave, False, False),
)


# ---------------------------------------------------------------- malha

def orient_faces(verts, faces, closed):
    out = []
    for face in faces:
        cos = [Vector(verts[i]) for i in face]
        center = sum(cos, Vector()) / len(cos)
        normal = Vector()
        for k in range(len(cos)):
            normal += cos[k].cross(cos[(k + 1) % len(cos)])
        outward = normal.dot(center) if closed else normal.z
        out.append(list(face) if outward >= 0.0 else list(reversed(face)))
    return out


def poly_frame(mesh, poly):
    return poly.normal.copy(), poly.center.copy()


def make_object(scene, name, verts, faces, uv_func, closed):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], orient_faces(verts, faces, closed))
    mesh.update(calc_edges=True)
    mesh.uv_textures.new("UV")
    uv_data = mesh.uv_layers.active.data
    for poly in mesh.polygons:
        normal, center = poly_frame(mesh, poly)
        for li in poly.loop_indices:
            co = mesh.vertices[mesh.loops[li].vertex_index].co
            uv_data[li].uv = uv_func(co, normal, center)[0]
    obj = bpy.data.objects.new(name, mesh)
    scene.objects.link(obj)
    return obj


def tri_min_angle(a, b, c):
    best = 180.0
    for p, q, r in ((a, b, c), (b, c, a), (c, a, b)):
        e1 = q - p
        e2 = r - p
        if e1.length < 1e-12 or e2.length < 1e-12:
            return 0.0
        best = min(best, math.degrees(e1.angle(e2)))
    return best


def measure(mesh, dist_func, uv_func, closed, periodic):
    uv_data = mesh.uv_layers.active.data if mesh.uv_layers.active else None
    dev_max = 0.0
    dev_sum = 0.0
    dev_n = 0
    uv_max = 0.0
    uv_sum = 0.0
    uv_n = 0
    volume = 0.0
    ang_min = 180.0
    slivers = 0
    flipped = 0
    tris = 0

    for poly in mesh.polygons:
        normal, center = poly_frame(mesh, poly)
        loops = list(poly.loop_indices)
        cos = [mesh.vertices[mesh.loops[li].vertex_index].co.copy() for li in loops]

        if uv_data is not None:
            for li, co in zip(loops, cos):
                expected, weight = uv_func(co, normal, center)
                du = uv_data[li].uv[0] - expected[0]
                if periodic:
                    du -= round(du)
                dv = uv_data[li].uv[1] - expected[1]
                err = math.hypot(du * weight, dv)
                uv_max = max(uv_max, err)
                uv_sum += err * err
                uv_n += 1

        for k in range(1, len(cos) - 1):
            a, b, c = cos[0], cos[k], cos[k + 1]
            tris += 1
            volume += a.dot(b.cross(c)) / 6.0
            tri_normal = (b - a).cross(c - a)
            tri_center = (a + b + c) / 3.0
            if (tri_normal.dot(tri_center) if closed else tri_normal.z) < 0.0:
                flipped += 1
            angle = tri_min_angle(a, b, c)
            ang_min = min(ang_min, angle)
            if angle < 5.0:
                slivers += 1
            for p in (a, b, c, tri_center, (a + b) * 0.5, (b + c) * 0.5, (c + a) * 0.5):
                d = dist_func(p)
                dev_max = max(dev_max, d)
                dev_sum += d * d
                dev_n += 1

    return {
        "tris": tris,
        "dev_max": dev_max,
        "dev_rms": math.sqrt(dev_sum / max(dev_n, 1)),
        "uv_max": uv_max,
        "uv_rms": math.sqrt(uv_sum / max(uv_n, 1)),
        "volume": volume,
        "ang_min": ang_min,
        "slivers": slivers,
        "flipped": flipped,
    }


def setup_view(scene):
    lamp = bpy.data.lamps.new("Sun", 'SUN')
    sun = bpy.data.objects.new("Sun", lamp)
    sun.rotation_euler = (math.radians(50.0), 0.0, math.radians(30.0))
    scene.objects.link(sun)
    cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    cam.data.lens = 16.0
    cam.location = (6.0, -14.0, 7.0)
    cam.rotation_euler = (Vector((6.0, 0.0, 0.0)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    scene.objects.link(cam)
    scene.camera = cam


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if len(argv) < 2 or argv[1] not in ("antigo", "novo"):
        raise SystemExit("uso: <saida.txt> <antigo|novo> [cena.range]")
    out_path = argv[0]
    quality = argv[1] == "novo"
    scene_path = argv[2] if len(argv) > 2 else None

    scene = bpy.context.scene
    for obj in list(scene.objects):
        scene.objects.unlink(obj)
    scene.render.engine = 'BLENDER_GAME'

    lines = []
    header = "{:9} {:>5} {:>6} {:>9} {:>9} {:>8} {:>9} {:>9} {:>7} {:>5} {:>5} {:>7}".format(
        "forma", "ratio", "tris", "desv_max", "desv_rms", "volume%", "uv_max", "uv_rms", "ang_min", "<5gr", "virad", "ms")
    lines.append(header)

    colors = ((0.8, 0.2, 0.2), (0.8, 0.4, 0.8), (0.2, 0.7, 0.2), (0.2, 0.4, 0.9), (0.9, 0.7, 0.1))
    for idx, (name, builder, dist_func, uv_func, closed, periodic) in enumerate(SHAPES):
        verts, faces = builder()
        obj = make_object(scene, name, verts, faces, uv_func, closed)
        obj.location = (idx * 3.0, 0.0, 0.0)
        mat = bpy.data.materials.new(name)
        mat.diffuse_color = colors[idx]
        obj.data.materials.append(mat)

        mod = obj.modifiers.new("Decimate", 'DECIMATE')
        mod.decimate_type = 'COLLAPSE'
        mod.use_collapse_triangulate = True
        if not hasattr(mod, "use_collapse_quality"):
            if quality:
                raise SystemExit("este build nao tem use_collapse_quality")
        else:
            mod.use_collapse_quality = quality
        base_volume = None
        for ratio in RATIOS:
            mod.ratio = ratio
            scene.update()
            start = time.time()
            mesh = obj.to_mesh(scene, True, 'PREVIEW')
            elapsed = (time.time() - start) * 1000.0
            res = measure(mesh, dist_func, uv_func, closed, periodic)
            bpy.data.meshes.remove(mesh)
            if base_volume is None:
                base_volume = res["volume"]
            vol_err = (res["volume"] / base_volume - 1.0) * 100.0 if closed and base_volume else 0.0
            lines.append("{:9} {:5.2f} {:6d} {:9.5f} {:9.5f} {:8.3f} {:9.5f} {:9.5f} {:7.2f} {:5d} {:5d} {:7.1f}".format(
                name, ratio, res["tris"], res["dev_max"], res["dev_rms"], vol_err,
                res["uv_max"], res["uv_rms"], res["ang_min"], res["slivers"], res["flipped"], elapsed))
        mod.ratio = 0.1
        lines.append("")

    with open(out_path, "w") as handle:
        handle.write("\n".join(lines) + "\n")
        handle.write("# fim\n")

    if scene_path:
        setup_view(scene)
        scene.update()
        bpy.ops.wm.save_as_mainfile(filepath=scene_path)


main()
