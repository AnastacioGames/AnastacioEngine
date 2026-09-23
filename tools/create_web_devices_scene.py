"""Run with RangeEngine -b --python tools/create_web_devices_scene.py.

Jogo de teste de dispositivos de entrada no runtime Web. Um cubo segue o mouse e gira com a roda; o
script imprime "[dev] ..." a cada mudanca de estado: teclas, botoes e posicao do mouse, roda, gamepad
(botoes e eixos) e toque (vira clique de mouse). Abra com ?debug=1 para ver o log.
Saida: build-web/bin/web-devices.range.
"""
import bpy
from pathlib import Path

out_dir = Path(__file__).resolve().parents[1] / 'build-web' / 'bin'
out_dir.mkdir(parents=True, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.name = 'Devices'
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.resolution_x = 640
scene.game_settings.resolution_y = 480
scene.world = bpy.data.worlds.new('DevWorld')

cam = bpy.data.objects.new('DevCam', bpy.data.cameras.new('DevCam'))
scene.objects.link(cam)
cam.location = (0, -10, 0)
cam.rotation_euler = (1.5708, 0, 0)
scene.camera = cam
lamp = bpy.data.objects.new('DevSun', bpy.data.lamps.new('DevSun', 'SUN'))
scene.objects.link(lamp)
lamp.rotation_euler = (0.6, 0.2, 0.4)

bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0))
cube = bpy.context.object
cube.name = 'Cube'
cube.game.physics_type = 'NO_COLLISION'

script = bpy.data.texts.new('devices.py')
script.write('''import Range
from Range import events
cont = Range.logic.getCurrentController()
obj = cont.owner
kb = Range.logic.keyboard.inputs
ms = Range.logic.mouse
if "init" not in obj:
    obj["init"] = 1
    obj["last"] = {}
    print("[dev] ready: mexa mouse, teclas, roda, gamepad, toque", flush=True)
last = obj["last"]


def edge(name, value):
    if last.get(name) != value:
        last[name] = value
        print("[dev] %s=%s" % (name, value), flush=True)


for code, inp in kb.items():
    if inp.active:
        edge("key_%d" % code, "down")
    elif last.get("key_%d" % code) == "down":
        edge("key_%d" % code, "up")
for code, name in ((events.LEFTMOUSE, "left"), (events.MIDDLEMOUSE, "middle"), (events.RIGHTMOUSE, "right")):
    edge("mouse_" + name, "down" if ms.inputs[code].active else "up")
mx, my = ms.position
edge("mouse_pos", "%.1f,%.1f" % (mx, my))
if ms.inputs[events.WHEELUPMOUSE].activated:
    print("[dev] wheel up", flush=True)
    obj.applyRotation((0, 0, 0.3), False)
if ms.inputs[events.WHEELDOWNMOUSE].activated:
    print("[dev] wheel down", flush=True)
    obj.applyRotation((0, 0, -0.3), False)
obj.worldPosition = ((mx - 0.5) * 8, 0, (0.5 - my) * 6)

joys = Range.logic.joysticks
if joys and joys[0]:
    j = joys[0]
    edge("pad_buttons", str(list(j.activeButtons)))
    edge("pad_axes", str([round(a, 1) for a in j.axisValues]))
else:
    edge("pad", "nenhum")
''')
bpy.ops.logic.sensor_add(type='ALWAYS', object=cube.name)
s = cube.game.sensors[-1]
s.use_pulse_true_level = True
bpy.ops.logic.controller_add(type='PYTHON', object=cube.name)
c = cube.game.controllers[-1]
c.text = script
s.link(c)

output = out_dir / 'web-devices.range'
bpy.ops.wm.save_as_mainfile(filepath=str(output))
print('[web-devices] saved', str(output))
