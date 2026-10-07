# Gera runtime_test.blend para scene.convertObject() e bge.logic.freeUnconvertedData().
# Uso: RangeEngine -b -P make_runtime_test.py -- out.blend
# Rodar no RangeRuntime; o resultado vai para runtime_results.txt.
#   Raiz (+ filho Raiz_Filho)  Convert off -> convertObject("Raiz") traz os dois
#   Carro (Convert on) com filho Piloto_Carro (off) -> convertObject mantém a posição relativa ao Carro
#   Pesado_0..3 (off)          -> freeUnconvertedData libera; depois convertObject/setObjectConvert recusam
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
for ob in [raiz, raiz_filho, piloto] + pesados:
    ob.convert_object = False

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
r = tenta("convertObject(Raiz)", lambda: sc.convertObject("Raiz"))
if r:
    log.append("  Raiz ativo=%s filhos=%s" % (r in sc.objects, [c.name for c in r.children]))
carro = sc.objects["Carro"]
carro.worldPosition.x += 10.0
carro.applyRotation((0, 0, 1.5708))
p = tenta("convertObject(Piloto_Carro)", lambda: sc.convertObject("Piloto_Carro"))
if p:
    rel = carro.worldTransform.inverted() * p.worldTransform
    log.append("  pai=%s pos_rel=%s (esperado ~(0,0,2))" % (p.parent and p.parent.name, tuple(round(v, 3) for v in rel.translation)))
tenta("convertObject(Raiz) de novo", lambda: sc.convertObject("Raiz").name)
tenta("convertObject(Inexistente)", lambda: sc.convertObject("Inexistente"))
antes = rss()
livre = tenta("freeUnconvertedData", lambda: bge.logic.freeUnconvertedData(sc.name))
log.append("  liberado=%.1f MB, commit do processo %.1f -> %.1f MB" % ((livre or 0) / 1048576.0, antes, rss()))
tenta("convertObject(Pesado_0) apos free", lambda: sc.convertObject("Pesado_0"))
tenta("setObjectConvert(Pesado_1) apos free", lambda: bge.logic.setObjectConvert(sc.name, "Pesado_1", True))
tenta("freeUnconvertedData de novo", lambda: bge.logic.freeUnconvertedData(sc.name))
log.append("fim ativos=%s" % sorted(o.name for o in sc.objects))
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
