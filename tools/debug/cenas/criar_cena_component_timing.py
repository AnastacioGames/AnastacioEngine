# Cena de teste do horario do componente Python: awake() e start() no 1o quadro, update() a partir do 2o.
# Ordem de um quadro: sensores/controllers -> componentes -> actuators. O contador fica num controller, entao no
# 1o quadro ele ja vale 1 quando o componente roda.
# Uso: AnastacioEngine.exe -b -P criar_cena_component_timing.py -- <pasta de saida>
# Depois: AnastacioRuntime.exe <pasta>/component_timing.range ; resultado em <pasta>/component_timing_result.txt
import bpy
import os
import sys

out_dir = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else os.getcwd()

with open(os.path.join(out_dir, "timing_comp.py"), "w") as f:
    f.write('''import Range
from collections import OrderedDict

EVENTS = []


class Timing(Range.types.KX_PythonComponent):
    args = OrderedDict([("Tag", "x")])

    def awake(self, args):
        EVENTS.append(("awake", self.object["brick_frame"]))

    def start(self, args):
        EVENTS.append(("start", self.object["brick_frame"]))

    def update(self):
        EVENTS.append(("update", self.object["brick_frame"]))


class NoAwake(Range.types.KX_PythonComponent):
    args = OrderedDict()

    def start(self, args):
        EVENTS.append(("noawake.start", self.object["brick_frame"]))

    def update(self):
        EVENTS.append(("noawake.update", self.object["brick_frame"]))
''')

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.data.scenes[0]
scene.render.engine = 'BLENDER_GAME'
cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
scene.objects.link(cam)
scene.camera = cam

ob = bpy.data.objects.new("Probe", None)
scene.objects.link(ob)
scene.objects.active = ob
prop = ob.game.properties
bpy.ops.object.game_property_new(type='INT', name="brick_frame")

# Controller que conta os quadros: roda antes dos componentes no mesmo quadro.
text = bpy.data.texts.new("brick.py")
text.write('''import Range, os
import timing_comp
own = Range.logic.getCurrentController().owner
if own["brick_frame"] == 4:
    ev = timing_comp.EVENTS
    def first(name):
        return next((f for n, f in ev if n == name), None)
    lines = []
    def check(label, ok):
        lines.append(("OK " if ok else "FALHA ") + label)
    check("awake no 1o quadro", first("awake") == 1)
    check("start no 1o quadro (mesmo de awake)", first("start") == 1)
    check("update so a partir do 2o quadro", first("update") == 2)
    check("awake antes de start", [n for n, f in ev].index("awake") < [n for n, f in ev].index("start"))
    check("componente sem awake: start no 1o quadro", first("noawake.start") == 1)
    check("componente sem awake: update no 2o quadro", first("noawake.update") == 2)
    lines.append("eventos: %r" % ev)
    with open(os.path.join(Range.logic.expandPath("//"), "component_timing_result.txt"), "w") as f:
        f.write("\\n".join(lines) + "\\n")
    Range.logic.endGame()
own["brick_frame"] += 1
''')
bpy.ops.logic.sensor_add(type='ALWAYS', name='tick', object=ob.name)
bpy.ops.logic.controller_add(type='PYTHON', name='py', object=ob.name)
ob.game.sensors['tick'].use_pulse_true_level = True
ob.game.controllers['py'].text = text
ob.game.controllers['py'].link(sensor=ob.game.sensors['tick'])

sys.path.insert(0, out_dir)
bpy.ops.logic.python_component_register(component_name="timing_comp.Timing")
bpy.ops.logic.python_component_register(component_name="timing_comp.NoAwake")

path = os.path.join(out_dir, "component_timing.range")
bpy.ops.wm.save_as_mainfile(filepath=path)
print("salvo:", path, [c.name for c in ob.game.components])
