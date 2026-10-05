# Gera cena de teste para KX_GameObject.life (tempo de vida nativo, sem property ::timebomb).
# Uso: RangeEngine.exe -b --python gen_object_life.py  e depois  RangeRuntime.exe object_life.blend
# Resultado em object_life_log.txt (linha final "PASS" ou "FAIL ...").
import bpy
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "object_life.blend")

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'

LAYER2 = [i == 1 for i in range(20)]

bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0))
tmpl = bpy.context.active_object
tmpl.name = "Template"
tmpl.layers = LAYER2

cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
cam.location = (0, -15, 3)
cam.rotation_euler = (1.4, 0, 0)
scene.objects.link(cam)
scene.camera = cam

script = bpy.data.texts.new("life_test.py")
script.write(r'''import bge, traceback
LOG = bge.logic.expandPath("//object_life_log.txt")
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
        tmpl = sc.objectsInactive["Template"]

        a = sc.addObject("Template", own, 10)
        check(abs(a.life - 10.0) < 1e-3, "life inicial %r" % a.life)
        check("::timebomb" not in a.getPropertyNames(), "::timebomb vazou")
        own["a"] = a

        b = sc.addObject("Template", own, 0)
        check(b.life is None, "objeto permanente deveria ter life None, %r" % b.life)
        b.life = 5
        check(abs(b.life - 5.0) < 1e-3, "life setado %r" % b.life)
        own["b"] = b

        c = sc.addObject("Template", own, 5)
        c.life = None
        check(c.life is None, "life=None deveria cancelar")
        own["c"] = c

        d = sc.addObject("Template", own, 0)
        check(d.life is None, "objeto sem tempo recebeu life")
        own["d"] = d

        for bad, exc in ((-1, ValueError), ("x", TypeError)):
            try:
                a.life = bad
                raise AssertionError("aceitou life=%r" % bad)
            except exc:
                pass
        try:
            tmpl.life = 3
            raise AssertionError("aceitou life em objeto inativo")
        except ValueError:
            pass
        check(tmpl.life is None, "template ficou com life")

        a.life = a.life
        check(abs(a.life - 10.0) < 1e-3, "ida e volta mudou o valor %r" % a.life)
        log("setup ok")
    elif n == 30:
        check(own["a"].invalid, "a (10 frames) nao morreu")
        check(own["b"].invalid, "b (life=5 via Python) nao morreu")
        check(not own["c"].invalid, "c (life=None) morreu")
        check(not own["d"].invalid, "d (permanente) morreu")
        check(not sc.objectsInactive["Template"].invalid, "template sumiu")
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
