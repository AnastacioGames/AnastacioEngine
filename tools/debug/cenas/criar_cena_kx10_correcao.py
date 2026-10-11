"""KX10 correctness scene (not a benchmark): valida AutoShadowStillValid/BuildShadowCullCache
em condicoes realistas -- Spot com Auto Shadow, um objeto deformado por armature sempre dentro
do alcance (deve forcar invalidacao todo frame mesmo com a pose parada), um objeto rigido que
entra/sai do alcance via Python (deve invalidar so nas transicoes) e um objeto numa layer fora
do shadow_layer do Spot (nunca deve contar como caster nem forcar update).
Generate: AnastacioEngine.exe -b --factory-startup --python <this> -- <scene.range>
Run: player grava JSON com amostras por frame de lightsShadowUpdated e a fase do teste.
"""
import bpy, sys
from mathutils import Vector
out = sys.argv[sys.argv.index('--') + 1]
sem_armature = '--sem-armature' in sys.argv
s = bpy.context.scene
for o in list(s.objects): bpy.data.objects.remove(o, do_unlink=True)
s.render.engine = 'BLENDER_GAME'
s.game_settings.use_frame_rate = False
s.game_settings.vsync = 'OFF'
s.render.resolution_x = 640; s.render.resolution_y = 360; s.render.resolution_percentage = 100

mat_floor = bpy.data.materials.new('Floor'); mat_floor.diffuse_color = (0.6, 0.6, 0.6)
mat_char = bpy.data.materials.new('Char'); mat_char.diffuse_color = (0.9, 0.2, 0.2)
mat_mover = bpy.data.materials.new('Mover'); mat_mover.diffuse_color = (0.2, 0.9, 0.3)
mat_off = bpy.data.materials.new('OffLayer'); mat_off.diffuse_color = (0.2, 0.3, 0.9)

bpy.ops.mesh.primitive_plane_add(radius=6, location=(0, 0, 0))
floor = bpy.context.object; floor.name = 'floor'
floor.data.materials.append(mat_floor); floor.game.physics_type = 'STATIC'

# personagem deformado por armature, parado mas sempre com modifier ARMATURE -> GetDeformer() != null
# (--sem-armature gera a mesma cena so com mesh rigida, pra isolar o teste do 'mover')
bpy.ops.mesh.primitive_cylinder_add(vertices=12, depth=2, radius=0.35, location=(-1.5, 0, 1))
char = bpy.context.object; char.name = 'char_mesh'
char.data.materials.append(mat_char)
char.game.physics_type = 'NO_COLLISION'
if not sem_armature:
    bpy.ops.object.armature_add(location=(-1.5, 0, 1))
    arm = bpy.context.object; arm.name = 'char_arm'
    mod = char.modifiers.new('arm', 'ARMATURE'); mod.object = arm
    vg = char.vertex_groups.new('Bone'); vg.add(list(range(len(char.data.vertices))), 1.0, 'REPLACE')
    char.parent = arm
    arm.game.physics_type = 'NO_COLLISION'

# objeto rigido que entra/sai do alcance via Python (sem deformer)
bpy.ops.mesh.primitive_cube_add(radius=0.4, location=(0, 0, 1))
mover = bpy.context.object; mover.name = 'mover'
mover.data.materials.append(mat_mover); mover.game.physics_type = 'NO_COLLISION'

# objeto numa layer fora do shadow_layer do Spot -- nao deve contar como caster
bpy.ops.mesh.primitive_cube_add(radius=0.4, location=(2.5, 1.5, 1))
offlayer = bpy.context.object; offlayer.name = 'off_layer'
offlayer.data.materials.append(mat_off); offlayer.game.physics_type = 'NO_COLLISION'
offlayer.layers = [i == 2 for i in range(20)]  # layer 3 (0-index 2)

spot = bpy.data.objects.new('spot', bpy.data.lamps.new('spot', 'SPOT'))
s.objects.link(spot)
spot.location = (0, -4, 5)
spot.rotation_euler = (Vector((0, 0, 0)) - Vector((0, -4, 5))).to_track_quat('-Z', 'Y').to_euler()
spot.data.distance = 12
spot.data.spot_size = 1.3
spot.data.use_shadow = True
spot.data.use_auto_shadow_update = True
spot.layers = [i == 0 for i in range(20)]  # so a layer 1 conta como caster (exclui off_layer)

sun = bpy.data.objects.new('sun', bpy.data.lamps.new('sun', 'SUN'))
s.objects.link(sun); sun.rotation_euler = (0.6, 0.2, 0)
if s.world is None: s.world = bpy.data.worlds.new('World')
s.world.mist_settings.use_mist = False

cam = bpy.data.objects.new('camera', bpy.data.cameras.new('camera'))
s.objects.link(cam); s.camera = cam
cam.location = (0, -14, 7); cam.data.lens = 25
cam.rotation_euler = (Vector((0, 0, 1)) - cam.location).to_track_quat('-Z', 'Y').to_euler()

t = bpy.data.texts.new('kx10.py')
t.write('''import bge, json, os
frame = [0]
log = []
def tick(cont):
    frame[0] += 1
    f = frame[0]
    sc = bge.logic.getCurrentScene()
    mover = sc.objects['mover']
    # fases: 1-40 dentro do alcance (perto do spot); 41-80 fora do alcance (longe);
    # 81-120 dentro de novo -- cada transicao de fase deve forcar 1 update do Spot.
    if f <= 40:
        mover.worldPosition = (0, 0, 1)
        phase = 'perto'
    elif f <= 80:
        mover.worldPosition = (0, 40, 1)
        phase = 'longe'
    else:
        mover.worldPosition = (0, 0, 1)
        phase = 'perto2'
    st = dict(bge.logic.getRenderStats())
    if f > 3:
        log.append((f, phase, st.get('lightsShadowUpdated', -1)))
    if f >= 150:
        with open(os.environ['KX10_LOG'], 'w') as fp:
            json.dump(log, fp)
        bge.logic.endGame()
''')
s.objects.active = cam
bpy.ops.logic.sensor_add(type='ALWAYS', object=cam.name)
bpy.ops.logic.controller_add(type='PYTHON', object=cam.name)
sens = cam.game.sensors[0]; sens.use_pulse_true_level = True
ctrl = cam.game.controllers[0]; ctrl.mode = 'MODULE'; ctrl.module = 'kx10.tick'
sens.link(ctrl)

bpy.ops.wm.save_as_mainfile(filepath=out)
