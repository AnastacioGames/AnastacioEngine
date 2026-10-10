# Gera runtime_test.blend para scene.convertObject() e bge.logic.freeUnconvertedData().
# Uso: RangeEngine -b -P make_runtime_test.py -- out.blend
# Rodar no RangeRuntime; o resultado vai para runtime_results.txt.
#   Raiz (+ filho Raiz_Filho)  Convert off -> convertObject("Raiz") traz os dois
#   Carro (Convert on) com filho Piloto_Carro (off) -> convertObject mantém a posição relativa ao Carro
#   Pesado_0..3 (off)          -> freeUnconvertedData libera; depois convertObject/setObjectConvert recusam
#   Ajudante (Editor Only) e Raiz_Ajudante (Editor Only, filho de Raiz) -> nunca convertidos
import bpy, sys

out = sys.argv[sys.argv.index("--") + 1]
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
scene = bpy.context.scene
scene.layers = [i == 0 for i in range(20)]


def esfera(nome, loc, segs=256):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segs, ring_count=segs // 2, location=loc)
    ob = bpy.context.active_object
    ob.name = nome
    ob.data.name = nome
    return ob


def filho(ob, pai):
    ob.parent = pai
    ob.matrix_parent_inverse = pai.matrix_world.inverted()


raiz = esfera("Raiz", (0, 0, 0))
raiz_filho = esfera("Raiz_Filho", (0, 3, 0), 16)
filho(raiz_filho, raiz)
carro = esfera("Carro", (5, 0, 0), 16)
piloto = esfera("Piloto_Carro", (5, 0, 2), 16)
filho(piloto, carro)
pesados = [esfera("Pesado_%d" % i, (0, -5 - 3 * i, 0)) for i in range(4)]

# Filho de osso e filho de vértice (Convert off); a posição do Blender vai em propriedades.
arm = bpy.data.objects.new("Arm", bpy.data.armatures.new("Arm"))
arm.location = (-6, 0, 0)
arm.rotation_euler = (0, 0, 0.7)
scene.objects.link(arm)
scene.objects.active = arm
bpy.ops.object.mode_set(mode='EDIT')
b = arm.data.edit_bones.new("Osso")
b.head, b.tail = (0, 0, 0), (0, 0, 2)
bpy.ops.object.mode_set(mode='OBJECT')
no_osso = esfera("No_Osso", (-6, 1, 3), 16)
no_osso.parent, no_osso.parent_type, no_osso.parent_bone = arm, 'BONE', "Osso"
alvo = esfera("Alvo", (-10, 0, 0), 8)
no_vert = esfera("No_Vertice", (-10, 2, 1), 16)
no_vert.parent, no_vert.parent_type, no_vert.parent_vertices[0] = alvo, 'VERTEX', 0
scene.update()
# O BGE (KX_VertexParentRelation) segue só a origem do pai: esperado = origem do pai + local.
esperado = {no_osso: no_osso.matrix_world.translation, no_vert: alvo.location + no_vert.location}
for ob in (no_osso, no_vert):
    for eixo, v in zip("xyz", esperado[ob]):
        bpy.ops.object.game_property_new({"object": ob, "active_object": ob}, type='FLOAT', name=eixo)
        ob.game.properties[eixo].value = v

for ob in [raiz, raiz_filho, piloto, no_osso, no_vert] + pesados:
    ob.convert_object = False
ajudante = esfera("Ajudante", (0, 10, 0), 8)
raiz_ajudante = esfera("Raiz_Ajudante", (0, 6, 0), 8)
filho(raiz_ajudante, raiz)
for ob in (ajudante, raiz_ajudante):
    ob.game_load_mode = 'EDITOR_ONLY'
assert not ajudante.convert_object

txt = bpy.data.texts.new("teste.py")
txt.write('''import bge, ctypes, ctypes.wintypes
log = []

def rss():
    class PMC(ctypes.Structure):
        _fields_ = [("cb", ctypes.wintypes.DWORD), ("PageFaultCount", ctypes.wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
    c = PMC(); c.cb = ctypes.sizeof(c)
    ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(c), c.cb)
    return c.PagefileUsage / 1048576.0

def tenta(nome, f):
    try:
        r = f()
        log.append("%s: ok %r" % (nome, r))
        return r
    except Exception as e:
        log.append("%s: %s: %s" % (nome, type(e).__name__, e))

sc = bge.logic.getCurrentScene()
log.append("inicio ativos=%s" % sorted(o.name for o in sc.objects))
log.append("unconvertedObjects=%s" % sorted(sc.unconvertedObjects))
log.append("loadLog convert=%s" % [e["detail"].split(", meshes")[0] for e in bge.logic.getLoadLog() if e["stage"] == "convert"])
tenta("convertObject(Ajudante)", lambda: sc.convertObject("Ajudante"))
tenta("setObjectConvert(Ajudante)", lambda: bge.logic.setObjectConvert(sc.name, "Ajudante", True))
r = tenta("convertObject(Raiz)", lambda: sc.convertObject("Raiz"))
if r:
    log.append("  Raiz ativo=%s filhos=%s" % (r in sc.objects, sorted(c.name for c in r.children)))
carro = sc.objects["Carro"]
carro.worldPosition.x += 10.0
carro.applyRotation((0, 0, 1.5708))
p = tenta("convertObject(Piloto_Carro)", lambda: sc.convertObject("Piloto_Carro"))
if p:
    rel = carro.worldTransform.inverted() * p.worldTransform
    log.append("  pai=%s pos_rel=%s (esperado ~(0,0,2))" % (p.parent and p.parent.name, tuple(round(v, 3) for v in rel.translation)))
for nome in ("No_Osso", "No_Vertice"):
    o = tenta("convertObject(%s)" % nome, lambda: sc.convertObject(nome))
    if o:
        log.append("  pai=%s pos=%s esperado=%s" % (o.parent and o.parent.name,
                   tuple(round(v, 3) for v in o.worldPosition), tuple(round(o[e], 3) for e in "xyz")))
tenta("convertObject(Raiz) de novo", lambda: sc.convertObject("Raiz").name)
tenta("convertObject(Inexistente)", lambda: sc.convertObject("Inexistente"))
antes = rss()
livre = tenta("freeUnconvertedData", lambda: bge.logic.freeUnconvertedData(sc.name))
log.append("  liberado=%.1f MB, commit do processo %.1f -> %.1f MB" % ((livre or 0) / 1048576.0, antes, rss()))
tenta("convertObject(Pesado_0) apos free", lambda: sc.convertObject("Pesado_0"))
tenta("setObjectConvert(Pesado_1) apos free", lambda: bge.logic.setObjectConvert(sc.name, "Pesado_1", True))
tenta("freeUnconvertedData de novo", lambda: bge.logic.freeUnconvertedData(sc.name))
log.append("fim ativos=%s" % sorted(o.name for o in sc.objects))
log.append("fim unconvertedObjects=%s" % sorted(sc.unconvertedObjects))
with open(bge.logic.expandPath("//runtime_results.txt"), "w") as f:
    f.write("\\n".join(log) + "\\n")
bge.logic.endGame()
''')
logica = bpy.data.objects.new("Logica", None)
scene.objects.link(logica)
scene.objects.active = logica
bpy.ops.logic.sensor_add(type='ALWAYS', object=logica.name)
bpy.ops.logic.controller_add(type='PYTHON', object=logica.name)
logica.game.sensors[0].link(logica.game.controllers[0])
logica.game.controllers[0].text = txt
bpy.ops.wm.save_as_mainfile(filepath=out)
