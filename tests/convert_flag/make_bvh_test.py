# Gera bvh_test.blend (+ bvh_lib.blend) para conferir a BVH de malha de triângulos construída em paralelo.
# Uso: RangeEngine -b -P make_bvh_test.py -- <pasta>
# Rodar duas vezes no RangeRuntime, com e sem RANGE_NO_BVH_BATCH=1: bvh_results.txt tem que sair idêntico.
#   - malhas únicas, cópias Shift+D (mesmo conteúdo, malha separada) e duplicatas ligadas, uma com escala
#   - 900 raios em grade (objeto, ponto, normal) e 6 bolas dinâmicas caindo nas malhas por 120 frames
#   - as mesmas malhas via LibLoad assíncrono (BVH construída na thread do LibLoad)
import bpy, bmesh, sys, os

pasta = sys.argv[sys.argv.index("--") + 1]


def limpa():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_GAME'
    sc.layers = [i == 0 for i in range(20)]
    return sc


def terreno(nome, seed, n=80):
    # grade ondulada: cada seed dá um conteúdo diferente
    import math
    me = bpy.data.meshes.new(nome)
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=n, y_segments=n, size=4.0)
    for v in bm.verts:
        v.co.z = 0.4 * math.sin(v.co.x * (1.3 + seed * 0.37)) * math.cos(v.co.y * (0.9 + seed * 0.21))
    bm.to_mesh(me)
    bm.free()
    return me


def malha(sc, nome, me, loc, scale=1.0):
    ob = bpy.data.objects.new(nome, me)
    ob.location = loc
    ob.scale = (scale, scale, scale)
    ob.game.physics_type = 'STATIC'
    ob.game.use_collision_bounds = True
    ob.game.collision_bounds_type = 'TRIANGLE_MESH'
    sc.objects.link(ob)
    return ob


def malhas(sc, prefixo, y):
    base = [terreno("%sT%d" % (prefixo, i), i) for i in range(4)]
    for i, me in enumerate(base):
        malha(sc, "%sUnica_%d" % (prefixo, i), me, (i * 10 - 15, y, 0))
    # Shift+D: malha separada com o mesmo conteúdo
    malha(sc, "%sCopia_0" % prefixo, base[0].copy(), (-15, y + 10, 0))
    malha(sc, "%sCopia_1" % prefixo, base[1].copy(), (-5, y + 10, 0))
    # Alt+D: mesma malha
    malha(sc, "%sLigada_0" % prefixo, base[2], (5, y + 10, 0))
    malha(sc, "%sLigada_1" % prefixo, base[3], (15, y + 10, 0), scale=1.5)


# Biblioteca para o LibLoad assíncrono
sc = limpa()
malhas(sc, "L", 60)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(pasta, "bvh_lib.blend"))

sc = limpa()
malhas(sc, "", 0)
for i in range(6):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=6, size=0.5, location=(i * 6 - 15, (i % 2) * 10, 3))
    ob = bpy.context.active_object
    ob.name = "Bola_%d" % i
    ob.game.physics_type = 'RIGID_BODY'
    ob.game.collision_bounds_type = 'SPHERE'
    ob.game.use_collision_bounds = True

cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
cam.location = (0, -40, 30)
cam.rotation_euler = (0.9, 0, 0)
sc.objects.link(cam)
sc.camera = cam

txt = bpy.data.texts.new("bvh.py")
txt.write('''import bge, time
from mathutils import Vector

def r(v):
    return "(%.4f %.4f %.4f)" % tuple(v)

def raios(sc, y0, log):
    for i in range(30):
        for j in range(30):
            ini = Vector((-22 + i * 1.5, y0 - 4 + j * 0.8, 10))
            ob, pt, nor = sc.objects["Logica"].rayCast(ini - Vector((0, 0, 20)), ini, 0)
            log.append("raio %d %d: %s %s %s" % (i, j, ob.name if ob else "-", r(pt) if ob else "", r(nor) if ob else ""))

def main(cont):
    g = bge.logic.globalDict
    sc = bge.logic.getCurrentScene()
    f = g.get("f", 0)
    g["f"] = f + 1
    if f == 0:
        g["log"] = []
        g["lib"] = bge.logic.LibLoad(bge.logic.expandPath("//bvh_lib.blend"), "Scene", asynchronous=True)
    if f == 30:
        # forma recriada depois do load: Unica_2 passa a colidir com a malha da Unica_3
        sc.objects["Unica_2"].reinstancePhysicsMesh(sc.objects["Unica_3"])
    if f == 120:
        log = g["log"]
        raios(sc, 0, log)
        raios(sc, 10, log)
        for nome in sorted(o.name for o in sc.objects if o.name.startswith("Bola_")):
            log.append("%s %s" % (nome, r(sc.objects[nome].worldPosition)))
    if f >= 120 and g["lib"].finished:
        log = g["log"]
        raios(sc, 60, log)
        raios(sc, 70, log)
        with open(bge.logic.expandPath("//bvh_results.txt"), "w") as fh:
            fh.write("\\n".join(log) + "\\n")
        with open(bge.logic.expandPath("//bvh_load.txt"), "a") as fh:
            for e in bge.logic.getLoadLog():
                if e["stage"] == "convert":
                    fh.write("%s %.0f ms: %s\\n" % (e["scene"], e["ms"], e["detail"]))
        bge.logic.endGame()
''')
logica = bpy.data.objects.new("Logica", None)
sc.objects.link(logica)
sc.objects.active = logica
bpy.ops.logic.sensor_add(type='ALWAYS', object=logica.name)
bpy.ops.logic.controller_add(type='PYTHON', object=logica.name)
s, c = logica.game.sensors[0], logica.game.controllers[0]
s.use_pulse_true_level = True
c.mode = 'MODULE'
c.module = "bvh.main"
s.link(c)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(pasta, "bvh_test.blend"))
print("ok")
