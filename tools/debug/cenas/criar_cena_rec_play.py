# Cena do Rec Play: Cubo (corpo rigido, quaternion), Girador (script, ordem ZXY, angulos grandes) e
# Filho (com pai). O script registra a matriz real de cada objeto em REC_LOG e encerra o jogo sozinho.
# Usar com tools/debug/editor_rec_play.py.
#   AnastacioEngine.exe -b --factory-startup --python criar_cena_rec_play.py -- saida.range
import bpy
import sys
from mathutils import Vector

out = sys.argv[sys.argv.index('--') + 1]
scene = bpy.context.scene
for ob in list(scene.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.use_frame_rate = True
scene.frame_start, scene.frame_end = 1, 125


def material(ob, nome, cor):
    mat = bpy.data.materials.new(nome)
    mat.diffuse_color = cor
    ob.data.materials.append(mat)


bpy.ops.mesh.primitive_plane_add(radius=12, location=(0, 0, 0))
chao = scene.objects.active
chao.name = 'Chao'
material(chao, 'chao', (0.35, 0.4, 0.35))
chao.game.physics_type = 'STATIC'

bpy.ops.mesh.primitive_cube_add(radius=0.6, location=(-3, 0, 6), rotation=(0.5, 0.3, 0.2))
cubo = scene.objects.active
cubo.name = 'Cubo'
material(cubo, 'vermelho', (0.9, 0.1, 0.1))
cubo.game.physics_type = 'RIGID_BODY'
cubo.rotation_mode = 'QUATERNION'
cubo.ae_rec_actor = True

bpy.ops.mesh.primitive_cube_add(radius=0.5, location=(3, 0, 2))
girador = scene.objects.active
girador.name = 'Girador'
material(girador, 'azul', (0.1, 0.3, 0.9))
girador.game.physics_type = 'NO_COLLISION'
girador.rotation_mode = 'ZXY'
girador.ae_rec_actor = True

bpy.ops.mesh.primitive_cube_add(radius=0.25, location=(4.5, 0, 2))
filho = scene.objects.active
filho.name = 'Filho'
material(filho, 'amarelo', (0.95, 0.8, 0.1))
filho.game.physics_type = 'NO_COLLISION'
filho.parent = girador
filho.matrix_parent_inverse = girador.matrix_world.inverted()
filho.ae_rec_actor = True

texto = bpy.data.texts.new('rec_teste.py')
texto.write('''import bge, json, math, os
PASSOS = 300
def tick(cont):
    own = cont.owner
    n = own.get('n', 0)
    own['n'] = n + 1
    a = n / 60.0
    own.worldPosition = (3 * math.cos(a), 3 * math.sin(a), 2 + math.sin(a * 2))
    own.applyRotation((0.03, 0.05, 0.07), True)
    filho = own.scene.objects['Filho']
    filho.applyRotation((0, 0, 0.1), True)
    log = own.get('log')
    if log is None:
        log = own['log'] = []
    log.append({o.name: [list(r) for r in o.worldTransform] for o in own.scene.objects
                if o.name in ('Cubo', 'Girador', 'Filho')})
    if n + 1 >= PASSOS:
        with open(os.environ['REC_LOG'], 'w') as f:
            json.dump(log, f)
        bge.logic.endGame()
''')
scene.objects.active = girador
bpy.ops.logic.sensor_add(type='ALWAYS', object=girador.name)
bpy.ops.logic.controller_add(type='PYTHON', object=girador.name)
sensor = girador.game.sensors[-1]
sensor.use_pulse_true_level = True
controller = girador.game.controllers[-1]
controller.mode = 'MODULE'
controller.module = 'rec_teste.tick'
sensor.link(controller)

bpy.ops.object.lamp_add(type='SUN', location=(0, -5, 12), rotation=(0.7, 0.2, 0.3))
bpy.ops.object.camera_add(location=(0, -16, 8))
camera = scene.objects.active
camera.data.type = 'PERSP'
camera.data.lens = 16
camera.rotation_euler = (Vector((0, 0, 2)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
scene.camera = camera
bpy.ops.wm.save_as_mainfile(filepath=out)
