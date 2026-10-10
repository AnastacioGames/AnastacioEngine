"""Lote CV4/PH5/GL7/GL8: smoke test de comportamento.

AnastacioEngine.exe -b --factory-startup --python criar_cena_lote_auditoria.py -- teste.range
LOTE_RESULT recebe o JSON.
"""
import bpy, sys, math
from mathutils import Vector

out = sys.argv[sys.argv.index('--') + 1]
scene = bpy.context.scene
for obj in list(scene.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
scene.render.engine = 'BLENDER_GAME'

def logic(obj, name, module, pulse=True):
    scene.objects.active = obj
    bpy.ops.logic.sensor_add(type='ALWAYS', name='t_' + name, object=obj.name)
    bpy.ops.logic.controller_add(type='PYTHON', name='c_' + name, object=obj.name)
    s = obj.game.sensors['t_' + name]; s.use_pulse_true_level = pulse
    c = obj.game.controllers['c_' + name]; c.mode = 'MODULE'; c.module = module
    s.link(c)

# chao
bpy.ops.mesh.primitive_plane_add(radius=20, location=(0, 0, 0))
# personagem (PH5)
bpy.ops.mesh.primitive_cube_add(radius=0.5, location=(-6, 0, 3))
ch = scene.objects.active; ch.name = 'char'; ch.game.physics_type = 'CHARACTER'
# alvo movel para Near/Ray
bpy.ops.mesh.primitive_cube_add(radius=0.5, location=(6, 8, 1))
tgt = scene.objects.active; tgt.name = 'target'; tgt.game.physics_type = 'STATIC'; tgt.game.use_actor = True
tgt.game.properties.new('alvo', type='BOOL') if hasattr(tgt.game.properties, 'new') else None
# dono dos sensores (parado)
bpy.ops.mesh.primitive_cube_add(radius=0.3, location=(6, 0, 1))
own = scene.objects.active; own.name = 'owner'; own.game.physics_type = 'NO_COLLISION'
scene.objects.active = own
bpy.ops.logic.sensor_add(type='NEAR', name='near', object=own.name)
own.game.sensors['near'].distance = 3.0
own.game.sensors['near'].reset_distance = 3.5
bpy.ops.logic.sensor_add(type='RAY', name='ray', object=own.name)
r = own.game.sensors['ray']; r.axis = 'YAXIS'; r.range = 20.0
if hasattr(r, 'cone_angle'): r.cone_angle = 0.5
bpy.ops.logic.controller_add(type='LOGIC_AND', name='and', object=own.name)
own.game.sensors['near'].link(own.game.controllers['and'])
r.link(own.game.controllers['and'])
# armatures (CV4): uma parada, uma girando
for nm, x in (('arm_hold', -2), ('arm_move', 2)):
    bpy.ops.object.armature_add(location=(x, -4, 0))
    arm = scene.objects.active; arm.name = nm
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, depth=2, radius=0.3, location=(x, -4, 1))
    m = scene.objects.active; m.name = nm + '_mesh'
    mod = m.modifiers.new('arm', 'ARMATURE'); mod.object = arm
    vg = m.vertex_groups.new('Bone'); vg.add(list(range(len(m.data.vertices))), 1.0, 'REPLACE')
    m.parent = arm
cam = bpy.data.objects.new('camera', bpy.data.cameras.new('camera'))
cam.location = (0, -20, 12)
cam.rotation_euler = (-Vector(cam.location)).to_track_quat('-Z', 'Y').to_euler()
scene.objects.link(cam); scene.camera = cam
scene.objects.link(bpy.data.objects.new('sun', bpy.data.lamps.new('sun', 'SUN')))

text = bpy.data.texts.new('lote.py')
text.write('''import bge, json, os, math
frame = 0
log = []
def tick(cont):
    global frame
    frame += 1
    sc = bge.logic.getCurrentScene()
    own = sc.objects['owner']; tgt = sc.objects['target']; ch = sc.objects['char']
    near = own.sensors['near']; ray = own.sensors['ray']
    if frame == 60: tgt.worldPosition = (6, 2, 1)
    if frame == 100: own.worldPosition.x += 10   # dono move: near deve sair
    if frame == 140: own.worldPosition.x -= 10
    if 150 <= frame < 190: bge.constraints.getCharacter(ch).walkDirection = (0.05, 0, 0)
    if frame == 190: bge.constraints.getCharacter(ch).walkDirection = (0, 0, 0)
    arm = sc.objects['arm_move']
    ch_b = arm.channels['Bone']; ch_b.rotation_mode = 1
    ch_b.rotation_euler = (math.sin(frame * 0.1), 0, 0); arm.update()
    if frame % 10 == 0:
        log.append(dict(f=frame, near=near.positive, ray=ray.positive,
                        hit=(ray.hitObject.name if ray.hitObject else None),
                        char=[round(v, 3) for v in ch.worldPosition]))
    if frame == 220:
        with open(os.environ['LOTE_RESULT'], 'w') as d: json.dump(log, d)
        bge.logic.endGame()
''')
logic(cam, 'lote', 'lote.tick')
bpy.ops.wm.save_as_mainfile(filepath=out, check_existing=False)
