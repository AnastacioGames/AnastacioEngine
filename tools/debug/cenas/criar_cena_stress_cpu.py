# Cena de carga de CPU para o plano de melhorias de CPU (branch cpu-threads): personagens com skinning
# em CPU, corpos rigidos que nao dormem, sol com CSM + point com sombra, sensores Near/Ray/MouseOver e
# textos atualizados por propriedade. Encerra sozinha depois de STRESS_SECONDS (padrao 10) e grava em
# STRESS_LOG o numero de frames, para conferir que o script rodou.
#   AnastacioEngine.exe -b --factory-startup --python criar_cena_stress_cpu.py -- saida.range
import bpy
import bmesh
import math
import sys
from mathutils import Vector

out = sys.argv[sys.argv.index('--') + 1]
scene = bpy.context.scene
for ob in list(scene.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.use_frame_rate = False
scene.game_settings.physics_engine = 'BULLET'
scene.render.fps = 60


def material(nome, cor):
    mat = bpy.data.materials.new(nome)
    mat.diffuse_color = cor
    return mat


mat_chao = material('chao', (0.35, 0.35, 0.38))
mat_corpo = material('corpo', (0.85, 0.45, 0.2))
mat_caixa = material('caixa', (0.2, 0.55, 0.85))
mat_sensor = material('sensor', (0.3, 0.8, 0.3))
mat_texto = material('texto', (1.0, 1.0, 1.0))

bpy.ops.mesh.primitive_plane_add(radius=40, location=(0, 0, 0))
chao = scene.objects.active
chao.name = 'chao'
chao.data.materials.append(mat_chao)
chao.game.physics_type = 'STATIC'

# Paredes baixas: as caixas ficam rolando dentro de um cercado em vez de se espalhar.
for x, y, sx, sy in ((0, 12, 12, 0.3), (0, -12, 12, 0.3), (12, 0, 0.3, 12), (-12, 0, 0.3, 12)):
    bpy.ops.mesh.primitive_cube_add(radius=1, location=(x + 20, y, 1))
    parede = scene.objects.active
    parede.scale = (sx, sy, 1)
    parede.data.materials.append(mat_chao)
    parede.game.physics_type = 'STATIC'

# --- Personagens: armature de 3 ossos + esfera alongada (~2k vertices) deformada na CPU. ---
arm_data = bpy.data.armatures.new('esqueleto')
arm_base = bpy.data.objects.new('arm_base', arm_data)
scene.objects.link(arm_base)
scene.objects.active = arm_base
bpy.ops.object.mode_set(mode='EDIT')
anterior = None
for k in range(3):
    osso = arm_data.edit_bones.new('b%d' % k)
    osso.head = (0, 0, k * 1.0)
    osso.tail = (0, 0, (k + 1) * 1.0)
    if anterior:
        osso.parent = anterior
        osso.use_connect = True
    anterior = osso
bpy.ops.object.mode_set(mode='OBJECT')

acao = bpy.data.actions.new('balanco')
arm_base.animation_data_create()
arm_base.animation_data.action = acao
for k in (1, 2):
    pb = arm_base.pose.bones['b%d' % k]
    pb.rotation_mode = 'XYZ'
    for frame, ang in ((1, -0.6), (20, 0.6), (40, -0.6)):
        pb.rotation_euler = (ang, 0, ang * 0.5)
        pb.keyframe_insert('rotation_euler', frame=frame)
arm_base.animation_data.action = None

malha = bpy.data.meshes.new('corpo')
bm = bmesh.new()
bmesh.ops.create_uvsphere(bm, u_segments=64, v_segments=32, diameter=0.5)
for v in bm.verts:
    v.co.z = (v.co.z + 0.5) * 3.0
bm.to_mesh(malha)
bm.free()
malha.materials.append(mat_corpo)

for i in range(30):
    pos = Vector(((i % 6) * 2.5 - 6.25, (i // 6) * 2.5 - 5, 0))
    arm = bpy.data.objects.new('arm%02d' % i, arm_data)
    arm.location = pos
    scene.objects.link(arm)
    corpo = bpy.data.objects.new('corpo%02d' % i, malha)
    corpo.location = pos
    scene.objects.link(corpo)
    for k in range(3):
        grupo = corpo.vertex_groups.new('b%d' % k)
        for v in malha.vertices:
            peso = max(0.0, 1.0 - abs(v.co.z - (k + 0.5)))
            if peso > 0:
                grupo.add([v.index], peso, 'REPLACE')
    mod = corpo.modifiers.new('arm', 'ARMATURE')
    mod.object = arm
    corpo.parent = arm
    corpo.matrix_parent_inverse = arm.matrix_world.inverted()
    corpo.game.physics_type = 'NO_COLLISION'
    arm.game.physics_type = 'NO_COLLISION'

    scene.objects.active = arm
    bpy.ops.logic.sensor_add(type='ALWAYS', name='sempre', object=arm.name)
    bpy.ops.logic.controller_add(type='LOGIC_AND', name='e', object=arm.name)
    bpy.ops.logic.actuator_add(type='ACTION', name='anim', object=arm.name)
    atu = arm.game.actuators['anim']
    atu.action = acao
    atu.frame_start = 1
    atu.frame_end = 40
    atu.play_mode = 'LOOPEND'
    arm.game.sensors['sempre'].link(arm.game.controllers['e'])
    arm.game.actuators['anim'].link(arm.game.controllers['e'])

bpy.data.objects.remove(arm_base, do_unlink=True)

# --- 300 corpos rigidos que nunca dormem, caindo dentro do cercado. ---
for i in range(300):
    bpy.ops.mesh.primitive_cube_add(radius=0.35, location=(20 + (i % 10) * 2 - 9, (i // 10) % 10 * 2 - 9, 2 + (i // 100) * 1.5))
    caixa = scene.objects.active
    caixa.name = 'caixa%03d' % i
    caixa.data.materials.append(mat_caixa)
    caixa.game.physics_type = 'RIGID_BODY'
    caixa.game.use_sleep = True

# --- 20 sensores Near + Ray + MouseOver ligados a um AND (sem ligacao o sensor nem e avaliado). ---
for i in range(20):
    bpy.ops.mesh.primitive_cube_add(radius=0.3, location=(-15 + (i % 5) * 2, (i // 5) * 2 - 4, 0.3))
    sensor = scene.objects.active
    sensor.name = 'sensor%02d' % i
    sensor.data.materials.append(mat_sensor)
    sensor.game.physics_type = 'STATIC'
    bpy.ops.logic.sensor_add(type='NEAR', name='perto', object=sensor.name)
    bpy.ops.logic.sensor_add(type='RAY', name='raio', object=sensor.name)
    bpy.ops.logic.sensor_add(type='MOUSE', name='mouse', object=sensor.name)
    bpy.ops.logic.controller_add(type='LOGIC_AND', name='e', object=sensor.name)
    sensor.game.sensors['perto'].distance = 30
    sensor.game.sensors['raio'].range = 30
    sensor.game.sensors['mouse'].mouse_event = 'MOUSEOVER'
    for nome in ('perto', 'raio', 'mouse'):
        sensor.game.sensors[nome].use_pulse_true_level = True
        sensor.game.sensors[nome].link(sensor.game.controllers['e'])

# --- 20 textos com a propriedade Text trocada todo frame pelo script. ---
for i in range(20):
    bpy.ops.object.text_add(location=(-15 + (i % 5) * 2, (i // 5) * 2 + 6, 0.1))
    texto = scene.objects.active
    texto.name = 'texto%02d' % i
    texto.data.materials.append(mat_texto)
    texto.data.size = 0.5
    bpy.ops.object.game_property_new(type='STRING', name='Text')

codigo = bpy.data.texts.new('stress.py')
codigo.write('''import bge, os
def tick(cont):
    logic = bge.logic
    scene = logic.getCurrentScene()
    dono = cont.owner
    dono['frames'] += 1
    for o in scene.objects:
        if o.name.startswith('texto'):
            o['Text'] = str(dono['frames'])
    limite = float(os.environ.get('STRESS_SECONDS', '10'))
    if logic.getRealTime() - dono['inicio'] >= limite:
        log = os.environ.get('STRESS_LOG')
        if log:
            with open(log, 'w') as f:
                f.write('frames %d segundos %.2f\\n' % (dono['frames'], logic.getRealTime() - dono['inicio']))
        logic.endGame()

def inicio(cont):
    cont.owner['inicio'] = bge.logic.getRealTime()
''')

ctrl = bpy.data.objects.new('controle', None)
scene.objects.link(ctrl)
scene.objects.active = ctrl
bpy.ops.object.game_property_new(type='INT', name='frames')
bpy.ops.object.game_property_new(type='FLOAT', name='inicio')
bpy.ops.logic.sensor_add(type='ALWAYS', name='uma_vez', object='controle')
bpy.ops.logic.sensor_add(type='ALWAYS', name='sempre', object='controle')
bpy.ops.logic.controller_add(type='PYTHON', name='ini', object='controle')
bpy.ops.logic.controller_add(type='PYTHON', name='tick', object='controle')
ctrl.game.sensors['sempre'].use_pulse_true_level = True
ini = ctrl.game.controllers['ini']
ini.mode = 'MODULE'
ini.module = 'stress.inicio'
ini.use_priority = True
tick = ctrl.game.controllers['tick']
tick.mode = 'MODULE'
tick.module = 'stress.tick'
ctrl.game.sensors['uma_vez'].link(ini)
ctrl.game.sensors['sempre'].link(tick)

# --- Camera, luzes e mundo. ---
cam = bpy.data.objects.new('camera', bpy.data.cameras.new('camera'))
cam.data.type = 'PERSP'
cam.data.lens = 16
cam.location = (0, -30, 22)
cam.rotation_euler = (Vector((2, 0, 0)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
scene.objects.link(cam)
scene.camera = cam

sol = bpy.data.objects.new('sol', bpy.data.lamps.new('sol', 'SUN'))
sol.rotation_euler = (math.radians(50), math.radians(20), 0)
sol.data.use_shadow = True
sol.data.use_csm_shadow = True
scene.objects.link(sol)

ponto = bpy.data.objects.new('ponto', bpy.data.lamps.new('ponto', 'POINT'))
ponto.location = (0, 0, 6)
ponto.data.use_shadow = True
ponto.data.distance = 25
scene.objects.link(ponto)

if scene.world is None:
    scene.world = bpy.data.worlds.new('mundo')
scene.world.mist_settings.use_mist = False

bpy.ops.wm.save_as_mainfile(filepath=out, check_existing=False)
print('CENA salva', out)
