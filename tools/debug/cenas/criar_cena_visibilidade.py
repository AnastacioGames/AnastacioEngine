"""V0 do plano de visibilidade (docs/plano-visibilidade-portais.md): predio de salas para medir o ganho de PVS.

  AnastacioEngine.exe -b --factory-startup --python tools/debug/cenas/criar_cena_visibilidade.py -- saida.range [occluder|auto] [nobatch] [open] [aceite] [lado]

Grade lado x lado de salas 8x8 m (padrao 6x6) ligadas em serpentina: portas no eixo X em todas as salas e
porta no eixo Y so na ponta da fileira. A camera fica na sala (0,0) olhando +X pelo corredor de portas:
so a fileira 0 e a sala (lado-1, 1) aparecem. Cada sala tem moveis com malha propria (~1,3k tri cada).
Com "aceite": cena para olhar com janela (Automatic Occluders ligado, contador de FPS, personagem invisivel com
a camera: W/A/S/D anda, setas giram); sem o script de medicao.
Com "occluder": paredes viram Occluder e o Occlusion Culling da cena liga.

No jogo (script vis_test.py na camera), variaveis de ambiente:
  VIS_MODE    all (padrao) | oracle (esconde as salas que a camera nao ve: teto de ganho do PVS)
  VIS_RESULT  arquivo texto com medias dos quadros 100..VIS_FRAMES
  VIS_SHOT    .png capturado no quadro 100
  VIS_FRAMES  ultimo quadro (padrao 500); o jogo fecha nele
"""
import math
import random
import sys

import bpy

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
if not argv:
    raise SystemExit('uso: ... -- saida.range [occluder] [lado]')
out = argv[0]
use_occluder = 'occluder' in argv[1:]
aceite = 'aceite' in argv[1:]
open_area = 'open' in argv[1:]  # sem paredes nem teto: a oclusao nao tem o que esconder
SIDE = next((int(a) for a in argv[1:] if a.isdigit()), 6)
ROOM = 8.0
HEIGHT = 3.0
THICK = 0.2
DOOR = 1.6
FURNITURE = 30

random.seed(7)
scene = bpy.context.scene
for ob in list(scene.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
scene.render.engine = 'BLENDER_GAME'
scene.render.resolution_x = 1280
scene.render.resolution_y = 720
scene.game_settings.vsync = 'OFF'
scene.game_settings.use_frame_rate = False
# use_frame_rate=False nao solta o FPS no runtime atual (a espera segue a taxa de logica): logica alta
scene.game_settings.fps = 1000
scene.game_settings.use_auto_static_batch = 'nobatch' not in argv[1:]
scene.game_settings.physics_engine = 'BULLET'
scene.game_settings.use_occlusion_culling = True
# auto: paredes STATIC (com colisao) viram occluder sozinhas no load (Automatic Occluders)
scene.game_settings.use_auto_occlusion = 'auto' in argv[1:] or aceite
scene.game_settings.show_fps_counter = aceite
scene.world.horizon_color = (0.3, 0.3, 0.35)
scene.world.mist_settings.use_mist = False

materials = []
for i in range(12):
    m = bpy.data.materials.new('Mat%02d' % i)
    m.diffuse_color = (random.uniform(0.2, 0.9), random.uniform(0.2, 0.9), random.uniform(0.2, 0.9))
    materials.append(m)
wall_mat = bpy.data.materials.new('Parede')
wall_mat.diffuse_color = (0.8, 0.78, 0.72)


def box(name, center, size, mat, room, physics='STATIC'):
    bpy.ops.mesh.primitive_cube_add(location=center)
    ob = scene.objects.active
    ob.name = name
    ob.scale = (size[0] / 2.0, size[1] / 2.0, size[2] / 2.0)
    bpy.ops.object.transform_apply(scale=True)
    ob.data.materials.append(mat)
    ob.game.physics_type = physics
    ob['vis_room'] = room
    return ob


def wall_x(name, x0, x1, y, door, room):
    """Parede ao longo de X em y, de x0 a x1, com porta no meio se door."""
    if open_area:
        return
    phys = 'OCCLUDER' if use_occluder else 'STATIC'
    if not door:
        box(name, ((x0 + x1) / 2, y, HEIGHT / 2), (x1 - x0, THICK, HEIGHT), wall_mat, room, phys)
        return
    mid = (x0 + x1) / 2
    a, b = mid - DOOR / 2, mid + DOOR / 2
    box(name + 'a', ((x0 + a) / 2, y, HEIGHT / 2), (a - x0, THICK, HEIGHT), wall_mat, room, phys)
    box(name + 'b', ((b + x1) / 2, y, HEIGHT / 2), (x1 - b, THICK, HEIGHT), wall_mat, room, phys)
    box(name + 'c', (mid, y, HEIGHT - 0.4), (DOOR, THICK, 0.8), wall_mat, room, phys)


def wall_y(name, y0, y1, x, door, room):
    if open_area:
        return
    phys = 'OCCLUDER' if use_occluder else 'STATIC'
    if not door:
        box(name, (x, (y0 + y1) / 2, HEIGHT / 2), (THICK, y1 - y0, HEIGHT), wall_mat, room, phys)
        return
    mid = (y0 + y1) / 2
    a, b = mid - DOOR / 2, mid + DOOR / 2
    box(name + 'a', (x, (y0 + a) / 2, HEIGHT / 2), (THICK, a - y0, HEIGHT), wall_mat, room, phys)
    box(name + 'b', (x, (b + y1) / 2, HEIGHT / 2), (THICK, y1 - b, HEIGHT), wall_mat, room, phys)
    box(name + 'c', (x, mid, HEIGHT - 0.4), (THICK, DOOR, 0.8), wall_mat, room, phys)


# Movel base: icosfera subdividida (malha copiada por objeto: sem instancia compartilhada).
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, size=0.5)
proto = scene.objects.active
proto_mesh = proto.data
bpy.data.objects.remove(proto, do_unlink=True)

