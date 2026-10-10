"""RA4: exercita o cache de stream VBO para instancing normal.

AnastacioEngine.exe -b --factory-startup --python criar_cena_ra4_instancing.py -- teste.range
RA4_RESULT recebe o JSON durante a execucao no player.
"""
import bpy
import sys
from mathutils import Vector

out = sys.argv[sys.argv.index('--') + 1]
scene = bpy.context.scene
for obj in list(scene.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.use_shading_nodes = True
scene.render.resolution_x = 640
scene.render.resolution_y = 360
scene.render.resolution_percentage = 100
scene.world.mist_settings.use_mist = False

mat = bpy.data.materials.new('instanced')
mat.use_nodes = True
mat.use_instancing = True
nodes = mat.node_tree.nodes
nodes.clear()
shader = nodes.new('ShaderNodeBsdfPrincipled')
shader.inputs['Base Color'].default_value = (0.15, 0.6, 0.95, 1.0)
output = nodes.new('ShaderNodeOutputMaterial')
mat.node_tree.links.new(shader.outputs[0], output.inputs[0])

bpy.ops.mesh.primitive_cube_add(radius=0.35, location=(-4, -4, 0))
prototype = scene.objects.active
prototype.name = 'instance000'
prototype.data.materials.append(mat)
prototype.game.physics_type = 'NO_COLLISION'
for i in range(1, 100):
    obj = bpy.data.objects.new('instance%03d' % i, prototype.data)
    obj.location = ((i % 10) - 4, (i // 10) - 4, 0)
    obj.game.physics_type = 'NO_COLLISION'
    scene.objects.link(obj)

sun = bpy.data.objects.new('sun', bpy.data.lamps.new('sun', 'SUN'))
sun.rotation_euler = (0.3, -0.4, -0.2)
scene.objects.link(sun)
cam = bpy.data.objects.new('camera', bpy.data.cameras.new('camera'))
cam.location = (0, -14, 13)
cam.data.lens = 16
cam.rotation_euler = (-Vector(cam.location)).to_track_quat('-Z', 'Y').to_euler()
scene.objects.link(cam)
scene.camera = cam

text = bpy.data.texts.new('ra4_test.py')
text.write('''import bge, json, os
frame = 0
samples = []
def tick(cont):
    global frame
    frame += 1
    scene = bge.logic.getCurrentScene()
    changed = scene.objects['instance000']
    if frame == 60: changed.worldPosition.x += 0.4
    if frame == 100: changed.color = (1.0, 0.1, 0.1, 1.0)
    if frame == 140: changed.visible = False
    if frame == 180: changed.visible = True
    if True:  # todo frame: getRenderStats reflete o frame renderizado anterior
        stats = bge.logic.getRenderStats()
        samples.append(dict(frame=frame, draws=stats['drawCalls'], uploads=stats['instancingUploads']))
    if frame == 205:
        with open(os.environ['RA4_RESULT'], 'w') as dest: json.dump(samples, dest, indent=2)
        bge.logic.endGame()
''')
scene.objects.active = cam
bpy.ops.logic.sensor_add(type='ALWAYS', name='tick', object=cam.name)
bpy.ops.logic.controller_add(type='PYTHON', name='test', object=cam.name)
cam.game.sensors['tick'].use_pulse_true_level = True
controller = cam.game.controllers['test']
controller.mode = 'MODULE'
controller.module = 'ra4_test.tick'
cam.game.sensors['tick'].link(controller)
bpy.ops.wm.save_as_mainfile(filepath=out, check_existing=False)
