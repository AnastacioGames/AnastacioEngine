# Gera vs_convert.blend e vs_lib.blend: os mesmos objetos carregados por scene.convertObject() e por LibLoad.
# Uso: RangeEngine -b -P make_vs_libload.py -- <pasta>
# Rodar no RangeRuntime com VS_MODE=convert | lib | libasync; cada rodada acrescenta uma linha em vs_results.txt.
#   8 esferas de ~130k triângulos (física estática Convex Hull) e 4 terrenos de 12,8k triângulos (Triangle Mesh)
import bpy, bmesh, sys, os, math

pasta = sys.argv[sys.argv.index("--") + 1]
NOMES = ["Pesado_%d" % i for i in range(8)] + ["Terreno_%d" % i for i in range(4)]


def limpa():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    # Sem isso as malhas novas viram "Terreno_0.001" e o objeto herda o nome.
    for me in list(bpy.data.meshes):
        bpy.data.meshes.remove(me)
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_GAME'
    sc.layers = [i == 0 for i in range(20)]
    return sc


def objetos(sc, convert):
    for i in range(8):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=512, ring_count=128, location=(i * 3 - 10, 20, 2))
        ob = bpy.context.active_object
        ob.name = ob.data.name = "Pesado_%d" % i
        ob.game.physics_type = 'STATIC'
        ob.game.use_collision_bounds = True
        ob.game.collision_bounds_type = 'CONVEX_HULL'
        ob.game_load_mode = 'SCENE' if convert else 'ON_DEMAND'
    for i in range(4):
        me = bpy.data.meshes.new("Terreno_%d" % i)
        bm = bmesh.new()
        bmesh.ops.create_grid(bm, x_segments=80, y_segments=80, size=4.0)
        for v in bm.verts:
            v.co.z = 0.4 * math.sin(v.co.x * (1.3 + i * 0.37)) * math.cos(v.co.y * (0.9 + i * 0.21))
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new(me.name, me)
        ob.location = (i * 10 - 15, 0, 0)
        ob.game.physics_type = 'STATIC'
        ob.game.use_collision_bounds = True
        ob.game.collision_bounds_type = 'TRIANGLE_MESH'
        ob.game_load_mode = 'SCENE' if convert else 'ON_DEMAND'
        sc.objects.link(ob)


sc = limpa()
objetos(sc, True)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(pasta, "vs_lib.blend"))

TESTE = r'''import bge, os, time, traceback, ctypes, ctypes.wintypes
NOMES = @NOMES@

def mem():
    class PMC(ctypes.Structure):
        _fields_ = [("cb", ctypes.wintypes.DWORD), ("PageFaultCount", ctypes.wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
    c = PMC()
    c.cb = ctypes.sizeof(c)
    k32 = ctypes.windll.kernel32
    k32.GetCurrentProcess.restype = ctypes.wintypes.HANDLE
    psapi = ctypes.windll.psapi
    psapi.GetProcessMemoryInfo.argtypes = (ctypes.wintypes.HANDLE, ctypes.c_void_p, ctypes.wintypes.DWORD)
    psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(c), c.cb)
    return c.PagefileUsage / 1048576.0

def grava(linha):
    with open(bge.logic.expandPath("//vs_results.txt"), "a") as fh:
        fh.write(linha + "\n")

def main(cont):
    # Qualquer erro encerra o jogo e vai para vs_results.txt, em vez de deixar a janela aberta.
    try:
        passo()
    except Exception:
        grava("ERRO %s: %s" % (os.environ.get("VS_MODE", "convert"), traceback.format_exc()))
        bge.logic.endGame()

def passo():
    g = bge.logic.globalDict
    sc = bge.logic.getCurrentScene()
    modo = os.environ.get("VS_MODE", "convert")
    f = g.get("f", 0)
    g["f"] = f + 1
    if f == 5:
        g["m0"] = mem()
        bge.logic.getLoadLog(clear=True)
        g["t0"] = time.perf_counter()
        if modo == "convert":
            for n in NOMES:
                sc.convertObject(n)
        else:
            g["lib"] = bge.logic.LibLoad(bge.logic.expandPath("//vs_lib.blend"), "Scene",
                                         asynchronous=(modo == "libasync"))
        g["chamada"] = (time.perf_counter() - g["t0"]) * 1000.0
        g["f0"] = f
    elif f > 5 and (modo == "convert" or g["lib"].finished):
        pronto = (time.perf_counter() - g["t0"]) * 1000.0
        m1 = mem()
        ativos = sum(1 for n in NOMES if n in sc.objects)
        livre = bge.logic.freeUnconvertedData(sc.name) / 1048576.0 if modo == "convert" else 0.0
        grava("%-9s chamada %7.1f ms | pronto %7.1f ms em %3d frames | memoria +%6.1f MB | ativos %d/%d | "
              "freeUnconverted %5.1f MB | commit final %6.1f MB"
              % (modo, g["chamada"], pronto, f - g["f0"], m1 - g["m0"], ativos, len(NOMES), livre, mem()))
        # Tempo por etapa da conversão (o CM_Message "[Load]" não chega ao stdout do runtime).
        for e in bge.logic.getLoadLog():
            grava("  log %-28s %8.1f ms  %s" % (e["stage"], e["ms"], e["detail"]))
        bge.logic.endGame()
    elif f > 1200:
        raise RuntimeError("nao terminou em 1200 frames")
'''.replace("@NOMES@", repr(NOMES))

sc = limpa()
objetos(sc, False)
cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
cam.location = (0, -40, 30)
cam.rotation_euler = (0.9, 0, 0)
sc.objects.link(cam)
sc.camera = cam
bpy.data.texts.new("vs.py").write(TESTE)
logica = bpy.data.objects.new("Logica", None)
sc.objects.link(logica)
sc.objects.active = logica
bpy.ops.logic.sensor_add(type='ALWAYS', object=logica.name)
bpy.ops.logic.controller_add(type='PYTHON', object=logica.name)
s, c = logica.game.sensors[0], logica.game.controllers[0]
s.use_pulse_true_level = True
c.mode = 'MODULE'
c.module = "vs.main"
s.link(c)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(pasta, "vs_convert.blend"))
print("ok")
