"""Abre uma cena .range ja existente, ajusta bias/slopebias de toda luz Sun com sombra
ligada, embute o probe generico (sombra_bias_probe_generico.py) numa camera e salva uma
COPIA em outro caminho -- nunca sobrescreve a cena original.

Uso:
  AnastacioEngine.exe -b --factory-startup <cena_original.range> --python \
      preparar_cena_sombra_bias.py -- <saida.range> <bias> <slopebias>
"""
import bpy
import os
import sys

argv = sys.argv[sys.argv.index('--') + 1:]
out = argv[0]
bias = float(argv[1])
slopebias = float(argv[2])

scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'

changed = 0
for ob in scene.objects:
    if ob.type != 'LAMP':
        continue
    lamp = ob.data
    if lamp.type == 'SUN' and lamp.use_shadow:
        lamp.shadow_buffer_bias = bias
        lamp.shadow_buffer_slope_bias = slopebias
        changed += 1

if changed == 0:
    raise SystemExit('nenhuma luz Sun com use_shadow encontrada na cena -- nada para ajustar')

cam = scene.camera
if cam is None:
    raise SystemExit('cena sem scene.camera definida -- probe precisa de uma camera ativa')

script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sombra_bias_probe_generico.py')
with open(script_path, encoding='utf-8') as handle:
    runtime = handle.read()
text_name = 'sombra_bias_probe_generico.py'
if text_name in bpy.data.texts:
    bpy.data.texts.remove(bpy.data.texts[text_name])
text = bpy.data.texts.new(text_name)
text.write(runtime)

scene.objects.active = cam
# Remove um probe anterior (caso esta cena ja tenha sido preparada antes) para nao duplicar.
for sensor in list(cam.game.sensors):
    if sensor.name == 'SombraProbe':
        bpy.ops.logic.sensor_remove(sensor=sensor.name, object=cam.name)
for controller in list(cam.game.controllers):
    if controller.name == 'SombraProbe':
        bpy.ops.logic.controller_remove(controller=controller.name, object=cam.name)

bpy.ops.logic.sensor_add(type='ALWAYS', name='SombraProbe', object=cam.name)
bpy.ops.logic.controller_add(type='PYTHON', name='SombraProbe', object=cam.name)
sensor = cam.game.sensors[-1]
sensor.use_pulse_true_level = True
controller = cam.game.controllers[-1]
controller.mode = 'MODULE'
controller.module = 'sombra_bias_probe_generico.tick'
sensor.link(controller)

bpy.ops.wm.save_as_mainfile(filepath=out, check_existing=False)
print('CENA preparada', out, 'bias=%s slopebias=%s luzes_ajustadas=%d' % (bias, slopebias, changed))
