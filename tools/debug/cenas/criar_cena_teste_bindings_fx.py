# Cena de teste dos bindings Python de particulas GPU, Explosive e clima (World.setWeather/getWeather).
# Uso: AnastacioEngine.exe -b --factory-startup --python criar_cena_teste_bindings_fx.py -- <saida.range>
# No jogo: BINDINGS_LOG=<arquivo> grava uma linha OK/FALHA por atributo e fecha.
import bpy
import bmesh
import sys

saida = sys.argv[sys.argv.index('--') + 1]

SCRIPT = '''
import bge, os

PARTICULAS = {
    'blendMode': 'ADDITIVE', 'billboardMode': 'VERTICAL', 'emissionMode': 'BURST',
    'useBackfaceCulling': True, 'useDebugUi': False, 'useVortex': True,
    'vortexHeight': 3.5, 'vortexRadiusTop': 2.5, 'vortexRotationSpeed': 1.5,
}
EXPLOSAO = {
    'explosionRadius': 7.0, 'explosionForce': 12.0, 'upBias': 0.5, 'useOcclusion': False,
    'effectLife': 2.0, 'useParticleExplosion': True, 'particleSize': 'HUGE', 'particleStyle': 'ELECTRIC',
    'fireColor': (0.25, 0.5, 0.75), 'smokeColor': (0.5, 0.25, 0.75), 'sparkColor': (0.75, 0.5, 0.25),
    'fireAmount': 2.0, 'smokeAmount': 0.5, 'sparkAmount': 3.0, 'smokeDuration': 2.0, 'blastSpeed': 1.5,
    'useGroundMark': True, 'useMarkNearby': True, 'markSize': 2.0, 'markLife': 12.0,
}
CLIMA = {
    'use_sky_layers': True, 'use_volumetric_clouds': True, 'vcloud_shadow_enable': True,
    'vfog_use_lamps': True, 'vfog_use_shafts': True, 'vfog_use_sun_shafts': False, 'vfog_volumes_only': True,
    'vfog_use_wind': True, 'vfog_use_time_of_day': True, 'vfog_use_layer': True, 'vfog_use_reach_clouds': True,
    'cloud_detail': 3, 'vcloud_quality': 2, 'vfog_quality': 1, 'vfog_max_lights': 6,
    'cloud_color_r': 0.25, 'cloud_color_g': 0.5, 'cloud_color_b': 0.75,
    'vcloud_coverage': 0.25, 'vcloud_scale': 2.0, 'vcloud_speed': 0.5, 'vcloud_altitude': 250.0,
    'vcloud_thickness': 75.0, 'vcloud_density': 0.5, 'vcloud_detail_scale': 2.0,
    'vcloud_silver_intensity': 0.5, 'vcloud_shadow_strength': 0.25,
    'vcloud_color_r': 0.75, 'vcloud_color_g': 0.5, 'vcloud_color_b': 0.25,
    'vfog_anisotropy': 0.5, 'vfog_edge': 0.25, 'vfog_noise_scale': 0.125, 'vfog_shaft_intensity': 2.0,
    'vfog_morning_boost': 3.0, 'vfog_wind_direction': 45.0,
}


def igual(a, b):
    if isinstance(b, tuple):
        return all(abs(x - y) < 1e-4 for x, y in zip(a, b))
    if isinstance(b, float):
        return abs(a - b) < 1e-4
    return a == b


def tick(cont):
    arquivo = os.environ.get('BINDINGS_LOG')
    if not arquivo:
        return
    scene = bge.logic.getCurrentScene()
    linhas = []

    def conferir(grupo, nome, ler, escrever, valor):
        try:
            escrever(valor)
            lido = ler()
            linhas.append('%s %s.%s = %r -> %r' % ('OK' if igual(lido, valor) else 'FALHA', grupo, nome, valor, lido))
        except Exception as e:
            linhas.append('FALHA %s.%s: %r' % (grupo, nome, e))

    ps = scene.objects['emissor'].particles
    for nome, valor in PARTICULAS.items():
        conferir('particles', nome, lambda n=nome: getattr(ps, n), lambda v, n=nome: setattr(ps, n, v), valor)
    linhas.append('%s particles.burstMode segue emissionMode' % ('OK' if ps.burstMode else 'FALHA'))
    try:
        ps.blendMode = 'NADA'
        linhas.append('FALHA particles.blendMode aceitou valor invalido')
    except ValueError:
        linhas.append('OK particles.blendMode invalido -> ValueError')

    bomba = scene.objects['bomba']
    for nome, valor in EXPLOSAO.items():
        conferir('bomba', nome, lambda n=nome: getattr(bomba, n), lambda v, n=nome: setattr(bomba, n, v), valor)
    marca = scene.objectsInactive['marca']
    conferir('bomba', 'groundMark', lambda: bomba.groundMark, lambda v: setattr(bomba, 'groundMark', v), marca)
    conferir('bomba', 'explosionEffect', lambda: bomba.explosionEffect,
             lambda v: setattr(bomba, 'explosionEffect', v), marca)
    conferir('bomba', 'explosionEffect', lambda: bomba.explosionEffect,
             lambda v: setattr(bomba, 'explosionEffect', v), None)
    try:
        scene.objects['chao'].explosionRadius = 1.0
        linhas.append('FALHA chao.explosionRadius aceitou objeto nao explosivo')
    except AttributeError:
        linhas.append('OK chao.explosionRadius -> AttributeError')

    world = scene.world
    for nome, valor in CLIMA.items():
        conferir('weather', nome, lambda n=nome: world.getWeather(n), lambda v, n=nome: world.setWeather(n, v), valor)

    with open(arquivo, 'w') as f:
        f.write('\\n'.join(linhas) + '\\n')
    bge.logic.endGame()
'''

scene = bpy.context.scene
for ob in list(scene.objects):
    scene.objects.unlink(ob)
scene.render.engine = 'BLENDER_GAME'
scene.world = scene.world or bpy.data.worlds.new('World')


def malha(nome, fazer, pos):
    me = bpy.data.meshes.new(nome)
    bm = bmesh.new()
    fazer(bm)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(nome, me)
    ob.location = pos
    scene.objects.link(ob)
    return ob


malha('chao', lambda bm: bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=20.0), (0, 0, 0))

emissor = malha('emissor', lambda bm: bmesh.ops.create_cube(bm, size=0.5), (-3, 0, 1))
emissor.use_gpu_particles = True

bomba = malha('bomba', lambda bm: bmesh.ops.create_cube(bm, size=0.8), (3, 0, 0.4))
bomba.game.use_explosive = True
bomba.game.explosive.fuse = 0.0
bomba.game.explosive.use_explode_on_impact = False

marca = malha('marca', lambda bm: bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=0.5), (0, 0, 0))
marca.data.materials.append(bpy.data.materials.new('marca'))
marca.layers = [i == 19 for i in range(20)]

cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
cam.location = (0, -12, 4)
cam.rotation_euler = (1.3, 0, 0)
scene.objects.link(cam)
scene.camera = cam

txt = bpy.data.texts.new('bindings_teste.py')
txt.write(SCRIPT)
scene.objects.active = cam
bpy.ops.logic.sensor_add(type='ALWAYS', name='sempre', object=cam.name)
bpy.ops.logic.controller_add(type='PYTHON', name='py', object=cam.name)
ctrl = cam.game.controllers['py']
ctrl.mode = 'MODULE'
ctrl.module = 'bindings_teste.tick'
cam.game.sensors['sempre'].link(ctrl)

bpy.ops.wm.save_as_mainfile(filepath=saida)
print('BINDINGS_SALVO', saida)
