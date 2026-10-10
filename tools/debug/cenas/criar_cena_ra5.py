"""RA5: materiais unicos com slots ocultos, fora do frustum e reativados.

AnastacioEngine.exe -b --factory-startup --python criar_cena_ra5.py -- teste.range
RA5_RESULT recebe o destino JSON durante a execucao do player.
"""
import bpy
import sys
from mathutils import Vector

scene = bpy.context.scene
for obj in list(scene.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.use_shading_nodes = True
scene.render.resolution_x = 640
scene.render.resolution_y = 360
scene.render.resolution_percentage = 100
scene.world.mist_settings.use_mist = False
for i in range(24):
    bpy.ops.mesh.primitive_cube_add(radius=0.4, location=((i % 6) - 2.5, (i // 6) - 1.5, 0))
    obj = scene.objects.active
    obj.name = 'cube%02d' % i
    obj.game.physics_type = 'NO_COLLISION'
    mat = bpy.data.materials.new('unique%02d' % i)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    shader = nodes.new('ShaderNodeBsdfPrincipled')
    shader.inputs['Base Color'].default_value = (0.8, 0.1 + i / 40.0, 0.05, 1)
    output = nodes.new('ShaderNodeOutputMaterial')
    mat.node_tree.links.new(shader.outputs[0], output.inputs[0])
    obj.data.materials.append(mat)
lamp = bpy.data.objects.new('sun', bpy.data.lamps.new('sun', 'SUN'))
scene.objects.link(lamp)
lamp.rotation_euler = (0.3, -0.4, -0.2)
cam = bpy.data.objects.new('camera', bpy.data.cameras.new('camera'))
scene.objects.link(cam)
cam.location = (0, -10, 9)
cam.data.lens = 16
cam.rotation_euler = (-Vector(cam.location)).to_track_quat('-Z', 'Y').to_euler()
scene.camera = cam
text = bpy.data.texts.new('ra5_test.py')
text.write('''import bge, json, os
frame = 0
samples = []
def tick(cont):
    global frame
    frame += 1
    scene = bge.logic.getCurrentScene()
    cubes = [scene.objects['cube%02d' % i] for i in range(24)]
    if frame == 30:
        for obj in cubes[1:]: obj.visible = False
    if frame == 60:
        for obj in cubes[1:]: obj.visible = True
    if frame == 90:
        for obj in cubes[1:]: obj.worldPosition.x += 1000
    if frame == 120:
        for obj in cubes[1:]: obj.worldPosition.x -= 1000
    if frame == 150:
        for obj in cubes: obj.visible = False
    if frame == 180:
        for obj in cubes: obj.visible = True
    if frame in (20, 45, 75, 105, 135, 165, 195):
        stats = bge.logic.getRenderStats()
        samples.append(dict(frame=frame, visible=sum(obj.visible for obj in cubes),
                            draws=stats['drawCalls'], materials=stats['materialBinds']))
    if frame == 210:
        with open(os.environ['RA5_RESULT'], 'w') as dest: json.dump(samples, dest, indent=2)
        bge.logic.endGame()
''')
scene.objects.active = cam
bpy.ops.logic.sensor_add(type='ALWAYS', name='tick', object=cam.name)
bpy.ops.logic.controller_add(type='PYTHON', name='test', object=cam.name)
cam.game.sensors['tick'].use_pulse_true_level = True
controller = cam.game.controllers['test']
controller.mode = 'MODULE'
controller.module = 'ra5_test.tick'
cam.game.sensors['tick'].link(controller)
bpy.ops.wm.save_as_mainfile(filepath=sys.argv[sys.argv.index('--') + 1], check_existing=False)
