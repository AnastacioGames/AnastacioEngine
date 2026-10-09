"""Bindings Python da Prioridade 1 (D:/AnastacioDocs/inventario/faltando_python.md).

AnastacioEngine.exe -b --factory-startup --python criar_cena_api_prioridade1.py -- teste.range
API_P1_RESULT recebe o JSON: lista de [nome, ok, detalhe] e contagens.
- world: skyType, estrelas, lua, aurora e atmosfera (troca o shader do ceu durante o jogo);
- 'wall' destrutivel (fragments 'frags'), 'bomb' explosiva, 'plate' deformavel, 'plain' sem nada;
- scene.filterManager: FXAA e grao;
- Range.network.replicate(..., quantize=...).
"""
import bpy, sys
from mathutils import Vector

out = sys.argv[sys.argv.index('--') + 1]
scene = bpy.context.scene
for obj in list(scene.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
scene.render.engine = 'BLENDER_GAME'
scene.render.resolution_x = 640
scene.render.resolution_y = 360
scene.game_settings.use_frame_rate = False

world = scene.world or bpy.data.worlds.new('World')
scene.world = world
world.mist_settings.use_mist = False
world.sky_type = 'GRADIENT'


def material(name, color):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = color
    return mat


def cube(name, location, color, radius=1.0):
    bpy.ops.mesh.primitive_cube_add(radius=radius, location=location)
    obj = scene.objects.active
    obj.name = name
    obj.data.materials.append(material(name, color))
    return obj


bpy.ops.mesh.primitive_plane_add(radius=20, location=(0, 0, 0))
ground = scene.objects.active
ground.name = 'ground'
ground.data.materials.append(material('ground', (0.3, 0.3, 0.3)))

# Fragmento modelo numa camada inativa, no grupo 'frags'.
frag = cube('frag', (0, 0, 1), (0.9, 0.6, 0.1), radius=0.3)
frag.game.physics_type = 'RIGID_BODY'
frag.layers = [i == 1 for i in range(20)]
group = bpy.data.groups.new('frags')
group.objects.link(frag)

wall = cube('wall', (-4, 0, 1), (0.8, 0.2, 0.2))
wall.game.physics_type = 'RIGID_BODY'
wall.game.use_destruction = True
wall.game.destruction.fragments = group

bomb = cube('bomb', (0, 0, 1), (0.2, 0.2, 0.8))
bomb.game.physics_type = 'RIGID_BODY'
bomb.game.use_explosive = True
bomb.game.explosive.fuse = 0.0

plate = cube('plate', (4, 0, 1), (0.2, 0.8, 0.2))
plate.game.physics_type = 'RIGID_BODY'
plate.game.use_deform = True

plain = cube('plain', (0, 5, 1), (0.8, 0.8, 0.8))
plain.game.physics_type = 'RIGID_BODY'
scene.objects.active = plain
bpy.ops.object.game_property_new(type='FLOAT', name='speed')

sun = bpy.data.objects.new('sun', bpy.data.lamps.new('sun', 'SUN'))
sun.rotation_euler = (0.7, 0.2, 0.4)
scene.objects.link(sun)
cam = bpy.data.objects.new('camera', bpy.data.cameras.new('camera'))
cam.location = (0, -16, 6)
cam.data.lens = 16
cam.rotation_euler = (Vector((0, 0, 1)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
scene.objects.link(cam)
scene.camera = cam

text = bpy.data.texts.new('api_p1.py')
text.write('''import bge, json, os
frame = 0
log = dict(checks=[], objects={})

def check(name, fn, expect=None, error=None):
    try:
        value = fn()
        if error:
            log['checks'].append([name, False, 'sem erro: %r' % (value,)])
        elif expect is not None and value != expect and not (isinstance(expect, float) and abs(value - expect) < 1e-4):
            log['checks'].append([name, False, 'valor %r, esperado %r' % (value, expect)])
        else:
            log['checks'].append([name, True, repr(value)])
    except Exception as exc:
        ok = error is not None and isinstance(exc, error)
        log['checks'].append([name, ok, '%s: %s' % (type(exc).__name__, exc)])

def setget(obj, attr, value, expect=None):
    def run():
        setattr(obj, attr, value)
        return getattr(obj, attr)
    check('%s=%r' % (attr, value), run, value if expect is None else expect)

def tick(cont):
    global frame
    frame += 1
    sc = bge.logic.getCurrentScene()
    w = sc.world
    if frame == 2:
        check('skyType inicial', lambda: w.skyType, 'GRADIENT')
        for attr in ('starStyle', 'useSkyStars', 'useSkyMoon', 'moonSize', 'moonBrightness', 'useSkyAurora',
                     'auroraColors', 'atmosphereIntensity', 'atmosphereRayleighDensity', 'atmosphereMieDensity',
                     'atmosphereMieDirection', 'atmosphereAltitude'):
            check('ler ' + attr, lambda a=attr: getattr(w, a))
        check('ler atmosphereRayleighColor', lambda: list(w.atmosphereRayleighColor))
        setget(w, 'skyType', 'ATMOSPHERIC')
        setget(w, 'starStyle', 'REALISTIC')
        setget(w, 'useSkyStars', True)
        setget(w, 'useSkyMoon', True)
        setget(w, 'moonSize', 0.05)
        setget(w, 'moonSize', 5.0, 0.1)
        setget(w, 'moonBrightness', 0.7)
        setget(w, 'useSkyAurora', True)
        setget(w, 'auroraColors', 'SHIFTING')
        setget(w, 'atmosphereIntensity', 20.0)
        setget(w, 'atmosphereRayleighDensity', 1.5)
        setget(w, 'atmosphereMieDensity', 2.0)
        setget(w, 'atmosphereMieDirection', 0.8)
        setget(w, 'atmosphereAltitude', 5000.0)
        check('atmosphereRayleighColor', lambda: (setattr(w, 'atmosphereRayleighColor', [0.2, 0.4, 1.0]),
              [round(c, 3) for c in w.atmosphereRayleighColor])[1], [0.2, 0.4, 1.0])
        check('skyType invalido', lambda: setattr(w, 'skyType', 'NADA'), error=ValueError)

        wall, bomb, plate, plain = (sc.objects[n] for n in ('wall', 'bomb', 'plate', 'plain'))
        check('fragments', lambda: wall.fragments, 'frags')
        setget(wall, 'fragments', None)
        setget(wall, 'fragments', 'frags')
        check('fragments invalido', lambda: setattr(wall, 'fragments', 'nao_existe'), error=ValueError)
        setget(wall, 'burstSpeed', 7.0)
        setget(wall, 'debrisLifetime', 3.0)
        setget(wall, 'useBreakOnCollision', False)
        setget(wall, 'useInheritVelocity', True)
        setget(bomb, 'impactImpulse', 50.0)
        setget(bomb, 'useExplodeOnImpact', True)
        setget(bomb, 'useChainReaction', True)
        setget(plate, 'dentImpulse', 3.0)
        setget(plate, 'useDentOnCollision', False)
        setget(plate, 'bendAxis', 'Y')
        setget(plate, 'bendAngle', 0.3)
        setget(plate, 'bendMaxAngle', 1.0)
        setget(plate, 'decal', None)
        setget(plate, 'decalSize', 0.4)
        setget(plate, 'decalLife', 9.0)
        setget(plate, 'maxDecals', 5000, 1000)
        check('isDeformable plate', lambda: plate.isDeformable, True)
        check('isDeformable plain', lambda: plain.isDeformable, False)
        check('plain.burstSpeed= erro', lambda: setattr(plain, 'burstSpeed', 1.0), error=AttributeError)
        check('wall.dentImpulse= erro', lambda: setattr(wall, 'dentImpulse', 1.0), error=AttributeError)
        check('bendAxis invalido', lambda: setattr(plate, 'bendAxis', 'W'), error=ValueError)

        fm = sc.filterManager
        for attr in ('fxaaEnabled', 'fxaaEdgeThreshold', 'fxaaEdgeThresholdMin', 'fxaaSubpix', 'fxaaSearchSteps',
                     'grainEnabled', 'grainStrength'):
            check('ler ' + attr, lambda a=attr: getattr(fm, a))
        setget(fm, 'fxaaSubpix', 0.5)
        setget(fm, 'fxaaEnabled', True)
        setget(fm, 'fxaaEdgeThreshold', 0.2)
        setget(fm, 'fxaaEdgeThresholdMin', 0.05)
        setget(fm, 'fxaaSearchSteps', 100, 32)
        setget(fm, 'grainEnabled', True)
        setget(fm, 'grainStrength', 0.1)

        import Range.network as net
        check('replicate quantize', lambda: net.replicate(plain, props=['speed'], quantize={'speed': (0.0, 10.0, 8)}) > 0, True)
        check('quantize invalido', lambda: net.replicate(wall, props=[], quantize={'x': (1.0, 0.0, 8)}), error=ValueError)
    if frame == 20:
        log['objects']['antes'] = len(sc.objects)
        check('shatter com fragments trocado', lambda: len(sc.objects['wall'].shatter()) > 0, True)
    if frame == 22:
        log['objects']['depois'] = len(sc.objects)
    if frame == 60:
        check('skyType final', lambda: w.skyType, 'ATMOSPHERIC')
        with open(os.environ['API_P1_RESULT'], 'w') as d:
            json.dump(log, d, indent=1)
        bge.logic.endGame()
''')
scene.objects.active = cam
bpy.ops.logic.sensor_add(type='ALWAYS', name='t', object=cam.name)
bpy.ops.logic.controller_add(type='PYTHON', name='c', object=cam.name)
s = cam.game.sensors['t']
s.use_pulse_true_level = True
c = cam.game.controllers['c']
c.mode = 'MODULE'
c.module = 'api_p1.tick'
s.link(c)
bpy.ops.wm.save_as_mainfile(filepath=out, check_existing=False)
