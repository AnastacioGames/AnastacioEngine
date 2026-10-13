# Cena headless para checar se sobra estado (listas do KX_Scene, timers da fisica) entre reinicios de cena.
# Hipotese de Kitsuy (Discord, 2026-10-12): listas nao limpas no KX_Scene e timers do Bullet deixam a cena pior a cada startup.
# 'Perto': 8 cubos rigid body caindo, dentro do raio de activity culling.
# 'Longe': 8 cubos rigid body caindo a 80 m da camera; com culling de fisica, nao devem cair.
# Cada rodada roda 90 frames, grava altura dos cubos, tempo de frame e estado, e chama scene.restart().
# Se nao sobra estado, todas as rodadas saem iguais.
#   AnastacioEngine.exe -b --factory-startup --python criar_cena_restart_estado.py -- saida.range
#   $env:RESTART_RESULT = 'resultado.json'; AnastacioRuntime.exe saida.range
import bpy
import sys

out = sys.argv[sys.argv.index('--') + 1]
scene = bpy.context.scene
for ob in list(scene.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.use_activity_culling = True

bpy.ops.object.camera_add(location=(0, -20, 5))
cam = scene.objects.active
cam.data.use_object_activity_culling = True
scene.camera = cam

bpy.ops.mesh.primitive_plane_add(radius=200, location=(0, 0, 0))
scene.objects.active.game.physics_type = 'STATIC'


def cubo(nome, loc):
    bpy.ops.mesh.primitive_cube_add(radius=0.5, location=loc)
    ob = scene.objects.active
    ob.name = nome
    ob.game.physics_type = 'RIGID_BODY'
    ob.game.activity_culling.use_physics = True
    ob.game.activity_culling.physics_radius = 30.0
    return ob


for i in range(8):
    cubo('Perto%d' % i, (i * 1.5 - 5, 0, 4 + i * 0.7))
    cubo('Longe%d' % i, (i * 1.5 - 5, 60, 4 + i * 0.7))

bpy.ops.mesh.primitive_cube_add(radius=0.2, location=(0, -25, 1))
probe_ob = scene.objects.active
probe_ob.name = 'Probe'
probe_ob.game.physics_type = 'NO_COLLISION'

probe = bpy.data.texts.new('probe.py')
probe.write('''import bge, json, os, time
RODADAS = 6
def tick(cont):
    g = bge.logic.globalDict
    sc = bge.logic.getCurrentScene()
    r = g.setdefault('rodadas', [])
    atual = g.get('atual')
    if atual is None or atual.get('scene_id') != id(sc):
        atual = {'scene_id': id(sc), 'frame': 0, 'dt': [], 't': time.perf_counter()}
        g['atual'] = atual
    atual['frame'] += 1
    agora = time.perf_counter()
    atual['dt'].append(agora - atual['t'])
    atual['t'] = agora
    if atual['frame'] < 90:
        return
    obs = sc.objects
    perto = [round(obs['Perto%d' % i].worldPosition.z, 4) for i in range(8)]
    longe = [round(obs['Longe%d' % i].worldPosition.z, 4) for i in range(8)]
    dt = sorted(atual['dt'][10:])
    r.append({'perto_z': perto, 'longe_z': longe,
              'objetos': len(obs),
              'dt_med_ms': round(1000 * dt[len(dt) // 2], 3),
              'dt_max_ms': round(1000 * dt[-1], 3)})
    if len(r) >= RODADAS:
        with open(os.environ['RESTART_RESULT'], 'w') as d:
            json.dump(r, d, indent=1)
        bge.logic.endGame()
    else:
        g['atual'] = None
        sc.restart()
''')
scene.objects.active = probe_ob
bpy.ops.logic.sensor_add(type='ALWAYS', name='t', object='Probe')
bpy.ops.logic.controller_add(type='PYTHON', name='c', object='Probe')
s = probe_ob.game.sensors['t']
s.use_pulse_true_level = True
c = probe_ob.game.controllers['c']
c.mode = 'MODULE'
c.module = 'probe.tick'
s.link(c)
bpy.ops.wm.save_as_mainfile(filepath=out, check_existing=False)
