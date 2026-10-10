# Gera cooked_mesh.blend: confere se a malha montada do .cooked é idêntica à conversão normal.
# Uso: RangeEngine -b -P make_cooked_mesh_test.py -- <pasta>
# Rodar o RangeRuntime duas vezes em <pasta>/cooked_mesh.blend (a 1ª grava o .cooked, a 2ª usa);
# cada rodada acrescenta uma linha "checksum ..." em cooked_mesh.txt, que devem ser iguais.
#   Malha com 2 materiais (um wire), faces lisas e planas, 2 camadas de UV e 1 de cor, >10k loops.
import bpy, bmesh, sys, os

pasta = sys.argv[sys.argv.index("--") + 1]

for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
sc = bpy.context.scene
sc.render.engine = 'BLENDER_GAME'

bpy.ops.mesh.primitive_uv_sphere_add(segments=96, ring_count=64, location=(0, 0, 0))
ob = bpy.context.active_object
ob.name = ob.data.name = "Misto"
me = ob.data
me.uv_textures.new("Segunda")
me.vertex_colors.new("Cor")
bm = bmesh.new()
bm.from_mesh(me)
uv2 = bm.loops.layers.uv["Segunda"]
cor = bm.loops.layers.color["Cor"]
for f in bm.faces:
    f.smooth = (f.index % 3) != 0
    f.material_index = 1 if (f.index % 7) == 0 else 0
    for l in f.loops:
        l[uv2].uv = (l.vert.co.x * 0.5 + f.index * 0.001, l.vert.co.z)
        l[cor] = (abs(l.vert.co.x), (f.index % 5) / 4.0, 0.5, 1.0)
bm.to_mesh(me)
bm.free()
for nome, wire in (("Normal", False), ("Arame", True)):
    ma = bpy.data.materials.new(nome)
    ma.type = 'WIRE' if wire else 'SURFACE'
    me.materials.append(ma)

TESTE = r'''import bge
def checksum(cont):
    h = 0
    def mix(x):
        nonlocal_h[0] = (nonlocal_h[0] * 1000003 + hash(x)) & 0xffffffffffffffff
    nonlocal_h = [0]
    linhas = []
    for ob in bge.logic.getCurrentScene().objects:
        for mesh in ob.meshes:
            for m in range(mesh.numMaterials):
                n = mesh.getVertexArrayLength(m)
                for i in range(n):
                    v = mesh.getVertex(m, i)
                    mix((tuple(round(c, 5) for c in v.XYZ), tuple(round(c, 4) for c in v.normal), tuple(round(c, 4) for c in v.tangent),
                         tuple(round(c, 5) for uv in v.uvs for c in uv), tuple(round(c, 3) for c in v.color)))
                linhas.append("%s/%d: %d vertices" % (mesh.name, m, n))
            for p in range(mesh.numPolygons):
                poly = mesh.getPolygon(p)
                mix((poly.material_id, tuple(poly.getVertexIndex(k) for k in range(poly.getNumVertex()))))
            linhas.append("%s: %d polygons" % (mesh.name, mesh.numPolygons))
    # Raycasts contra a malha de física (BVH cozida ou construída).
    juiz = cont.owner
    import math
    acertos = 0
    for i in range(400):
        a, b = i * 0.37, (i % 20) * 0.157 - 1.5
        de = (6 * math.cos(a) * math.cos(b), 6 * math.sin(a) * math.cos(b), 6 * math.sin(b))
        ob, ponto, normal, poly = juiz.rayCast((0, 0, 0), de, 0, "", 0, 1, 1)
        if ob:
            acertos += 1
            mix((tuple(round(c, 4) for c in ponto), tuple(round(c, 3) for c in normal), poly.v1 if poly else -1))
    linhas.append("%d raios" % acertos)
    with open(bge.logic.expandPath("//cooked_mesh.txt"), "a") as fh:
        cozidas = [str(e) for e in bge.logic.getLoadLog() if "cooked" in str(e)]
        fh.write("checksum %016x | %s | %s\n" % (nonlocal_h[0], ", ".join(linhas), " ".join(cozidas)[:300]))
    bge.logic.endGame()
'''
txt = bpy.data.texts.new("checksum.py")
txt.write(TESTE)
bpy.ops.object.empty_add(location=(0, 0, 5))
juiz = bpy.context.active_object
juiz.name = "Juiz"
bpy.ops.logic.sensor_add(type='ALWAYS', object=juiz.name)
bpy.ops.logic.controller_add(type='PYTHON', object=juiz.name)
juiz.game.controllers[0].mode = 'MODULE'
juiz.game.controllers[0].module = "checksum.checksum"
juiz.game.sensors[0].link(juiz.game.controllers[0])
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(pasta, "cooked_mesh.blend"))
