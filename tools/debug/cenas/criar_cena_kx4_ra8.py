"""KX4 + RA8: billboard LOD parado nao reescreve a orientacao; batching reusa arrays.

AnastacioEngine.exe -b --factory-startup --python criar_cena_kx4_ra8.py -- teste.range
KX4_RESULT recebe o JSON durante a execucao no player.
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

mat = bpy.data.materials.new('batched')
for i in range(40):
    bpy.ops.mesh.primitive_cube_add(radius=0.3, location=((i % 8) - 4, (i // 8) - 2, 0))
    obj = scene.objects.active
    obj.name = 'batch%02d' % i
    obj.data.materials.append(mat)
    obj.game.physics_type = 'NO_COLLISION'

# Billboard: nivel 0 ja e billboard (distancia 0) para valer a qualquer distancia.
bpy.ops.mesh.primitive_plane_add(radius=1.0, location=(0, 4, 1))
bb = scene.objects.active
bb.name = 'billboard'
bb.rotation_euler = (1.5708, 0, 0)
bb.game.physics_type = 'NO_COLLISION'
bpy.ops.object.lod_add()
bpy.ops.object.lod_add()
bb.lod_levels[1].object = bb
bb.lod_levels[1].distance = 1000.0
bb.lod_levels[0].use_billboard = True
print('LODS', len(bb.lod_levels))

sun = bpy.data.objects.new('sun', bpy.data.lamps.new('sun', 'SUN'))
scene.objects.link(sun)
cam = bpy.data.objects.new('camera', bpy.data.cameras.new('camera'))
cam.location = (0, -12, 8)
cam.rotation_euler = (-Vector(cam.location)).to_track_quat('-Z', 'Y').to_euler()
scene.objects.link(cam)
scene.camera = cam

text = bpy.data.texts.new('kx4_test.py')
text.write('''import bge, json, os
frame = 0
samples = []
def tick(cont):
    global frame
    frame += 1
    scene = bge.logic.getCurrentScene()
    if frame == 2:
        bge.types.KX_BatchGroup([o for o in scene.objects if o.name.startswith('batch')])
    if frame == 60:
        scene.active_camera.worldPosition.x += 6.0
    if frame == 90:
        scene.objects['batch00'].worldPosition.z += 0.5
    bb = scene.objects['billboard']
    stats = bge.logic.getRenderStats()
    samples.append(dict(frame=frame, draws=stats['drawCalls'],
                        ori=[list(r) for r in bb.worldOrientation]))
    if frame == 120:
        with open(os.environ['KX4_RESULT'], 'w') as dest: json.dump(samples, dest)
        bge.logic.endGame()
''')
scene.objects.active = cam
bpy.ops.logic.sensor_add(type='ALWAYS', name='tick', object=cam.name)
bpy.ops.logic.controller_add(type='PYTHON', name='test', object=cam.name)
cam.game.sensors['tick'].use_pulse_true_level = True
c = cam.game.controllers['test']
c.mode = 'MODULE'
c.module = 'kx4_test.tick'
cam.game.sensors['tick'].link(c)
bpy.ops.wm.save_as_mainfile(filepath=out, check_existing=False)
