# Gera uma cena de teste para Range.logic.preloadScene, o "Preload" do atuador Add Scene e o "Keep" do
# Remove Scene / scene.end(keep=True).
# Uso: AnastacioEngine.exe -b -P criar_cena_preload_keep.py -- <pasta de saida>
# Depois: AnastacioRuntime.exe <pasta>/preload_keep.range ; o resultado vai para <pasta>/preload_keep_result.txt
import bpy
import os
import sys

out_dir = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else os.getcwd()

bpy.ops.wm.read_factory_settings(use_empty=True)
main = bpy.data.scenes[0]
main.name = "Main"
main.render.engine = 'BLENDER_GAME'
overlay = bpy.data.scenes.new("Overlay")
overlay.render.engine = 'BLENDER_GAME'
viaact = bpy.data.scenes.new("ViaActuator")
viaact.render.engine = 'BLENDER_GAME'


def add_camera(scene, name):
    cam = bpy.data.objects.new(name, bpy.data.cameras.new(name))
    scene.objects.link(cam)
    scene.camera = cam
    return cam


add_camera(main, "CamMain")
add_camera(overlay, "CamOverlay")
add_camera(viaact, "CamVia")

# Objeto com material na Overlay (para ter shader e propriedade de estado).
mesh = bpy.data.meshes.new("Quad")
mesh.from_pydata([(-1, -1, 0), (1, -1, 0), (1, 1, 0), (-1, 1, 0)], [], [(0, 1, 2, 3)])
quad = bpy.data.objects.new("Marker", mesh)
quad.data.materials.append(bpy.data.materials.new("MatOverlay"))
overlay.objects.link(quad)

# Atuador Add Overlay com Preload, em Main, nunca disparado: so a pre-carga deve acontecer.
holder = bpy.data.objects.new("Holder", None)
main.objects.link(holder)
main.objects.active = holder
bpy.ops.logic.controller_add(type='LOGIC_AND', name='and', object=holder.name)
bpy.ops.logic.actuator_add(type='SCENE', name='add_via', object=holder.name)
act = holder.game.actuators['add_via']
act.mode = 'ADDFRONT'
act.scene = viaact
act.use_preload = True
holder.game.controllers['and'].link(actuator=act)  # sem sensor: nunca dispara

script = bpy.data.texts.new("driver.py")
script.write('''import Range
import os

own = Range.logic.getCurrentController().owner
frame = own.get("frame", 0)
own["frame"] = frame + 1
log = own.get("log", [])
result_path = os.path.join(Range.logic.expandPath("//"), "preload_keep_result.txt")


def scenes():
    return {s.name: s for s in Range.logic.getSceneList()}


def converts(name):
    return sum(1 for e in Range.logic.getLoadLog() if e["scene"] == name and e["stage"] == "convert")


def check(label, ok):
    log.append(("OK " if ok else "FALHA ") + label)


if frame == 0:
    # O aquecimento do Cook reinicia o jogo no mesmo processo: descarta o log daquela passada.
    Range.logic.getLoadLog(clear=True)
elif frame == 1:
    check("preloadScene retorna True", Range.logic.preloadScene("Overlay") is True)
    check("preloadScene de cena inexistente retorna False", Range.logic.preloadScene("NaoExiste") is False)
elif frame == 3:
    check("Overlay convertida antes do addScene", converts("Overlay") == 1)
    check("Overlay fora da lista antes do addScene", "Overlay" not in scenes())
    check("ViaActuator pre-carregada pelo atuador", converts("ViaActuator") == 1)
    check("ViaActuator fora da lista", "ViaActuator" not in scenes())
    Range.logic.addScene("Overlay", 1)
elif frame == 5:
    s = scenes().get("Overlay")
    check("Overlay entrou na lista", s is not None)
    check("addScene usou a cena pronta (sem converter de novo)", converts("Overlay") == 1)
    if s:
        s.objects["Marker"]["estado"] = 42
        s.end(keep=True)
elif frame == 7:
    check("end(keep=True) tirou a Overlay da lista", "Overlay" not in scenes())
    Range.logic.addScene("Overlay", 1)
elif frame == 9:
    s = scenes().get("Overlay")
    check("Overlay voltou", s is not None)
    check("volta sem converter de novo", converts("Overlay") == 1)
    check("estado mantido (estado == 42)", bool(s) and s.objects["Marker"].get("estado") == 42)
    check("cena retomada (nao suspensa)", bool(s) and not s.suspended)
    if s:
        s.end()
elif frame == 11:
    check("end() normal removeu", "Overlay" not in scenes())
    Range.logic.addScene("Overlay", 1)
elif frame == 13:
    check("depois do end() normal converte de novo", converts("Overlay") == 2)
    with open(result_path, "w") as f:
        f.write("\\n".join(log) + "\\n")
    Range.logic.endGame()
own["log"] = log
''')

bpy.ops.logic.sensor_add(type='ALWAYS', name='tick', object=holder.name)
bpy.ops.logic.controller_add(type='PYTHON', name='py', object=holder.name)
holder.game.sensors['tick'].use_pulse_true_level = True
holder.game.controllers['py'].text = script
holder.game.controllers['py'].link(sensor=holder.game.sensors['tick'])

path = os.path.join(out_dir, "preload_keep.range")
bpy.ops.wm.save_as_mainfile(filepath=path)
print("salvo:", path)
