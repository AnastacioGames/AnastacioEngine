"""FSR: cena PARADA para comparar upscalers sob resolucao dinamica com escala FIXA.

AnastacioEngine.exe -b --factory-startup --python criar_cena_fsr.py -- [saida.range]
  (padrao: artifacts/fsr/fsr_test.range)

No jogo (script fsr_test.py, objeto camera):
  FSR_SCALE   escala fixa 0.25..1.0 (padrao 1.0) -> bge.render.setDynamicResolution(True, 60, s*100, s*100)
  FSR_SHOT    caminho .png: captura no quadro 60
  FSR_RESULT  arquivo texto com o tempo medio de quadro 60-300 (opcional)
  FSR_FRAMES  ultimo quadro (padrao 300); o jogo fecha nele
Na geracao, FSR_BAKE_SCALE, FSR_BAKE_SHOT e FSR_BAKE_FRAMES mudam esses padroes (Web, sem variaveis de ambiente).
Nada se move durante a medicao.
"""
import bpy
import math
import os
import sys
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
out = args[0] if args else os.path.join(ROOT, 'artifacts', 'fsr', 'fsr_test.range')

scene = bpy.context.scene
for obj in list(scene.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
scene.render.engine = 'BLENDER_GAME'
scene.render.resolution_x = 1280
scene.render.resolution_y = 720
scene.render.resolution_percentage = 100
scene.world.mist_settings.use_mist = False
scene.world.horizon_color = (0.45, 0.55, 0.7)
scene.game_settings.vsync = 'OFF'
scene.game_settings.use_frame_rate = False


def material(name, rgb):
    m = bpy.data.materials.new(name)
    m.diffuse_color = rgb
    m.specular_intensity = 0.1
    return m


def finish(obj, mat):
    obj.data.materials.append(mat)
    obj.game.physics_type = 'NO_COLLISION'
    return obj


# Xadrez preto/branco recuando: quadrados de 1 m, 24 x 120 m, dois materiais por face.
white = material('white', (0.95, 0.95, 0.95))
black = material('black', (0.02, 0.02, 0.02))
verts, faces, mats = [], [], []
W, D = 24, 120
for y in range(D):
    for x in range(W):
        i = len(verts)
        x0 = x - W / 2
        verts += [(x0, y, 0), (x0 + 1, y, 0), (x0 + 1, y + 1, 0), (x0, y + 1, 0)]
        faces.append((i, i + 1, i + 2, i + 3))
        mats.append((x + y) % 2)
me = bpy.data.meshes.new('checker')
me.from_pydata(verts, [], faces)
me.update()
floor = bpy.data.objects.new('checker', me)
scene.objects.link(floor)
finish(floor, white)
me.materials.append(black)
for poly, mi in zip(me.polygons, mats):
    poly.material_index = mi

# Postes finos e fios (alta frequencia).
pole_mat = material('pole', (0.1, 0.1, 0.1))
wire_mat = material('wire', (0.9, 0.85, 0.2))
for k in range(12):
    for side in (-1, 1):
        bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.03, depth=6,
                                            location=(side * 6, 4 + k * 8, 3))
        p = finish(scene.objects.active, pole_mat)
        p.name = 'pole_%d_%d' % (k, side)
for side in (-1, 1):
    for h in (5.0, 5.4, 5.8):
        bpy.ops.mesh.primitive_cube_add(radius=1, location=(side * 6, 48, h))
        w = finish(scene.objects.active, wire_mat)
        w.name = 'wire_%d_%d' % (side, int(h * 10))
        w.scale = (0.008, 44, 0.008)

# Cubos coloridos de borda dura.
colors = [(1, 0, 0), (0, 0.8, 0), (0, 0.2, 1), (1, 0.6, 0), (0.8, 0, 0.8), (0, 0.9, 0.9)]
for i, c in enumerate(colors):
    bpy.ops.mesh.primitive_cube_add(radius=0.6, location=(-4.5 + i * 1.8, 6 + i * 3, 0.6))
    cube = finish(scene.objects.active, material('cube_%d' % i, c))
    cube.name = 'cube_%d' % i
    cube.rotation_euler = (0, 0, math.radians(20 * i))

