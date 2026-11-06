# Cena da reproducao exata do Rec Play: Pai e Filho sem logica propria; o Observador os move com REC_MOVER=1 e
# registra, a cada passo, a pose final do passo anterior. Usar com tools/debug/editor_rec_exato.py.
#   AnastacioEngine.exe -b --factory-startup --python criar_cena_rec_exato.py -- saida.range
import bpy
import sys
from mathutils import Vector

out = sys.argv[sys.argv.index('--') + 1]
scene = bpy.context.scene
for ob in list(scene.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.use_frame_rate = True


def cubo(nome, cor, local):
    bpy.ops.mesh.primitive_cube_add(radius=0.5, location=local)
    ob = scene.objects.active
    ob.name = nome
    mat = bpy.data.materials.new(nome)
    mat.diffuse_color = cor
    ob.data.materials.append(mat)
    ob.game.physics_type = 'NO_COLLISION'
    return ob


pai = cubo('Pai', (0.1, 0.3, 0.9), (3, 0, 2))
pai.ae_rec_actor = True
filho = cubo('Filho', (0.95, 0.8, 0.1), (4.5, 0, 2))
filho.parent = pai
filho.matrix_parent_inverse = pai.matrix_world.inverted()
filho.ae_rec_actor = True
obs = cubo('Observador', (0.9, 0.1, 0.1), (0, 0, -3))

texto = bpy.data.texts.new('rec_exato.py')
texto.write('''import json, math, os
def tick(cont):
    own = cont.owner
    cena = own.scene
    pai, filho = cena.objects['Pai'], cena.objects['Filho']
    log = own.get('log')
    if log is None:
        log = own['log'] = []
    log.append({o.name: [list(r) for r in o.worldTransform] for o in (pai, filho)})
    with open(os.environ['REC_LOG'], 'w') as f:
        json.dump(log, f)
    if os.environ.get('REC_MOVER') == '1':
        a = len(log) / 60.0
        pai.worldPosition = (3 * math.cos(a), 3 * math.sin(a), 2 + math.sin(a * 2))
        pai.applyRotation((0.03, 0.05, 0.07), True)
        filho.applyRotation((0, 0, 0.1), True)
''')
scene.objects.active = obs
bpy.ops.logic.sensor_add(type='ALWAYS', object=obs.name)
bpy.ops.logic.controller_add(type='PYTHON', object=obs.name)
sensor, controlador = obs.game.sensors[-1], obs.game.controllers[-1]
sensor.use_pulse_true_level = True
controlador.mode = 'MODULE'
controlador.module = 'rec_exato.tick'
sensor.link(controlador)

bpy.ops.object.lamp_add(type='SUN', location=(4, -6, 12), rotation=(0.7, 0.2, 0.4))
bpy.ops.object.camera_add(location=(0, -18, 10))
camera = scene.objects.active
camera.rotation_euler = (Vector((0, 0, 1)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
scene.camera = camera
bpy.ops.wm.save_as_mainfile(filepath=out)
