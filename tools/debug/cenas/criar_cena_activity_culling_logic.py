# Cena headless para checar o culling de logica depois de desligar o culling de fisica
# no mesmo objeto (KX_GameObject::SetActivityCulling, ramo enable=false).
# A: logica + fisica ligadas; a fisica e desligada em runtime (frame 5) e depois A e B vao para longe (frame 60).
# B: controle, mantem as duas flags. Depois de sair do raio, a logica de ambos deve parar de rodar.
# Resultado (env CULL_RESULT): contagem de ticks por objeto em frame 60, 100 e 180.
#   AnastacioEngine.exe -b --factory-startup --python criar_cena_activity_culling_logic.py -- saida.range
#   $env:CULL_RESULT = 'resultado.json'; AnastacioRuntime.exe saida.range
import bpy
import sys

out = sys.argv[sys.argv.index('--') + 1]
scene = bpy.context.scene
for ob in list(scene.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.use_activity_culling = True

bpy.ops.object.camera_add(location=(0, 0, 2))
cam = scene.objects.active
cam.data.use_object_activity_culling = True
scene.camera = cam


def cubo(nome, loc):
    bpy.ops.mesh.primitive_cube_add(radius=0.5, location=loc)
    ob = scene.objects.active
    ob.name = nome
    ob.game.physics_type = 'NO_COLLISION'
    return ob


def logica(ob, modulo):
    scene.objects.active = ob
    bpy.ops.logic.sensor_add(type='ALWAYS', name='t', object=ob.name)
    bpy.ops.logic.controller_add(type='PYTHON', name='c', object=ob.name)
    s = ob.game.sensors['t']
    s.use_pulse_true_level = True
    c = ob.game.controllers['c']
    c.mode = 'MODULE'
    c.module = modulo
    s.link(c)


A = cubo('A', (0, 0, 1))
B = cubo('B', (0, 3, 1))
Probe = cubo('Probe', (0, -3, 1))

for ob in (A, B):
    ob.game.activity_culling.use_logic = True
    ob.game.activity_culling.use_physics = True
    ob.game.activity_culling.logic_radius = 10.0
    ob.game.activity_culling.physics_radius = 10.0

counter = bpy.data.texts.new('counter.py')
counter.write('''import bge
def tick(cont):
    g = bge.logic.globalDict
    nome = cont.owner.name
    g[nome] = g.get(nome, 0) + 1
''')

probe = bpy.data.texts.new('probe.py')
probe.write('''import bge, json, os
def tick(cont):
    g = bge.logic.globalDict
    f = g.get('frame', 0) + 1
    g['frame'] = f
    obs = bge.logic.getCurrentScene().objects
    if f == 5:
        # Desliga so a fisica de A, ainda dentro do raio.
        obs['A'].physicsCulling = False
    if f == 60:
        obs['A'].worldPosition = [60, 0, 1]
        obs['B'].worldPosition = [60, 3, 1]
    if f in (60, 100, 180):
        g['snap%d' % f] = [g.get('A', 0), g.get('B', 0)]
    if f == 180:
        log = {
            'snap60': g['snap60'], 'snap100': g['snap100'], 'snap180': g['snap180'],
            'A_physicsCulling': obs['A'].physicsCulling, 'A_logicCulling': obs['A'].logicCulling,
            'B_physicsCulling': obs['B'].physicsCulling, 'B_logicCulling': obs['B'].logicCulling,
        }
        with open(os.environ['CULL_RESULT'], 'w') as d:
            json.dump(log, d, indent=1)
        bge.logic.endGame()
''')

logica(Probe, 'probe.tick')
logica(A, 'counter.tick')
logica(B, 'counter.tick')
bpy.ops.wm.save_as_mainfile(filepath=out, check_existing=False)
