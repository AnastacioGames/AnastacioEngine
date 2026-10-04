"""Gera um .range que testa a API Python de atrito anisotrópico.

Run with:  RangeEngine -b --python tools/create_anisotropic_friction_test.py -- <output.range>
Depois:    RangeRuntime <output.range>
Imprime ANISO_FRICTION_TEST PASS|FAIL ... e grava em aniso_result.txt ao lado do .range.

Duas caixas deslizam em X com a mesma velocidade sobre um chão com atrito. Na caixa "Ski" o
script liga gameOb.anisotropicFriction com coeficientes (0, 1, 1): ela não perde velocidade em X.
A caixa "Plain" tem atrito normal e perde bem mais velocidade.
"""

import sys

import bpy

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if not argv:
    raise SystemExit("uso: ... -- <output.range>")

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'


def box(name, location, size):
    bpy.ops.mesh.primitive_cube_add(location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = size
    return obj


ground = box("Ground", (0.0, 0.0, -0.5), (50.0, 50.0, 0.5))
ground.game.physics_type = 'STATIC'

for name, y in (("Ski", -3.0), ("Plain", 3.0)):
    obj = box(name, (0.0, y, 0.5), (0.5, 0.5, 0.5))
    obj.game.physics_type = 'RIGID_BODY'
    obj.game.mass = 1.0

camera_data = bpy.data.cameras.new("Cam")
camera = bpy.data.objects.new("Cam", camera_data)
scene.objects.link(camera)
camera.location = (0.0, -25.0, 10.0)
camera.rotation_euler = (1.2, 0.0, 0.0)
scene.camera = camera

code = '''
from bge import logic

failures = []
own = logic.getCurrentController().owner
scene = own.scene
ski = scene.objects["Ski"]
plain = scene.objects["Plain"]
own["t"] = own.get("t", 0) + 1
t = own["t"]

def check(cond, tag):
    if not cond:
        failures.append(tag)

if t == 1:
    ski.friction = 1.0
    plain.friction = 1.0
    check(ski.anisotropicFriction is False, "default_off")
    check(list(ski.anisotropicFrictionCoefficients) == [1.0, 1.0, 1.0], "default_coef")
    ski.anisotropicFrictionCoefficients = [0.0, 1.0, 1.0]
    ski.anisotropicFriction = True
    check(ski.anisotropicFriction is True, "set_on")
    check(list(ski.anisotropicFrictionCoefficients) == [0.0, 1.0, 1.0], "set_coef")
    try:
        ski.anisotropicFrictionCoefficients = [-1.0, 1.0, 1.0]
        failures.append("negative_accepted")
    except AttributeError:
        pass
    own["fail"] = " ".join(failures)
elif t == 20:
    for obj in (ski, plain):
        obj.setLinearVelocity([6.0, 0.0, 0.0], False)
elif t == 80:
    vski = ski.getLinearVelocity(False)[0]
    vplain = plain.getLinearVelocity(False)[0]
    failures = own["fail"].split() if own["fail"] else []
    check(vski > 4.0, "ski_slowed(%.2f)" % vski)
    check(vplain < vski - 1.5, "plain_slid(%.2f)" % vplain)
    ski.anisotropicFriction = False
    check(ski.anisotropicFriction is False, "set_off")
    line = "ANISO_FRICTION_TEST " + ("PASS" if not failures else "FAIL " + " ".join(failures))
    line += " vski=%.2f vplain=%.2f" % (vski, vplain)
    print(line)
    with open(logic.expandPath("//aniso_result.txt"), "w") as f:
        f.write(line + "\\n")
    logic.endGame()
'''

checker = bpy.data.objects.new("Checker", None)
scene.objects.link(checker)
scene.objects.active = checker
text = bpy.data.texts.new("aniso_check.py")
text.write(code)
bpy.ops.logic.sensor_add(type='ALWAYS', name="Frame", object=checker.name)
checker.game.sensors["Frame"].use_pulse_true_level = True
bpy.ops.logic.controller_add(type='PYTHON', name="Check", object=checker.name)
checker.game.controllers["Check"].text = text
checker.game.sensors["Frame"].link(checker.game.controllers["Check"])

bpy.ops.wm.save_as_mainfile(filepath=argv[0])
print("saved", argv[0])
