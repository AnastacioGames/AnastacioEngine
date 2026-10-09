# Cria uma cena de teste para o grupo 1 e o PH2 de docs/auditoria-suspeitos.md:
# 200 postes com 3 filhos cada, regravados todo frame com a MESMA posicao/rotacao por um script
# (caso do atuador "Set position"), e 150 caixas dinamicas que caem e dormem com "Use Frame Rate" ligado.
#   AnastacioEngine.exe -b --factory-startup --python criar_cena_grava_igual.py -- saida.range
import bpy
import sys

out = sys.argv[sys.argv.index('--') + 1]
scene = bpy.context.scene
for ob in list(scene.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.use_frame_rate = True

# Sem material o mesh nao aparece no jogo.
mat = bpy.data.materials.new('cinza')
mat.diffuse_color = (0.7, 0.7, 0.7)


def com_material(ob):
    ob.data.materials.append(mat)


bpy.ops.mesh.primitive_plane_add(radius=60, location=(0, 0, 0))
com_material(scene.objects.active)

# Postes: pai + 3 filhos, todos sem fisica (so culling), regravados pelo script.
for i in range(200):
    bpy.ops.mesh.primitive_cube_add(radius=0.3, location=((i % 20) * 2 - 19, (i // 20) * 2 - 30, 0.3))
    pai = scene.objects.active
    pai.name = 'poste%03d' % i
    com_material(pai)
    pai.game.physics_type = 'NO_COLLISION'
    for k in range(3):
        bpy.ops.mesh.primitive_cube_add(radius=0.15, location=(pai.location.x, pai.location.y, 0.9 + k * 0.4))
        filho = scene.objects.active
        com_material(filho)
        filho.game.physics_type = 'NO_COLLISION'
        filho.parent = pai
        filho.matrix_parent_inverse = pai.matrix_world.inverted()

# Caixas dinamicas: caem de pouca altura e dormem em ~2 s.
for i in range(150):
    bpy.ops.mesh.primitive_cube_add(radius=0.4, location=((i % 15) * 2 - 14, (i // 15) * 2 + 4, 0.6))
    caixa = scene.objects.active
    com_material(caixa)
    caixa.game.physics_type = 'RIGID_BODY'

texto = bpy.data.texts.new('grava_igual.py')
texto.write('''import bge, os
def tick(cont):
    scene = bge.logic.getCurrentScene()
    lista = scene.get('postes')
    if lista is None:
        lista = scene['postes'] = [o for o in scene.objects if o.name.startswith('poste')]
        # O runtime nao mostra o print; grava num arquivo para conferir que o script roda.
        log = os.environ.get('GRAVA_LOG')
        if log:
            with open(log, 'w') as f:
                f.write('postes %d' % len(lista))
    for o in lista:
        o.localPosition = o.localPosition.copy()
        o.localOrientation = o.localOrientation.copy()
''')

ctrl = bpy.data.objects.new('controle', None)
scene.objects.link(ctrl)
scene.objects.active = ctrl
bpy.ops.logic.sensor_add(type='ALWAYS', name='always', object='controle')
bpy.ops.logic.controller_add(type='PYTHON', name='py', object='controle')
ctrl.game.sensors['always'].use_pulse_true_level = True
c = ctrl.game.controllers['py']
c.mode = 'MODULE'
c.module = 'grava_igual.tick'
ctrl.game.sensors['always'].link(c)

cam = bpy.data.objects.new('camera', bpy.data.cameras.new('camera'))
cam.location = (0, -60, 40)
cam.rotation_euler = (0.9, 0, 0)
scene.objects.link(cam)
scene.camera = cam

sol = bpy.data.objects.new('sol', bpy.data.lamps.new('sol', 'SUN'))
sol.rotation_euler = (0.6, 0.3, 0)
scene.objects.link(sol)
# Sem nevoa: a cena e grande e os postes do fundo sumiam.
if scene.world is None:
    scene.world = bpy.data.worlds.new('mundo')
scene.world.mist_settings.use_mist = False

bpy.ops.wm.save_as_mainfile(filepath=out, check_existing=False)
print('CENA salva', out)
