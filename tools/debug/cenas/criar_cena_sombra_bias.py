"""Gera uma cena minima para testar 1 combinacao de bias/angulo/escala de sombra contra um
gabarito geometrico (ver sombra_bias_probe.py). Protótipo para decidir se o metodo e viavel
antes de montar a matriz completa de combinacoes.

Uso:
  AnastacioEngine.exe -b --factory-startup --python criar_cena_sombra_bias.py -- saida.range \
      <bias> <slopebias> <angulo_graus> <escala_cubo>

angulo_graus: 90 = luz vertical (topo), 15 = luz rasante.
"""
import bpy
import math
import os
import sys
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:]
out = argv[0]
bias = float(argv[1])
slopebias = float(argv[2])
angle_deg = float(argv[3])
scale = float(argv[4])

scene = bpy.context.scene
for ob in list(scene.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.use_shading_nodes = True


def principled(name, color):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    for n in list(nodes):
        nodes.remove(n)
    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = color
    out_node = nodes.new('ShaderNodeOutputMaterial')
    mat.node_tree.links.new(bsdf.outputs[0], out_node.inputs[0])
    return mat


mat_floor = principled('chao', (0.8, 0.8, 0.8, 1.0))
mat_cube = principled('cubo', (0.8, 0.1, 0.05, 1.0))

bpy.ops.mesh.primitive_plane_add(radius=20, location=(0, 0, 0))
floor = bpy.context.scene.objects.active
floor.name = 'Floor'
floor.data.materials.append(mat_floor)

# Radius=1: worldScale do cubo bate 1:1 com a meia-largura em mundo (sem rotacao),
# o que o probe usa como gabarito geometrico (cube_min/max = worldPosition +/- worldScale).
bpy.ops.mesh.primitive_cube_add(radius=1, location=(0, 0, scale))
cube = bpy.context.scene.objects.active
cube.name = 'Cube'
cube.scale = (scale, scale, scale)
cube.data.materials.append(mat_cube)

lamp = bpy.data.lamps.new('Sun', 'SUN')
lamp.use_shadow = True
lamp.shadow_buffer_bias = bias
lamp.shadow_buffer_slope_bias = slopebias
lamp.energy = 1.0
sun = bpy.data.objects.new('Sun', lamp)
scene.objects.link(sun)
# Sun nao tem posicao real (raios paralelos); so a posicao e levantada para o
# gizmo nao ficar enterrado no chao/cubo ao olhar a cena.
sun.location = (0, 0, 10)
# angle_deg medido da vertical (90 = luz a pino, 0 = rasante na horizontal).
elevation = math.radians(angle_deg)
direction = Vector((math.cos(elevation), 0.0, -math.sin(elevation)))
sun.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()

cam = bpy.data.objects.new('Camera', bpy.data.cameras.new('Camera'))
cam.location = (0, -18, 10)
cam.rotation_euler = (Vector((0, 0, scale)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
scene.objects.link(cam)
scene.camera = cam

# A faixa de amostras no chao (do centro do cubo para fora, na direcao oposta a luz) e
# recalculada pelo probe em runtime a partir de ae_angle/ae_scale (ver _samples_for em
# sombra_bias_probe.py) -- evita serializar a lista numa Game Property STRING.
scene.objects.active = cam


def game_prop(name, prop_type, value):
    # Propriedade customizada generica (cam['x'] = y) nao e exposta ao jogo por este
    # motor -- so "Game Properties" tipadas (object.game.properties) chegam ao runtime.
    bpy.ops.object.game_property_new(type=prop_type, name=name)
    cam.game.properties[name].value = value


game_prop('ae_bias', 'FLOAT', bias)
game_prop('ae_slopebias', 'FLOAT', slopebias)
game_prop('ae_angle', 'FLOAT', angle_deg)
game_prop('ae_scale', 'FLOAT', scale)

script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sombra_bias_probe.py')
with open(script_path, encoding='utf-8') as handle:
    runtime = handle.read()
text = bpy.data.texts.new('sombra_bias_probe.py')
text.write(runtime)
scene.objects.active = cam
bpy.ops.logic.sensor_add(type='ALWAYS', name='SombraProbe', object=cam.name)
bpy.ops.logic.controller_add(type='PYTHON', name='SombraProbe', object=cam.name)
sensor = cam.game.sensors[-1]
sensor.use_pulse_true_level = True
controller = cam.game.controllers[-1]
controller.mode = 'MODULE'
controller.module = 'sombra_bias_probe.tick'
sensor.link(controller)

bpy.ops.wm.save_as_mainfile(filepath=out, check_existing=False)
print('CENA salva', out, bias, slopebias, angle_deg, scale)
