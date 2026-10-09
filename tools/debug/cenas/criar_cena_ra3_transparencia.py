"""Referencia RA3: editor -b --factory-startup --python este.py -- destino.range."""
import bpy
import math
import os
import sys
from mathutils import Vector

out = sys.argv[sys.argv.index('--') + 1]
scene = bpy.context.scene
for obj in list(scene.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.resolution_x = 1280
scene.game_settings.resolution_y = 720
scene.game_settings.use_frame_rate = True
scene.world = bpy.data.worlds.new('RA3 World')
scene.world.horizon_color = (0.055, 0.07, 0.1)
scene.world.mist_settings.use_mist = False


def material(name, rgb, mode='OPAQUE'):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = rgb
    mat.alpha = 0.45 if mode != 'OPAQUE' else 1.0
    mat.use_transparency = mode != 'OPAQUE'
    mat.game_settings.alpha_blend = mode
    mat.game_settings.use_backface_culling = False
    return mat


colors = [(1, 0.12, 0.08), (0.08, 0.8, 0.3), (0.12, 0.35, 1)]
mats = [material('SORT_%d' % i, color, 'ALPHA_SORT') for i, color in enumerate(colors)]


def layers(name, count):
    vertices, faces = [], []
    for i in range(count):
        y = (i - (count - 1) / 2.0) * 0.6
        start = len(vertices)
        vertices.extend([(-1.4, y, -1.4), (1.4, y, -1.4),
                         (1.4, y, 1.4), (-1.4, y, 1.4)])
        faces.extend([(start, start + 1, start + 2), (start, start + 2, start + 3)])
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    for mat in mats:
        mesh.materials.append(mat)
    for polygon in mesh.polygons:
        polygon.material_index = (polygon.index // 2) % 3
    return mesh


shared = layers('SharedLayers', 9)
for name, x, angle in [('Layers', -4, 0), ('SharedA', 0, 0.35), ('SharedB', 1, -0.7)]:
    obj = bpy.data.objects.new(name, shared)
    scene.objects.link(obj)
    obj.location = (x, 0, 2.3)
    obj.rotation_euler.z = angle
    obj.game.physics_type = 'NO_COLLISION'
alternate = bpy.data.objects.new('AlternateTopology', layers('AlternateLayers', 5))
scene.objects.link(alternate)
alternate.location = (0, 0, -100)
alternate.game.physics_type = 'NO_COLLISION'

for i, mode in enumerate(['OPAQUE', 'ALPHA', 'CLIP', 'ADD']):
    bpy.ops.mesh.primitive_cube_add(location=(5, (i - 1.5) * 2.8, 1))
    obj = bpy.context.object
    obj.name = 'Control_' + mode
    obj.scale = (0.6, 0.6, 0.8)
    obj.game.physics_type = 'NO_COLLISION'
    obj.data.materials.append(material(mode, colors[i % 3], mode))
bpy.ops.mesh.primitive_plane_add(location=(0, 0, -0.05))
bpy.context.object.scale = (12, 12, 1)
bpy.context.object.data.materials.append(material('Ground', (0.3, 0.33, 0.38)))
bpy.context.object.game.physics_type = 'NO_COLLISION'

font = bpy.data.fonts.load(os.path.join(os.environ.get('WINDIR', 'C:/Windows'), 'Fonts', 'arial.ttf'))
font.pack()
for name, location in [('Front', (0, -13, 7)), ('Back', (0, 13, 7))]:
    cam = bpy.data.objects.new(name, bpy.data.cameras.new(name))
    scene.objects.link(cam)
    cam.location = location
    cam.data.lens = 16
    cam.rotation_euler = (Vector((0, 0, 2)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    label = bpy.data.objects.new('HUD_' + name, bpy.data.curves.new('HUD_' + name, 'FONT'))
    scene.objects.link(label)
    label.parent = cam
    label.location = (-1, 0.47, -1.7)
    label.scale = (0.028, 0.028, 0.028)
    label.data.body = 'RA3'
    label.data.font = font
scene.camera = scene.objects['Front']
sun = bpy.data.objects.new('Sun', bpy.data.lamps.new('Sun', 'SUN'))
scene.objects.link(sun)
sun.rotation_euler = (0.5, -0.4, 0.3)

text = bpy.data.texts.new('ra3_reference.py')
text.write('''import bge, math, os
from mathutils import Vector
state = {}
def tick(cont):
    scene = bge.logic.getCurrentScene()
    if not state:
        state.update(frame=0, t=0.0, moving=False, deform=False, changed=False)
        state['mesh'] = scene.objects['Layers'].meshes[0]
        state['vertices'] = [(m, i, state['mesh'].getVertex(m, i).XYZ.copy())
                             for m in range(state['mesh'].numMaterials)
                             for i in range(state['mesh'].getVertexArrayLength(m))]
        log = os.environ.get('RA3_LOG')
        if log:
            with open(log, 'w') as f:
                f.write('START objects=%d vertices=%d\\n' % (len(scene.objects), len(state['vertices'])))
    state['frame'] += 1
    events = bge.logic.keyboard.events
    pressed = lambda key: events[key] == bge.logic.KX_INPUT_JUST_ACTIVATED
    if pressed(bge.events.SPACEKEY): state['moving'] = not state['moving']
    if pressed(bge.events.CKEY):
        scene.active_camera = scene.objects['Back' if scene.active_camera.name == 'Front' else 'Front']
    if pressed(bge.events.DKEY): state['deform'] = not state['deform']
    if pressed(bge.events.TKEY):
        state['changed'] = not state['changed']
        scene.objects['Layers'].replaceMesh('AlternateLayers' if state['changed'] else 'SharedLayers', True, False)
    if pressed(bge.events.RKEY):
        state.update(t=0.0, moving=False, deform=False, changed=False)
        scene.objects['Layers'].replaceMesh('SharedLayers', True, False)
        scene.active_camera = scene.objects['Front']
    if state['moving']: state['t'] += 1.0 / 60.0
    t = state['t']
    for name, x, angle in [('Layers', -4, 0), ('SharedA', 0, 0.35), ('SharedB', 1, -0.7)]:
        obj = scene.objects[name]
        obj.worldPosition = (x, math.sin(t) * 0.6, 2.3)
        obj.worldOrientation = (0, 0, angle + t * 0.4)
        obj.localScale = (-1 if name == 'SharedB' else 1, 1 + 0.25 * math.sin(t), 1)
    cam = scene.active_camera
    side = -1 if cam.name == 'Front' else 1
    cam.worldPosition = (math.sin(t * 0.3) * 9, side * 13, 7)
    cam.worldOrientation = (Vector((0, 0, 2)) - cam.worldPosition).to_track_quat('-Z', 'Y')
    for m, i, original in state['vertices']:
        pos = original.copy()
        if state['deform']: pos.y += 0.8 * math.sin(pos.x * 2 + t)
        vertex = state['mesh'].getVertex(m, i)
        if vertex.XYZ != pos:
            vertex.XYZ = pos
    scene.objects['HUD_' + cam.name].text = ('RA3 REFERENCE | SPACE motion | C camera | D deform | T topology | R reset\\n'
        'Left: layers | Center: shared mesh | Right: Opaque / Alpha / Clip / Add\\n'
        'camera=%s moving=%s deform=%s topology=%s' %
        (cam.name, state['moving'], state['deform'], state['changed']))
    if os.environ.get('RA3_AUTO') == '1':
        frame = state['frame']
        state['moving'] = frame < 180
        state['deform'] = 60 <= frame < 120
        if frame == 120: scene.active_camera = scene.objects['Back']
        if frame == 180:
            scene.objects['Layers'].replaceMesh('AlternateLayers', True, False)
        if frame == 210:
            scene.objects['Layers'].replaceMesh('SharedLayers', True, False)
        if frame == 240:
            with open(os.environ['RA3_LOG'], 'a') as f: f.write('END frames=240 camera/deform/topology exercised\\n')
            bge.logic.endGame()
''')
controller = bpy.data.objects.new('Controller', None)
scene.objects.link(controller)
scene.objects.active = controller
bpy.ops.logic.sensor_add(type='ALWAYS', object=controller.name)
bpy.ops.logic.controller_add(type='PYTHON', object=controller.name)
controller.game.sensors[-1].use_pulse_true_level = True
controller.game.controllers[-1].mode = 'MODULE'
controller.game.controllers[-1].module = 'ra3_reference.tick'
controller.game.sensors[-1].link(controller.game.controllers[-1])
bpy.ops.wm.save_as_mainfile(filepath=out, check_existing=False)
print('RA3 saved:', out)