for gy in range(SIDE):
    for gx in range(SIDE):
        room = '%d_%d' % (gx, gy)
        x0, y0 = gx * ROOM, gy * ROOM
        box('Piso_' + room, (x0 + ROOM / 2, y0 + ROOM / 2, -0.1), (ROOM, ROOM, 0.2), wall_mat, room)
        if not open_area:
            box('Teto_' + room, (x0 + ROOM / 2, y0 + ROOM / 2, HEIGHT + 0.1), (ROOM, ROOM, 0.2), wall_mat, room)
        # parede oeste (X = x0): porta se nao for a primeira coluna
        wall_y('ParedeO_' + room, y0, y0 + ROOM, x0, gx > 0, room)
        if gx == SIDE - 1:
            wall_y('ParedeL_' + room, y0, y0 + ROOM, x0 + ROOM, False, room)
        # parede sul (Y = y0): porta so na ponta da serpentina
        end = SIDE - 1 if (gy - 1) % 2 == 0 else 0
        wall_x('ParedeS_' + room, x0, x0 + ROOM, y0, gy > 0 and gx == end, room)
        if gy == SIDE - 1:
            wall_x('ParedeN_' + room, x0, x0 + ROOM, y0 + ROOM, False, room)
        for i in range(FURNITURE):
            ob = bpy.data.objects.new('Movel_%s_%02d' % (room, i), proto_mesh.copy())
            scene.objects.link(ob)
            # longe do eixo das portas (y = meio da sala) para nao tapar o corredor
            side = random.choice((-1, 1))
            ob.location = (x0 + random.uniform(0.8, ROOM - 0.8),
                           y0 + ROOM / 2 + side * random.uniform(1.6, ROOM / 2 - 0.8),
                           random.uniform(0.5, 2.2))
            s = random.uniform(0.6, 1.4)
            ob.scale = (s, s, s)
            ob.data.materials.append(materials[(gx * 7 + gy * 3 + i) % len(materials)])
            ob.game.physics_type = 'NO_COLLISION'
            ob['vis_room'] = room

lamp = bpy.data.lamps.new('Sol', 'SUN')
lamp_ob = bpy.data.objects.new('Sol', lamp)
lamp_ob.rotation_euler = (0.6, 0.2, 0.8)
scene.objects.link(lamp_ob)

cam_data = bpy.data.cameras.new('Camera')
cam_data.lens = 24.0
cam = bpy.data.objects.new('Camera', cam_data)
cam.location = (1.0, ROOM / 2, 1.6)
cam.rotation_euler = (math.pi / 2, 0.0, -math.pi / 2)  # olha +X
scene.objects.link(cam)
scene.camera = cam

