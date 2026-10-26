"""Teste do Auto Static Batch (Scene > Level of Detail > Auto Static Batch), sem janela.

Gera duas cenas: auto_on.range (opção ligada) e auto_off.range (desligada). Cada uma tem 6 cubos simples
(mesmo material) e 6 que devem ficar fora do lote: com logic brick, com cor de objeto, com pai, animado,
espelhado (escala negativa) e com Object Info no material (Random por objeto).
A saída do lote de um objeto movido acontece no desenho (UpdateBuckets), que o --server não faz;
por isso o teste só confere quem entra no lote.

    AnastacioEngine -b --python tools/debug/cenas/criar_teste_auto_static_batch.py -- PASTA
    set ASB_OUT=PASTA/on.txt&& AnastacioRuntime --server PASTA/auto_on.range
    set ASB_OUT=PASTA/off.txt&& AnastacioRuntime --server PASTA/auto_off.range

Cada .txt termina em "RESULTADO OK" ou "RESULTADO FALHOU".
"""
import bpy, sys, os
out = sys.argv[sys.argv.index("--") + 1]

TEST = '''import Range, os, traceback
try:
    sc = Range.logic.getCurrentScene()
    own = Range.logic.getCurrentController().owner
    own["f"] = own.get("f", 0) + 1
    f = own["f"]
    auto = own["auto"]
    def batched(n): return sc.objects[n].batchGroup is not None
    if f == 3:
        log = []
        ok = True
        for i in range(6):
            n = "Plain%d" % i
            log.append("%s lote=%s" % (n, batched(n)))
            ok = ok and batched(n) == auto
        for n in ("WithLogic", "WithColor", "Child", "Animated", "Mirrored", "ObjInfo", "ObjInfo2"):
            log.append("%s lote=%s" % (n, batched(n)))
            ok = ok and not batched(n)
        log.append("Marked lote=%s" % batched("Marked"))
        ok = ok and batched("Marked") == auto  # marcado sozinho so forma lote junto com os automaticos
        Range.logic.globalDict["log"] = log
        Range.logic.globalDict["ok"] = ok
        open(os.environ["ASB_OUT"], "w").write(chr(10).join(log + ["RESULTADO " + ("OK" if ok else "FALHOU")]))
        Range.logic.endGame()
except Exception:
    open(os.environ["ASB_OUT"], "w").write(traceback.format_exc())
    Range.logic.endGame()
'''

def build(auto):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene; sc.render.engine = 'BLENDER_GAME'
    sc.game_settings.use_auto_static_batch = auto
    mat = bpy.data.materials.new("Shared")
    def cube(name, x, y=0):
        bpy.ops.mesh.primitive_cube_add(location=(x, y, 0))
        ob = bpy.context.object; ob.name = name
        ob.data.materials.append(mat); ob.game.physics_type = 'STATIC'
        return ob
    for i in range(6):
        cube("Plain%d" % i, i * 3)
    logic = cube("WithLogic", 0, 4)
    sc.objects.active = logic
    bpy.ops.logic.sensor_add(type='ALWAYS', name="S", object=logic.name)
    color = cube("WithColor", 3, 4); color.color = (1, 0, 0, 1)
    child = cube("Child", 6, 4); child.parent = sc.objects["Plain0"]
    anim = cube("Animated", 9, 4)
    anim.keyframe_insert("location", frame=1)
    cube("Marked", 12, 4).use_static_batch = True
    cube("Mirrored", 15, 4).scale.x = -1
    oi = cube("ObjInfo", 18, 4)
    mi = bpy.data.materials.new("ObjInfoMat"); mi.use_nodes = True
    mi.node_tree.nodes.new('ShaderNodeObjectInfo')
    oi.data = oi.data.copy(); oi.data.materials[0] = mi
    oi2 = cube("ObjInfo2", 21, 4); oi2.data = oi.data  # dois com o mesmo material: lote possível sem o filtro
    cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera")); sc.objects.link(cam)
    cam.location = (8, -20, 5); sc.camera = cam
    sc.objects.active = cam
    bpy.ops.object.game_property_new(type='BOOL', name="auto")
    cam.game.properties["auto"].value = auto
    t = bpy.data.texts.new("t.py"); t.write(TEST)
    bpy.ops.logic.sensor_add(type='ALWAYS', name="A", object=cam.name)
    s = cam.game.sensors["A"]; s.use_pulse_true_level = True
    bpy.ops.logic.controller_add(type='PYTHON', name="P", object=cam.name)
    c = cam.game.controllers["P"]; c.text = t; s.link(c)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, "auto_%s.range" % ("on" if auto else "off")),
                                check_existing=False)

build(True)
build(False)
