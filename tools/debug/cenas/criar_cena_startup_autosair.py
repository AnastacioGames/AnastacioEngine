# Salva a cena de startup do usuario com um script que encerra o jogo apos ~3 s (saida limpa,
# para o alocador com checagem listar blocos nao liberados).
#   AnastacioEngine.exe -b --python tools/debug/cenas/criar_cena_startup_autosair.py -- saida.range
import bpy
import sys

out = sys.argv[sys.argv.index('--') + 1]
scene = bpy.context.scene
obj = bpy.data.objects.get('Cube') or scene.objects[0]
txt = bpy.data.texts.new('sair.py')
txt.write("import bge\n"
          "o = bge.logic.getCurrentController().owner\n"
          "o['t'] = o.get('t', 0) + 1\n"
          "if o['t'] > 180:\n"
          "    bge.logic.endGame()\n")
scene.objects.active = obj
bpy.ops.logic.sensor_add(type='ALWAYS', object=obj.name)
bpy.ops.logic.controller_add(type='PYTHON', object=obj.name)
sensor = obj.game.sensors[-1]
sensor.use_pulse_true_level = True
controller = obj.game.controllers[-1]
controller.text = txt
sensor.link(controller)
print("objetos:", [o.name for o in scene.objects], "world:", scene.world.name if scene.world else None)
bpy.ops.wm.save_as_mainfile(filepath=out)
