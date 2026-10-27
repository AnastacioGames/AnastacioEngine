"""Cena mínima para o teste do pacote de release: o jogo grava um arquivo e sai sozinho.

Uso: AnastacioEngine -b --factory-startup --python tools/linux/release_smoke_scene.py -- <saida.range> <marca.txt>
O runtime (AnastacioRuntime --server <saida.range>) roda 60 frames, grava "ok <frames> <versao python>"
em <marca.txt> e fecha. Ver tools/linux/testar-release.sh.
"""
import bpy
import sys

argv = sys.argv[sys.argv.index("--") + 1:]
output, marker = argv[0], argv[1]

script = bpy.data.texts.new("smoke.py")
script.write(
    "import Range, sys\n"
    "own = Range.logic.getCurrentController().owner\n"
    "own['frames'] = own.get('frames', 0) + 1\n"
    "if own['frames'] >= 60:\n"
    "    with open(%r, 'w') as f:\n"
    "        f.write('ok %%d %%s\\n' %% (own['frames'], sys.version.split()[0]))\n"
    "    Range.logic.endGame()\n" % marker)

scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
cube = bpy.data.objects["Cube"]
scene.objects.active = cube
bpy.ops.logic.sensor_add(type='ALWAYS', name="Always", object=cube.name)
bpy.ops.logic.controller_add(type='PYTHON', name="Smoke", object=cube.name)
sensor = cube.game.sensors["Always"]
sensor.use_pulse_true_level = True
controller = cube.game.controllers["Smoke"]
controller.text = script
sensor.link(controller)

bpy.ops.wm.save_as_mainfile(filepath=output)
