"""RA4-passes: cena PARADA para medir se o buffer de instancing compartilhado entre passes
(uma por DrawType) reenvia o grupo a cada passe de sombra. Ver docs/revisao-directx-claude.md (A1).

AnastacioEngine.exe -b --factory-startup --python criar_cena_ra4_passes.py -- saida.range N layout luz
  N      quantidade de instancias (ex.: 400)
  layout spread = objetos espalhados em profundidade (cada cascata ve um conjunto diferente)
         tight  = objetos juntos perto da camera (todas as cascatas veem o mesmo conjunto)
  luz    sun3 | sun2 | point | none
O player grava RA4P_RESULT (JSON) e fecha sozinho depois de RA4P_FRAMES quadros.
Nada se move, muda de cor ou some durante a medicao.
"""
import bpy
import math
import sys
from mathutils import Vector

args = sys.argv[sys.argv.index('--') + 1:]
out, count, layout, light = args[0], int(args[1]), args[2], args[3]
flags = args[4].split(',') if len(args) > 4 else []  # noinst, noground, small, sphere

scene = bpy.context.scene
for obj in list(scene.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.use_shading_nodes = True
scene.render.resolution_x = 640
scene.render.resolution_y = 360
scene.render.resolution_percentage = 100
scene.world.mist_settings.use_mist = False
scene.game_settings.vsync = 'OFF'
scene.game_settings.use_frame_rate = False

mat = bpy.data.materials.new('instanced')
mat.use_nodes = True
mat.use_instancing = 'noinst' not in flags
nodes = mat.node_tree.nodes
nodes.clear()
shader = nodes.new('ShaderNodeBsdfPrincipled')
shader.inputs['Base Color'].default_value = (0.15, 0.6, 0.95, 1.0)
output = nodes.new('ShaderNodeOutputMaterial')
mat.node_tree.links.new(shader.outputs[0], output.inputs[0])

ground_mat = bpy.data.materials.new('ground')
if 'noground' not in flags:
  bpy.ops.mesh.primitive_plane_add(radius=200, location=(0, 0, -0.4))
  ground = scene.objects.active
  ground.data.materials.append(ground_mat)
  ground.game.physics_type = 'NO_COLLISION'

if 'sphere' in flags:
    bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, size=0.35, location=(0, 0, 0))
else:
    bpy.ops.mesh.primitive_cube_add(radius=0.02 if 'small' in flags else 0.35, location=(0, 0, 0))
prototype = scene.objects.active
prototype.data.materials.append(mat)
scene.objects.unlink(prototype)

cols = 20
for i in range(count):
    obj = bpy.data.objects.new('inst%04d' % i, prototype.data)
    row, col = divmod(i, cols)
    rows = max(1, (count + cols - 1) // cols)
    if layout == 'spread':
        # Profundidade de 3 m a ~150 m: cruza as faixas Near/Medium/Low.
        y = 3.0 + 147.0 * (row / max(1, rows - 1)) ** 1.5
        x = (col - cols / 2) * (0.6 + y * 0.05)
    else:
        y = 3.0 + row * 0.15
        x = (col - cols / 2) * 0.15
    obj.location = (x, y, 0)
    obj.game.physics_type = 'NO_COLLISION'
    scene.objects.link(obj)

if light != 'none':
    lamp = bpy.data.lamps.new('key', 'POINT' if light == 'point' else 'SUN')
    lamp.use_shadow = True
    lamp_obj = bpy.data.objects.new('key', lamp)
    if light == 'point':
        lamp_obj.location = (0, 8, 6)
        lamp.distance = 200
    else:
        lamp_obj.rotation_euler = (math.radians(40), math.radians(-25), 0)
        lamp.use_csm_shadow = True
        lamp.csm_cascade_count = 2 if light == 'sun2' else 3
    scene.objects.link(lamp_obj)

cam = bpy.data.objects.new('camera', bpy.data.cameras.new('camera'))
cam.location = (0, -2, 3)
cam.data.lens = 18
cam.data.clip_end = 300
cam.rotation_euler = (Vector((0, 40, 0)) - Vector(cam.location)).to_track_quat('-Z', 'Y').to_euler()
scene.objects.link(cam)
scene.camera = cam

text = bpy.data.texts.new('ra4p_test.py')
text.write('''import bge, json, os
frame = 0
samples = []
LAST = int(os.environ.get('RA4P_FRAMES', '600'))
def tick(cont):
    global frame
    frame += 1
    s = bge.logic.getRenderStats()
    samples.append(dict(frame=frame, uploads=s['instancingUploads'], draws=s['drawCalls'],
                        shadowPasses=s.get('shadowPasses', -1), visible=s.get('cullingVisible', -1),
                        fps=bge.logic.getAverageFrameRate()))
    if frame == LAST:
        with open(os.environ['RA4P_RESULT'], 'w') as dest:
            json.dump(samples, dest)
        bge.logic.endGame()
''')
scene.objects.active = cam
bpy.ops.logic.sensor_add(type='ALWAYS', name='tick', object=cam.name)
bpy.ops.logic.controller_add(type='PYTHON', name='test', object=cam.name)
cam.game.sensors['tick'].use_pulse_true_level = True
controller = cam.game.controllers['test']
controller.mode = 'MODULE'
controller.module = 'ra4p_test.tick'
cam.game.sensors['tick'].link(controller)
bpy.ops.wm.save_as_mainfile(filepath=out, check_existing=False)
