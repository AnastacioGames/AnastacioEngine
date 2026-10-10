"""Lote CV1/KX2, PH9, GL4: comportamento + tempo por frame.

AnastacioEngine.exe -b --factory-startup --python criar_cena_lote2_auditoria.py -- teste.range
LOTE2_RESULT recebe o JSON.
- 30 armatures com acao so de bones (CV1) e 20 filhos cada;
- 1 cubo com acao de location (deve se mover);
- 150 cubos caindo numa pilha com sensor Collision (PH9);
- ImageBuff estatico com refresh todo frame e plot no frame 120 (GL4).
"""
import bpy, sys
from mathutils import Vector

out = sys.argv[sys.argv.index('--') + 1]
scene = bpy.context.scene
for obj in list(scene.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
scene.render.engine = 'BLENDER_GAME'
scene.render.resolution_x = 640
scene.render.resolution_y = 360
scene.game_settings.use_frame_rate = False
scene.game_settings.vsync = 'OFF'

def logic(obj, name, module):
    scene.objects.active = obj
    bpy.ops.logic.sensor_add(type='ALWAYS', name='t_' + name, object=obj.name)
    bpy.ops.logic.controller_add(type='PYTHON', name='c_' + name, object=obj.name)
    s = obj.game.sensors['t_' + name]; s.use_pulse_true_level = True
    c = obj.game.controllers['c_' + name]; c.mode = 'MODULE'; c.module = module
    s.link(c)

# acao so de bones
arm_data = bpy.data.armatures.new('arm')
bone_act = bpy.data.actions.new('bones_only')
fc = bone_act.fcurves.new('pose.bones["b"].rotation_quaternion', index=1, action_group='b')
fc.keyframe_points.insert(1, 0.0); fc.keyframe_points.insert(40, 0.7)
for i in range(30):
    arm = bpy.data.objects.new('arm%02d' % i, arm_data)
    arm.location = ((i % 6) * 3 - 8, (i // 6) * 3 + 10, 0)
    arm.game.physics_type = 'NO_COLLISION'
    scene.objects.link(arm)
    for j in range(20):
        ch = bpy.data.objects.new('ch%02d_%02d' % (i, j), None)
        ch.parent = arm
        ch.location = (0, 0, j * 0.1)
        scene.objects.link(ch)
scene.objects.active = scene.objects['arm00']
bpy.ops.object.mode_set(mode='EDIT')
b = arm_data.edit_bones.new('b'); b.head = (0, 0, 0); b.tail = (0, 0, 1)
bpy.ops.object.mode_set(mode='OBJECT')

# acao de objeto
obj_act = bpy.data.actions.new('obj_loc')
fc = obj_act.fcurves.new('location', index=0)
fc.keyframe_points.insert(1, 0.0); fc.keyframe_points.insert(40, 5.0)
bpy.ops.mesh.primitive_cube_add(location=(0, 30, 0))
mover = scene.objects.active; mover.name = 'mover'; mover.game.physics_type = 'NO_COLLISION'

# pilha de colisao
bpy.ops.mesh.primitive_plane_add(radius=20, location=(0, 0, 0))
ground = scene.objects.active; ground.name = 'ground'
for i in range(150):
    bpy.ops.mesh.primitive_cube_add(radius=0.4, location=((i % 10) - 4.5, ((i // 10) % 5) - 2, 1 + (i // 50) * 1.2))
    c = scene.objects.active; c.name = 'box%03d' % i
    c.game.physics_type = 'RIGID_BODY'
    scene.objects.active = c
    bpy.ops.logic.sensor_add(type='COLLISION', name='hit', object=c.name)
    bpy.ops.logic.controller_add(type='LOGIC_AND', name='and', object=c.name)
    c.game.sensors['hit'].link(c.game.controllers['and'])

# textura de video
mat = bpy.data.materials.new('vtex')
img = bpy.data.images.new('vimg', 64, 64)
tex = bpy.data.textures.new('vtex', 'IMAGE'); tex.image = img
slot = mat.texture_slots.add(); slot.texture = tex
bpy.ops.mesh.primitive_plane_add(radius=2, location=(0, -6, 3))
screen = scene.objects.active; screen.name = 'screen'; screen.data.materials.append(mat)
screen.game.physics_type = 'NO_COLLISION'

sun = bpy.data.objects.new('sun', bpy.data.lamps.new('sun', 'SUN')); scene.objects.link(sun)
cam = bpy.data.objects.new('camera', bpy.data.cameras.new('camera'))
cam.location = (0, -25, 18); cam.data.lens = 18
cam.rotation_euler = (Vector((0, 5, 0)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
scene.objects.link(cam); scene.camera = cam

text = bpy.data.texts.new('lote2.py')
text.write('''import bge, json, os, time
from bge import texture
frame = 0
log = dict(times=[], hits=[], mover=[], tex=None, nodes=[], syncs=[], prof={})
st = {}
def tick(cont):
    global frame
    frame += 1
    sc = bge.logic.getCurrentScene()
    if frame == 1:
        for o in sc.objects:
            if o.name.startswith('arm'): o.playAction('bones_only', 1, 40, play_mode=bge.logic.KX_ACTION_MODE_LOOP)
        sc.objects['mover'].playAction('obj_loc', 1, 40, play_mode=bge.logic.KX_ACTION_MODE_LOOP)
        scr = sc.objects['screen']
        t = texture.Texture(scr, 0)
        buf = texture.ImageBuff()
        buf.load(b'\\x40' * (64 * 64 * 3), 64, 64)
        t.source = buf
        st['t'] = t; st['buf'] = buf; st['last'] = time.perf_counter()
        return
    t = st['t']
    if frame == 120: st['buf'].plot(b'\\xff' * (8 * 8 * 3), 8, 8, 10, 10)
    t.refresh(False)
    if frame == 121: log['tex'] = 'plot ok'
    now = time.perf_counter(); log['times'].append((now - st['last']) * 1000); st['last'] = now
    rs = bge.logic.getRenderStats()
    if frame > 60:
        log['nodes'].append(rs['sceneNodeUpdates']); log['syncs'].append(rs['transformSyncs'])
        for k, v in bge.logic.getProfileInfo().items():
            log['prof'].setdefault(k, []).append(v[0])
    if frame % 30 == 0:
        log['hits'].append(sum(1 for o in sc.objects if o.name.startswith('box') and o.sensors['hit'].positive))
        log['mover'].append(round(sc.objects['mover'].worldPosition.x, 2))
    if frame == 600:
        with open(os.environ['LOTE2_RESULT'], 'w') as d: json.dump(log, d)
        bge.logic.endGame()
''')
logic(cam, 'run', 'lote2.tick')
bpy.ops.wm.save_as_mainfile(filepath=out, check_existing=False)
