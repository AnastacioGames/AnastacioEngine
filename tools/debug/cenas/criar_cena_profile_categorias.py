# Cena de teste das categorias do profile (getProfileInfo / painel Profile do Debug Mode).
# Um componente Python gasta ~2 ms por quadro: esse tempo tem de cair em "Components", nao em "Actuators",
# e as porcentagens de todas as categorias tem de somar 100.
# Uso: AnastacioEngine.exe -b -P criar_cena_profile_categorias.py -- <pasta de saida>
# Depois: AnastacioRuntime.exe <pasta>/profile_categorias.range ; resultado em <pasta>/profile_categorias_result.txt
import bpy
import os
import sys

out_dir = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else os.getcwd()

with open(os.path.join(out_dir, "burn_comp.py"), "w") as f:
    f.write('''import Range
import time
from collections import OrderedDict


class Burn(Range.types.KX_PythonComponent):
    args = OrderedDict()

    def start(self, args):
        pass

    def update(self):
        end = time.perf_counter() + 0.002
        while time.perf_counter() < end:
            pass
''')

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.data.scenes[0]
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.use_frame_rate = True
cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
scene.objects.link(cam)
scene.camera = cam

ob = bpy.data.objects.new("Probe", None)
scene.objects.link(ob)
scene.objects.active = ob
bpy.ops.object.game_property_new(type='INT', name="frame")

text = bpy.data.texts.new("probe.py")
text.write('''import Range, os


def tick(cont):
    own = cont.owner
    own["frame"] += 1
    if own["frame"] < 180:
        return
    info = Range.logic.getProfileInfo()
    lines = []

    def check(label, ok):
        lines.append(("OK " if ok else "FALHA ") + label)

    total = sum(v[1] for v in info.values())
    comp = info.get("Components", (0.0, 0.0))[0]
    act = info.get("Actuators", (9.0, 0.0))[0]
    check("categoria Components existe", "Components" in info)
    check("componente de 2 ms cai em Components (%.2f ms)" % comp, 1.5 <= comp <= 3.5)
    check("Actuators nao leva o tempo do componente (%.2f ms)" % act, act < 0.5)
    check("porcentagens somam 100 (%.2f)" % total, 99.0 <= total <= 101.0)
    for name, value in sorted(info.items(), key=lambda kv: -kv[1][0]):
        lines.append("%-28s %7.3f ms %6.2f %%" % (name, value[0], value[1]))
    with open(os.path.join(Range.logic.expandPath("//"), "profile_categorias_result.txt"), "w") as f:
        f.write("\\n".join(lines) + "\\n")
    Range.logic.endGame()
''')
bpy.ops.logic.sensor_add(type='ALWAYS', name='tick', object=ob.name)
bpy.ops.logic.controller_add(type='PYTHON', name='py', object=ob.name)
ob.game.sensors['tick'].use_pulse_true_level = True
ob.game.controllers['py'].mode = 'MODULE'
ob.game.controllers['py'].module = 'probe.tick'
ob.game.controllers['py'].link(sensor=ob.game.sensors['tick'])

sys.path.insert(0, out_dir)
bpy.ops.logic.python_component_register(component_name="burn_comp.Burn")

path = os.path.join(out_dir, "profile_categorias.range")
bpy.ops.wm.save_as_mainfile(filepath=path)
print("salvo:", path, [c.name for c in ob.game.components])
