# Cena do controle rapido do Rec Play: Andador (sem fisica, armature filha, Action AnimA), Personagem
# (Character) e Cubo (corpo rigido com logica: nao anda com WASD e prova que a contagem congela o mundo).
# Usar com tools/debug/editor_rec_wasd.py.
#   AnastacioEngine.exe -b --factory-startup --python criar_cena_rec_wasd.py -- saida.range
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


def cubo(nome, cor, local, raio=0.5):
    bpy.ops.mesh.primitive_cube_add(radius=raio, location=local)
    ob = scene.objects.active
    ob.name = nome
    material(ob, nome, cor)
    return ob


bpy.ops.mesh.primitive_plane_add(radius=30, location=(0, 0, 0))
chao = scene.objects.active
chao.name = 'Chao'
material(chao, 'chao', (0.35, 0.4, 0.35))
chao.game.physics_type = 'STATIC'

andador = cubo('Andador', (0.1, 0.3, 0.9), (0, 0, 1))
andador.game.physics_type = 'NO_COLLISION'
andador.ae_rec_actor = True
andador.ae_rec_action = 'AnimA'

personagem = cubo('Personagem', (0.9, 0.7, 0.1), (5, 0, 1))
personagem.game.physics_type = 'CHARACTER'
personagem.game.use_collision_bounds = True
personagem.ae_rec_actor = True

queda = cubo('Cubo', (0.9, 0.1, 0.1), (-5, 0, 6))
queda.game.physics_type = 'RIGID_BODY'
queda.ae_rec_actor = True

bpy.ops.object.armature_add(location=(0, 0, 2))
boneco = scene.objects.active
boneco.name = 'Boneco'
boneco.parent = andador
boneco.matrix_parent_inverse = andador.matrix_world.inverted()
boneco.animation_data_create()
osso = boneco.pose.bones[0]
osso.rotation_mode = 'XYZ'
acao = bpy.data.actions.new('AnimA')
acao.use_fake_user = True
boneco.animation_data.action = acao
for frame, valor in ((1, 0.0), (30, 1.5)):
    osso.rotation_euler = (valor, 0, 0)
    osso.keyframe_insert('rotation_euler', frame=frame)
boneco.animation_data.action = None
osso.rotation_euler = (0, 0, 0)
bpy.ops.object.mode_set(mode='OBJECT')

# Sem malha ligada a armature nao e atualizada no jogo.
corpo = cubo('Corpo', (0.6, 0.2, 0.8), (0, 0, 2.5), 0.3)
corpo.game.physics_type = 'NO_COLLISION'
corpo.vertex_groups.new('Bone').add([v.index for v in corpo.data.vertices], 1.0, 'REPLACE')
corpo.parent = boneco
corpo.parent_type = 'ARMATURE'
corpo.matrix_parent_inverse = boneco.matrix_world.inverted()
corpo.modifiers.new('Armature', 'ARMATURE').object = boneco

texto = bpy.data.texts.new('rec_wasd.py')
texto.write('''import os
def tick(cont):
    # REC_LOG: posicao real de cada ator durante o jogo, uma linha por passo.
    cena = cont.owner.scene
    with open(os.environ['REC_LOG'], 'a') as f:
        f.write(' '.join('%.3f,%.3f' % tuple((cena.objects.get(n) or cena.objects[n + 'X']).worldPosition)[:2] for n in ('Andador', 'Personagem')) + chr(10))
''')
bpy.ops.logic.sensor_add(type='ALWAYS', object=queda.name)
bpy.ops.logic.controller_add(type='PYTHON', object=queda.name)
sensor, controlador = queda.game.sensors[-1], queda.game.controllers[-1]
sensor.use_pulse_true_level = True
controlador.mode = 'MODULE'
controlador.module = 'rec_wasd.tick'
sensor.link(controlador)

bpy.ops.object.lamp_add(type='SUN', location=(4, -6, 12), rotation=(0.7, 0.2, 0.4))
bpy.ops.object.camera_add(location=(0, -18, 10))
camera = scene.objects.active
camera.rotation_euler = (Vector((0, 0, 1)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
camera.data.lens = 16
scene.camera = camera
scene.objects.active = andador
bpy.ops.wm.save_as_mainfile(filepath=out)
