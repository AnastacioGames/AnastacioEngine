"""CV3 correctness scene (not a benchmark): valida anim_needs_update/BL_ArmatureObject::TickCullSkip
em KX_Scene.cpp. Um armature com uma acao ciclica (Action Actuator) toca uma malha deformada por
ARMATURE; a camera so enquadra um marcador visivel, nunca o armature, que fica sempre culled.
Espera-se: pose/skin pulados na maioria dos frames (updateNotifies/boundsPushes ~0), um update
completo forcado a cada CULL_SKIP_FORCE_INTERVAL (15) frames seguidos, e update imediato no frame
em que o marcador move a camera e o armature passa a ficar visivel.
Generate: AnastacioEngine.exe -b --factory-startup --python <this> -- <scene.range>
Run: player grava JSON com amostras por frame de updateNotifies/boundsPushes/cullingVisible.
"""
import bpy, sys
from mathutils import Vector
out = sys.argv[sys.argv.index('--') + 1]
s = bpy.context.scene
for o in list(s.objects): bpy.data.objects.remove(o, do_unlink=True)
s.render.engine = 'BLENDER_GAME'
s.game_settings.use_frame_rate = False
s.game_settings.vsync = 'OFF'
s.render.resolution_x = 640; s.render.resolution_y = 360; s.render.resolution_percentage = 100
s.frame_start = 1; s.frame_end = 20

mat_floor = bpy.data.materials.new('Floor'); mat_floor.diffuse_color = (0.6, 0.6, 0.6)
mat_char = bpy.data.materials.new('Char'); mat_char.diffuse_color = (0.9, 0.2, 0.2)
mat_marker = bpy.data.materials.new('Marker'); mat_marker.diffuse_color = (0.2, 0.9, 0.3)

bpy.ops.mesh.primitive_plane_add(radius=8, location=(0, 0, 0))
floor = bpy.context.object; floor.name = 'floor'
floor.data.materials.append(mat_floor); floor.game.physics_type = 'STATIC'

# personagem deformado por armature, bem longe do enquadramento inicial da camera -> sempre culled
bpy.ops.mesh.primitive_cylinder_add(vertices=12, depth=2, radius=0.35, location=(20, 0, 1))
char = bpy.context.object; char.name = 'char_mesh'
char.data.materials.append(mat_char)
char.game.physics_type = 'NO_COLLISION'

bpy.ops.object.armature_add(location=(20, 0, 1))
arm = bpy.context.object; arm.name = 'char_arm'
mod = char.modifiers.new('arm', 'ARMATURE'); mod.object = arm
vg = char.vertex_groups.new('Bone'); vg.add(list(range(len(char.data.vertices))), 1.0, 'REPLACE')
char.parent = arm
arm.game.physics_type = 'NO_COLLISION'

# acao ciclica no osso -> mantem o armature em m_animatedlist (GetDoAnimations() true)
s.objects.active = arm
bpy.ops.object.mode_set(mode='POSE')
bone = arm.pose.bones[0]
bone.rotation_mode = 'XYZ'
arm.animation_data_create()
action = bpy.data.actions.new('Swing')
arm.animation_data.action = action
s.frame_set(1); bone.rotation_euler = (0, 0, 0); bone.keyframe_insert('rotation_euler', frame=1)
s.frame_set(20); bone.rotation_euler = (1.2, 0, 0); bone.keyframe_insert('rotation_euler', frame=20)
bpy.ops.object.mode_set(mode='OBJECT')
s.frame_set(1)

bpy.ops.logic.sensor_add(type='ALWAYS', object=arm.name)
bpy.ops.logic.controller_add(type='LOGIC_AND', object=arm.name)
bpy.ops.logic.actuator_add(type='ACTION', object=arm.name)
arm_sens = arm.game.sensors[0]; arm_sens.use_pulse_true_level = True
arm_ctrl = arm.game.controllers[0]
arm_act = arm.game.actuators[0]
arm_act.action = action; arm_act.play_mode = 'LOOPEND'; arm_act.frame_start = 1; arm_act.frame_end = 20
arm_sens.link(arm_ctrl)
arm_ctrl.link(actuator=arm_act)

# marcador visivel -- unico objeto que a camera enquadra no inicio
bpy.ops.mesh.primitive_cube_add(radius=0.4, location=(0, 0, 1))
marker = bpy.context.object; marker.name = 'marker'
marker.data.materials.append(mat_marker); marker.game.physics_type = 'NO_COLLISION'

sun = bpy.data.objects.new('sun', bpy.data.lamps.new('sun', 'SUN'))
s.objects.link(sun); sun.rotation_euler = (0.6, 0.2, 0)
if s.world is None: s.world = bpy.data.worlds.new('World')
s.world.mist_settings.use_mist = False

cam = bpy.data.objects.new('camera', bpy.data.cameras.new('camera'))
s.objects.link(cam); s.camera = cam
cam.location = (0, -10, 4); cam.data.lens = 35
cam.rotation_euler = (Vector((0, 0, 1)) - cam.location).to_track_quat('-Z', 'Y').to_euler()

t = bpy.data.texts.new('cv3.py')
t.write('''import bge, json, os
frame = [0]
log = []
def tick(cont):
    frame[0] += 1
    f = frame[0]
    sc = bge.logic.getCurrentScene()
    arm = sc.objects['char_arm']
    # fase 1 (1-100): camera nunca enquadra o armature (culled o tempo todo).
    # fase 2 (101-180): move o armature para dentro do enquadramento da camera.
    if f == 101:
        arm.worldPosition = (0, 2, 1)
    # pose_matrix e o resultado do BKE_pose_where_is da pose resolvida; so muda quando
    # BL_Action::Update roda com applyToObject=True (anim_needs_update retornou True).
    pm = arm.channels['Bone'].pose_matrix
    pose_sample = round(pm[1][1], 5)  # cos(bone X rotation): 1.0 at bind pose, ~0.362 at 1.2 rad
    char = sc.objects['char_mesh']
    st = dict(bge.logic.getRenderStats())
    log.append((f, pose_sample, round(char.worldPosition.y, 2), st.get('cullingVisible', -1), st.get('cullingTotal', -1)))
    if f >= 180:
        with open(os.environ['CV3_LOG'], 'w') as fp:
            json.dump(log, fp)
        bge.logic.endGame()
''')
s.objects.active = cam
bpy.ops.logic.sensor_add(type='ALWAYS', object=cam.name)
bpy.ops.logic.controller_add(type='PYTHON', object=cam.name)
cam_sens = cam.game.sensors[0]; cam_sens.use_pulse_true_level = True
cam_ctrl = cam.game.controllers[0]; cam_ctrl.mode = 'MODULE'; cam_ctrl.module = 'cv3.tick'
cam_sens.link(cam_ctrl)

bpy.ops.wm.save_as_mainfile(filepath=out)