GAME_SCRIPT = '''import bge, os, re, time
SIDE = %d
frame = 0
t_prev = None
acc = {}
n = 0
MODE = os.environ.get('VIS_MODE', 'all')
RESULT = os.environ.get('VIS_RESULT', '')
SHOT = os.environ.get('VIS_SHOT', '')
LAST = int(os.environ.get('VIS_FRAMES', '4000'))
VISIBLE = {'%%d_0' %% x for x in range(SIDE)} | {'%%d_1' %% (SIDE - 1)}

def tick(cont):
    global frame, t_prev, n
    frame += 1
    now = time.perf_counter()
    if frame == 1:
        hidden = 0
        if MODE == 'oracle':
            for ob in bge.logic.getCurrentScene().objects:
                m = re.search(r'_(\d+_\d+)', ob.name)  # Piso_3_2, ParedeO_3_2a, Movel_3_2_07
                if m and m.group(1) not in VISIBLE:
                    ob.visible = False
                    hidden += 1
        print('VIS mode=%%s hidden=%%d' %% (MODE, hidden))
    if frame > 300 and t_prev is not None:
        n += 1
        acc['tick_ms'] = acc.get('tick_ms', 0.0) + 1000.0 * (now - t_prev)
        for k, v in bge.logic.getRenderStats().items():
            acc[k] = acc.get(k, 0.0) + v
        for k, v in bge.logic.getProfileInfo().items():
            acc['p_' + k] = acc.get('p_' + k, 0.0) + v[0]
            if k != 'Sleeping':
                acc['work_ms'] = acc.get('work_ms', 0.0) + v[0]
    t_prev = now
    if frame == 300 and SHOT:
        bge.render.makeScreenshot(SHOT)
    if frame == LAST:
        line = 'mode=%%s frames=%%d ' %% (MODE, n) + ' '.join(
            '%%s=%%.3f' %% (k, v / max(1, n)) for k, v in sorted(acc.items()))
        print('VIS ' + line)
        if RESULT:
            with open(RESULT, 'w') as f:
                f.write(line + '\\n')
        bge.logic.endGame()
''' % SIDE
if aceite:
    bpy.ops.mesh.primitive_cube_add(location=(1.0, ROOM / 2, 1.0))
    player = scene.objects.active
    player.name = 'Jogador'
    player.scale = (0.3, 0.3, 0.9)
    bpy.ops.object.transform_apply(scale=True)
    player.game.physics_type = 'CHARACTER'
    player.game.use_collision_bounds = True
    player.game.collision_bounds_type = 'CAPSULE'
    player.hide_render = True
    cam.parent = player
    cam.location = (0.0, 0.0, 0.6)
    cam.rotation_euler = (math.pi / 2, 0.0, -math.pi / 2)
    text = bpy.data.texts.new('andar.py')
    text.write('''import bge
from bge import logic, events, constraints
def andar(cont):
    own = cont.owner
    k = logic.keyboard.inputs
    def on(key):
        return k[key].active
    frente = (on(events.WKEY) - on(events.SKEY)) * 0.08
    lado = (on(events.DKEY) - on(events.AKEY)) * 0.08
    giro = (on(events.LEFTARROWKEY) - on(events.RIGHTARROWKEY)) * 0.04
    own.applyRotation((0, 0, giro), True)
    # camera olha +X local do jogador
    d = own.worldOrientation * __import__('mathutils').Vector((frente, -lado, 0.0))
    constraints.getCharacter(own).walkDirection = d
''')
    scene.objects.active = player
    bpy.ops.logic.sensor_add(type='ALWAYS', name='tick', object=player.name)
    bpy.ops.logic.controller_add(type='PYTHON', name='andar', object=player.name)
    player.game.sensors['tick'].use_pulse_true_level = True
    ctl = player.game.controllers['andar']
    ctl.mode = 'MODULE'
    ctl.module = 'andar.andar'
    ctl.link(sensor=player.game.sensors['tick'])
    scene.game_settings.fps = 60
else:
    text = bpy.data.texts.new('vis_test.py')
    text.write(GAME_SCRIPT)
    scene.objects.active = cam
    bpy.ops.logic.sensor_add(type='ALWAYS', name='tick', object=cam.name)
    bpy.ops.logic.controller_add(type='PYTHON', name='test', object=cam.name)
    cam.game.sensors['tick'].use_pulse_true_level = True
    controller = cam.game.controllers['test']
    controller.mode = 'MODULE'
    controller.module = 'vis_test.tick'
    controller.link(sensor=cam.game.sensors['tick'])
print('VIS cena: %d salas, %d objetos, occluder=%s' % (SIDE * SIDE, len(scene.objects), use_occluder))
bpy.ops.wm.save_as_mainfile(filepath=out, compress=False)
