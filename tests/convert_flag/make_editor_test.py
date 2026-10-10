# Gera editor_test.blend: confere o Play do editor (player embutido).
# Uso: RangeEngine -b -P make_editor_test.py -- editor_test.blend
# Conferência automática: RangeEngine editor_test.blend -P run_editor_test.py
# Ou à mão: abrir, apertar P, e ver que as caixas Convert de A (off), B (on) e C (off)
# não mudaram; editor_results.txt mostra o que o jogo viu.
import bpy, sys

out = sys.argv[sys.argv.index("--") + 1]
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
menu = bpy.context.scene
menu.name = "Menu"
fase = bpy.data.scenes.new("Fase")
for sc in (menu, fase):
    sc.render.engine = 'BLENDER_GAME'


def logica(sc, nome, corpo):
    txt = bpy.data.texts.new(nome + ".py")
    txt.write(corpo)
    ob = bpy.data.objects.new(nome, None)
    sc.objects.link(ob)
    ctx = {"object": ob, "active_object": ob, "edit_object": None}
    bpy.ops.logic.sensor_add(ctx, type='ALWAYS', object=ob.name)
    bpy.ops.logic.controller_add(ctx, type='PYTHON', object=ob.name)
    ob.game.sensors[0].link(ob.game.controllers[0])
    ob.game.controllers[0].text = txt


for i, (nome, conv) in enumerate((("A", False), ("B", True), ("C", False))):
    me = bpy.data.meshes.new(nome)
    me.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [], [(0, 1, 2)])
    ob = bpy.data.objects.new(nome, me)
    ob.location = (i * 3, 0, 0)
    ob.convert_object = conv
    fase.objects.link(ob)

cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
cam.location = (3, -10, 2)
cam.rotation_euler = (1.5, 0, 0)
fase.objects.link(cam)
fase.camera = cam
cam2 = bpy.data.objects.new("CamMenu", bpy.data.cameras.new("CamMenu"))
menu.objects.link(cam2)
menu.camera = cam2

logica(menu, "MenuLogica", '''import bge
bge.logic.log = ["menu: A=%s B=%s" % (bge.logic.getObjectConvert("Fase", "A"), bge.logic.getObjectConvert("Fase", "B"))]
bge.logic.setObjectConvert("Fase", "A", True)
bge.logic.setObjectConvert("Fase", "B", False)
bge.logic.getCurrentScene().replace("Fase")
''')
logica(fase, "FaseLogica", '''import bge, os
pula = os.environ.get("EDITOR_TEST_SKIP", "")
log = bge.logic.log
sc = bge.logic.getCurrentScene()
log.append("fase: ativos=%s" % sorted(o.name for o in sc.objects if len(o.name) == 1))
try:
    if "convert" in pula: raise RuntimeError("pulado")
    log.append("convertObject(C): ok %s" % sc.convertObject("C").name)
except Exception as e:
    log.append("convertObject(C): %s: %s" % (type(e).__name__, e))
try:
    if "free" in pula: raise RuntimeError("pulado")
    log.append("freeUnconvertedData: NAO RECUSOU %r" % bge.logic.freeUnconvertedData("Fase"))
except Exception as e:
    log.append("freeUnconvertedData: %s: %s" % (type(e).__name__, e))
log.append("fase: ativos=%s" % sorted(o.name for o in sc.objects if len(o.name) == 1))
with open(bge.logic.expandPath("//editor_results.txt"), "w") as f:
    f.write("\\n".join(log) + "\\n")
bge.logic.endGame()
''')
bpy.context.screen.scene = menu
bpy.ops.wm.save_as_mainfile(filepath=out)
