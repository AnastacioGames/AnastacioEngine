# Gera cena de teste para o registro de properties do tipo Timer em addObject/endObject
# (KX_Scene::AddReplicaObject / RemoveObject iteram o map de properties direto).
# Uso: RangeEngine.exe -b --python gen_timer_props.py  e depois  RangeRuntime.exe timer_props.blend
# Resultado em timer_props_log.txt (linha final "PASS" ou "FAIL ...").
import bpy
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "timer_props.blend")

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'

bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0))
tmpl = bpy.context.active_object
tmpl.name = "Template"
tmpl.layers = [i == 1 for i in range(20)]
scene.objects.active = tmpl
# Muitas properties comuns intercaladas com timers, para cobrir posicoes variadas no map.
for i in range(40):
    bpy.ops.object.game_property_new(type='INT', name="p%02d" % i)
for name in ("a_timer", "m_timer", "z_timer"):
    bpy.ops.object.game_property_new(type='TIMER', name=name)

cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
cam.location = (0, -15, 3)
cam.rotation_euler = (1.4, 0, 0)
scene.objects.link(cam)
scene.camera = cam

script = bpy.data.texts.new("timer_test.py")
script.write(r'''import bge, traceback
LOG = bge.logic.expandPath("//timer_props_log.txt")
def log(msg):
    with open(LOG, "a") as f:
        f.write(msg + "\n")
def check(cond, msg):
    if not cond:
        raise AssertionError(msg)

own = bge.logic.getCurrentController().owner
sc = bge.logic.getCurrentScene()
try:
    n = own.get("n", 0)
    own["n"] = n + 1
    if n == 0:
        open(LOG, "w").close()
        own["keep"] = sc.addObject("Template", own, 0)
        # Cria e destroi varias replicas: exercita registro e remocao dos timers.
        for _ in range(200):
            sc.addObject("Template", own, 0).endObject()
        log("setup ok")
    elif n == 25:
        k = own["keep"]
        for name in ("a_timer", "m_timer", "z_timer"):
            check(k[name] > 0.3, "%s nao avancou: %r" % (name, k[name]))
        check(k["p00"] == 0 and k["p39"] == 0, "property comum alterada")
        log("PASS")
        bge.logic.endGame()
except Exception:
    log("FAIL " + traceback.format_exc())
    bge.logic.endGame()
''')
empty = bpy.data.objects.new("Tester", None)
scene.objects.link(empty)
scene.objects.active = empty
bpy.ops.logic.sensor_add(type='ALWAYS', object="Tester")
bpy.ops.logic.controller_add(type='PYTHON', object="Tester")
sens = empty.game.sensors[-1]
sens.use_pulse_true_level = True
cont = empty.game.controllers[-1]
cont.text = script
sens.link(cont)

scene.layers = [i == 0 for i in range(20)]
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print("SAVED", OUT)