# Textos 3D em varios tamanhos, de frente para a camera.
text_mat = material('text', (1, 1, 1))
for i, size in enumerate((1.2, 0.6, 0.3, 0.15, 0.08)):
    bpy.ops.object.text_add(location=(-3.5, 3 + i * 0.6, 0.9 + i * 0.55))
    t = scene.objects.active
    t.name = 'text_%d' % i
    t.data.body = 'Range FSR 0123 %.2f' % size
    t.data.size = size
    t.rotation_euler = (math.radians(80), 0, 0)
    t.data.materials.append(text_mat if i % 2 == 0 else black)

# Sol inclinado.
lamp = bpy.data.lamps.new('sun', 'SUN')
lamp.use_shadow = True
lamp_obj = bpy.data.objects.new('sun', lamp)
lamp_obj.rotation_euler = (math.radians(50), math.radians(-30), math.radians(20))
scene.objects.link(lamp_obj)

# Camera fixa.
cam = bpy.data.objects.new('camera', bpy.data.cameras.new('camera'))
cam.location = (0, -3, 2.2)
cam.data.lens = 24
cam.data.clip_end = 300
cam.rotation_euler = (Vector((0, 30, 0.5)) - Vector(cam.location)).to_track_quat('-Z', 'Y').to_euler()
scene.objects.link(cam)
scene.camera = cam

GAME_SCRIPT = r'''import bge, os, time
frame = 0
t_prev = None
times = []
SCALE = float(os.environ.get('FSR_SCALE', '1.0'))
SHOT = os.environ.get('FSR_SHOT', '')
RESULT = os.environ.get('FSR_RESULT', '')
LAST = int(os.environ.get('FSR_FRAMES', '300'))

def tick(cont):
    global frame, t_prev
    frame += 1
    now = time.perf_counter()
    if frame == 1:
        # min == max: escala fixa, em porcento (ver KX_KetsjiEngine::SetDynamicResolution).
        pct = int(round(max(0.25, min(SCALE, 1.0)) * 100))
        bge.render.setDynamicResolution(True, 60, pct, pct)
    if frame > 60 and t_prev is not None:
        times.append(now - t_prev)
    t_prev = now
    if frame == 60 and SHOT:
        bge.render.makeScreenshot(SHOT)
    if frame == LAST:
        avg = 1000.0 * sum(times) / max(1, len(times))
        line = 'scale=%.2f renderScale=%.3f frames=%d avg_tick_ms=%.3f tick_fps=%.1f engine_fps=%.1f' % (
            SCALE, bge.render.getRenderScale(), len(times), avg, 1000.0 / avg if avg else 0.0, bge.logic.getAverageFrameRate())
        print('FSR ' + line)
        if RESULT:
            with open(RESULT, 'w') as f:
                f.write(line + '\n')
        bge.logic.endGame()
'''
# Web has no environment: FSR_BAKE_SCALE / FSR_BAKE_FRAMES at generation become the script defaults.
GAME_SCRIPT = GAME_SCRIPT.replace("'FSR_SCALE', '1.0'", "'FSR_SCALE', '%s'" % os.environ.get('FSR_BAKE_SCALE', '1.0'))
GAME_SCRIPT = GAME_SCRIPT.replace("'FSR_SHOT', ''", "'FSR_SHOT', '%s'" % os.environ.get('FSR_BAKE_SHOT', ''))
GAME_SCRIPT = GAME_SCRIPT.replace("'FSR_FRAMES', '300'", "'FSR_FRAMES', '%s'" % os.environ.get('FSR_BAKE_FRAMES', '300'))
text = bpy.data.texts.new('fsr_test.py')
text.write(GAME_SCRIPT)
scene.objects.active = cam
bpy.ops.logic.sensor_add(type='ALWAYS', name='tick', object=cam.name)
bpy.ops.logic.controller_add(type='PYTHON', name='test', object=cam.name)
cam.game.sensors['tick'].use_pulse_true_level = True
controller = cam.game.controllers['test']
controller.mode = 'MODULE'
controller.module = 'fsr_test.tick'
cam.game.sensors['tick'].link(controller)
os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=out, check_existing=False)
