"""Especifico para RolimaRacer.range: a luz real da Pista_1 fica dentro do grupo
'group_Cameras' (objeto 'Sun', dado 'Sun.005') -- um objeto solto 'Sun.001' direto na
cena tem use_shadow=False e NAO e o usado. O grupo so e adicionado pelo fluxo normal do
jogo (selecao de piloto/corrida), nao ao carregar a cena direto -- por isso este script
NAO forca a cena inicial para Pista_1: mantem o fluxo original (menu etc.) intacto para
que o jogador passe por ele normalmente e o grupo seja carregado de verdade. So ajusta o
datablock da luz e embute o probe generico na camera da pista, que fica dormente ate
Pista_1 ficar ativa. Salva SEMPRE numa copia; nunca escreve no RolimaRacer.range original
durante a busca.

Uso:
  AnastacioEngine.exe -b --factory-startup <RolimaRacer.range> --python \
      preparar_pista1_bias.py -- <saida.range> <bias> <slopebias>
"""
import bpy
import os
import sys

argv = sys.argv[sys.argv.index('--') + 1:]
out = argv[0]
bias = float(argv[1])
slopebias = float(argv[2])

LAMP_DATA_NAME = 'Sun.005'
LIGHT_OBJECT_NAME = 'Sun'  # existe tambem um 'Sun.001' decorativo (use_shadow=False) na cena
RECEIVER_NAME = 'Track_mesh_Pista_1'
SCENE_NAME = 'Pista_1'

if LAMP_DATA_NAME not in bpy.data.lamps:
    raise SystemExit('lamp "%s" nao existe neste arquivo -- a estrutura pode ter mudado' % LAMP_DATA_NAME)
lamp = bpy.data.lamps[LAMP_DATA_NAME]
lamp.shadow_buffer_bias = bias
lamp.shadow_buffer_slope_bias = slopebias

if SCENE_NAME not in bpy.data.scenes:
    raise SystemExit('cena "%s" nao existe neste arquivo' % SCENE_NAME)
scene = bpy.data.scenes[SCENE_NAME]
scene.render.engine = 'BLENDER_GAME'
# Nao forca scene ativa aqui -- o jogo deve iniciar na cena original (menu/intro) e
# chegar em Pista_1 pelo fluxo normal, senao o grupo com o Sol nunca e carregado.

cam = scene.camera
if cam is None:
    raise SystemExit('Pista_1 sem scene.camera definida')

script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sombra_bias_probe_generico.py')
with open(script_path, encoding='utf-8') as handle:
    runtime = handle.read()
text_name = 'sombra_bias_probe_generico.py'
if text_name in bpy.data.texts:
    bpy.data.texts[text_name].from_string(runtime)
else:
    bpy.data.texts.new(text_name).write(runtime)

# bpy.ops.logic.*/object.game_property_* resolvem o objeto via contexto da cena ATIVA
# (bpy.context.scene), nao via scene.objects.active isolado -- por isso trocamos a cena
# ativa so durante estas edicoes, e devolvemos antes de salvar (o jogo deve iniciar na
# cena original, nao em Pista_1 -- ver comentario acima sobre o grupo do Sol).
original_scenes = {screen.name: screen.scene for screen in bpy.data.screens}
for screen in bpy.data.screens:
    screen.scene = scene
scene.objects.active = cam

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

for prop_name in ('ae_receiver_name', 'ae_light_name'):
    if prop_name in cam.game.properties:
        bpy.ops.object.game_property_remove(property=prop_name, object=cam.name)
bpy.ops.object.game_property_new(type='STRING', name='ae_receiver_name')
cam.game.properties['ae_receiver_name'].value = RECEIVER_NAME
bpy.ops.object.game_property_new(type='STRING', name='ae_light_name')
cam.game.properties['ae_light_name'].value = LIGHT_OBJECT_NAME

for screen_name, original in original_scenes.items():
    bpy.data.screens[screen_name].scene = original

bpy.ops.wm.save_as_mainfile(filepath=out, check_existing=False)
print('CENA preparada', out, 'bias=%s slopebias=%s' % (bias, slopebias))
