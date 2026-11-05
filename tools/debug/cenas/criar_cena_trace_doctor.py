# Cena de teste do Trace Doctor etapa 2 (docs/plano-trace-doctor.md): 12 cubos estaticos com o mesmo
# material, Auto Static Batch desligado, e um objeto pesado On Demand convertido no frame 30. Fecha sozinha
# no frame 60. Uso:
#   AnastacioEngine.exe -b -P tools/debug/cenas/criar_cena_trace_doctor.py -- saida.range
import bpy
import sys

out = sys.argv[sys.argv.index('--') + 1]
scene = bpy.context.scene
for ob in list(scene.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.use_auto_static_batch = False

bpy.ops.object.camera_add(location=(0, -14, 6), rotation=(1.2, 0, 0))
scene.camera = scene.objects.active
bpy.ops.object.lamp_add(type='SUN', location=(0, 0, 10))

mat = bpy.data.materials.new('Pedra')
for i in range(12):
    bpy.ops.mesh.primitive_cube_add(radius=0.4, location=((i % 4) * 1.5 - 2.25, (i // 4) * 1.5, 0.4))
    ob = scene.objects.active
    ob.name = 'Pedra.%02d' % i
    ob.data.materials.append(mat)
    ob.game.physics_type = 'STATIC'

# Pesado o bastante para a conversao no jogo passar de 1 ms.
bpy.ops.mesh.primitive_uv_sphere_add(segments=256, ring_count=128, size=1.0, location=(0, 3, 2))
pesado = scene.objects.active
pesado.name = 'Pesado'
pesado.game_load_mode = 'ON_DEMAND'

bpy.ops.object.empty_add(location=(0, 0, 0))
ctl = scene.objects.active
ctl.name = 'Controle'
txt = bpy.data.texts.new('controle.py')
txt.write('''import range
def tick(cont):
    g = range.logic.globalDict
    f = g.get('frame', 0) + 1
    g['frame'] = f
    if f == 30:
        range.logic.getCurrentScene().convertObject('Pesado')
    if f == 60:
        range.logic.endGame()
''')
bpy.ops.logic.sensor_add(type='ALWAYS', name='t', object=ctl.name)
bpy.ops.logic.controller_add(type='PYTHON', name='c', object=ctl.name)
s = ctl.game.sensors['t']
s.use_pulse_true_level = True
c = ctl.game.controllers['c']
c.mode = 'MODULE'
c.module = 'controle.tick'
s.link(c)
bpy.ops.wm.save_as_mainfile(filepath=out, check_existing=False)
