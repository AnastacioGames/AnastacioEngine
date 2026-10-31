"""Cena de teste do NLA no jogo (playNLA).

Armature com 1 osso "B" e duas faixas NLA:
- Faixa 1 (Replace): ROT_A gira Z 0->90 graus nos frames 1-21; ROT_B segura Z=180 nos frames 31-51.
- Faixa 2 (Add, influencia animada 0.5): MOVE soma location X = 1 nos frames 1-51.
O script do jogo pula para frames fixos com setNLAFrame e grava a pose do osso.

Uso: AnastacioEngine.exe -b --factory-startup --python criar_cena_nla.py -- saida.range log.txt
"""
import bpy, sys, math

argv = sys.argv[sys.argv.index('--') + 1:]
out_path, log_path = argv[0], argv[1]

scene = bpy.context.scene
for ob in list(scene.objects):
    scene.objects.unlink(ob)
scene.render.engine = 'BLENDER_GAME'

arm_data = bpy.data.armatures.new('ArmNLA')
arm_data.culling_method = 'NONE'  # sem malha filha: atualizar a pose mesmo sem nada na tela
arm = bpy.data.objects.new('ArmNLA', arm_data)
scene.objects.link(arm)
scene.objects.active = arm
arm.select = True
bpy.ops.object.mode_set(mode='EDIT')
b = arm_data.edit_bones.new('B')
b.head = (0, 0, 0)
b.tail = (0, 0, 1)
bpy.ops.object.mode_set(mode='POSE')
pb = arm.pose.bones['B']
pb.rotation_mode = 'XYZ'
bpy.ops.object.mode_set(mode='OBJECT')


def make_action(name, keys):
    act = bpy.data.actions.new(name)
    for path, index, points in keys:
        fc = act.fcurves.new('pose.bones["B"].%s' % path, index, 'B')
        for f, v in points:
            k = fc.keyframe_points.insert(f, v)
            k.interpolation = 'LINEAR'
    return act

rot_a = make_action('ROT_A', [('rotation_euler', 2, [(1, 0.0), (21, math.pi / 2)])])
rot_b = make_action('ROT_B', [('rotation_euler', 2, [(1, math.pi), (21, math.pi)])])
move = make_action('MOVE', [('location', 0, [(1, 1.0), (51, 1.0)])])

arm.animation_data_create()
tracks = arm.animation_data.nla_tracks
t1 = tracks.new()
t1.name = 'Base'
s = t1.strips.new('ROT_A', 1, rot_a)
s = t1.strips.new('ROT_B', 31, rot_b)
s.extrapolation = 'HOLD_FORWARD'
t2 = tracks.new()
t2.name = 'Add'
s = t2.strips.new('MOVE', 1, move)
s.blend_type = 'ADD'
s.use_animated_influence = True  # cria a curva de influencia; o jogo le essa curva
s.influence = 0.5
for fc in s.fcurves:
    if fc.data_path == 'influence':
        for k in fc.keyframe_points:
            k.co[1] = 0.5
            k.handle_left[1] = k.handle_right[1] = 0.5
s.extrapolation = 'HOLD'

# Logic: Always (pulse) -> Python module
text = bpy.data.texts.new('nla_test.py')
text.write('''import bge, math
FRAMES = [11, 25, 40, 1, 21]
# esperado: rotZ 45, 90, 180, 0, 90; locX 0.5 em todos
LOG = %r

def tick(cont):
    own = cont.owner
    g = bge.logic.globalDict
    st = g.setdefault('nla', {'i': -1, 'lines': []})
    if st['i'] == -1:
        ok = own.playNLA(speed=0.0, loop=False)
        st['lines'].append('playNLA=%%s' %% ok)
    else:
        ch = own.channels['B']
        st['lines'].append('frame=%%.1f rotZ=%%.2f locX=%%.3f playing=%%s' %% (
            own.getNLAFrame(), math.degrees(ch.rotation_euler[2]), ch.location[0], own.isPlayingNLA()))
    st['i'] += 1
    if st['i'] < len(FRAMES):
        own.setNLAFrame(FRAMES[st['i']])
    else:
        with open(LOG, 'w') as f:
            f.write(chr(10).join(st['lines']) + chr(10) + '# fim' + chr(10))
        bge.logic.endGame()
''' % log_path)

bpy.ops.logic.sensor_add(type='ALWAYS', name='Always', object=arm.name)
bpy.ops.logic.controller_add(type='PYTHON', name='Py', object=arm.name)
sens = arm.game.sensors['Always']
sens.use_pulse_true_level = True
cont = arm.game.controllers['Py']
cont.mode = 'MODULE'
cont.module = 'nla_test.tick'
sens.link(cont)

cam_data = bpy.data.cameras.new('Cam')
cam = bpy.data.objects.new('Cam', cam_data)
cam.location = (0, -6, 1)
scene.objects.link(cam)
scene.camera = cam

bpy.ops.wm.save_as_mainfile(filepath=out_path)
print('saved', out_path)
