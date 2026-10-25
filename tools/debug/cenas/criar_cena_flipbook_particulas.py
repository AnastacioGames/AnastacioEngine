# Cena de teste do flipbook de partículas GPU (plano-efeitos-render.md, Fase 3).
# Gera um atlas 4x4 (cada quadro com outra cor e um disco que encolhe) ao lado do .range e dois
# emissores: à esquerda o flipbook animado (1 ciclo por vida), à direita quadros parados e
# aleatórios (0 ciclos + Random Start).
# Uso: AnastacioEngine.exe -b --factory-startup --python criar_cena_flipbook_particulas.py -- <saida.range>
# No jogo: FLIPBOOK_LOG=<arquivo> grava particles.flipbook dos dois emissores, testa a escrita pelo
# Python e fecha após FLIPBOOK_T s (padrão 4); sem ela roda normal.
import bpy
import colorsys
import math
import os
import sys
from mathutils import Vector

saida = sys.argv[sys.argv.index('--') + 1]
pasta = os.path.dirname(os.path.abspath(saida))

# Atlas 4x4 de 64 px por quadro; o quadro 0 fica no canto de cima à esquerda.
COLS, ROWS, CEL = 4, 4, 64
W, H = COLS * CEL, ROWS * CEL
img = bpy.data.images.new('flipbook_atlas', W, H, alpha=True)
px = [0.0] * (W * H * 4)
for f in range(COLS * ROWS):
    cx, cy = f % COLS, ROWS - 1 - f // COLS
    r, g, b = colorsys.hsv_to_rgb(f / float(COLS * ROWS), 0.85, 1.0)
    raio = (0.45 - 0.022 * f) * CEL
    for y in range(CEL):
        for x in range(CEL):
            d = math.hypot(x + 0.5 - CEL / 2, y + 0.5 - CEL / 2)
            a = max(0.0, min(1.0, raio - d))
            i = ((cy * CEL + y) * W + cx * CEL + x) * 4
            px[i:i + 4] = [r, g, b, a]
img.pixels = px
atlas = os.path.join(pasta, 'flipbook_atlas.png')
img.filepath_raw = atlas
img.file_format = 'PNG'
img.save()

SCRIPT = (
    "import bge, os\n"
    "def tick(cont):\n"
    "    own = cont.owner\n"
    "    log = os.environ.get('FLIPBOOK_LOG')\n"
    "    if not log:\n"
    "        return\n"
    "    t = bge.logic.getRealTime()\n"
    "    if 'inicio' not in own:\n"
    "        own['inicio'] = t\n"
    "        sc = bge.logic.getCurrentScene()\n"
    "        with open(log, 'w') as f:\n"
    "            for nome in ('animado', 'aleatorio'):\n"
    "                ps = sc.objects[nome].particles\n"
    "                f.write('%s %r\\n' % (nome, tuple(ps.flipbook)))\n"
    "            ps = sc.objects['animado'].particles\n"
    "            ps.flipbook = (2, 2, 3.0, True)\n"
    "            f.write('escrito %r\\n' % (tuple(ps.flipbook),))\n"
    "            ps.flipbook = (4, 4, 1.0, False)\n"
    "    if t - own['inicio'] > float(os.environ.get('FLIPBOOK_T', '4')):\n"
    "        with open(log, 'a') as f:\n"
    "            f.write('fim ok\\n')\n"
    "        bge.logic.endGame()\n"
)

scene = bpy.context.scene
for ob in list(scene.objects):
    scene.objects.unlink(ob)
scene.render.engine = 'BLENDER_GAME'
scene.render.resolution_x = 1280
scene.render.resolution_y = 720
scene.game_settings.use_frame_rate = True

world = scene.world or bpy.data.worlds.new('World')
scene.world = world
world.horizon_color = (0.12, 0.13, 0.16)
world.zenith_color = (0.05, 0.06, 0.1)
world.mist_settings.use_mist = False

chao_me = bpy.data.meshes.new('chao')
chao_me.from_pydata([(-20, -20, 0), (20, -20, 0), (20, 20, 0), (-20, 20, 0)], [], [(0, 1, 2, 3)])
chao = bpy.data.objects.new('chao', chao_me)
scene.objects.link(chao)
chao_mat = bpy.data.materials.new('chao')
chao_mat.diffuse_color = (0.25, 0.25, 0.27)
chao_me.materials.append(chao_mat)

sol_data = bpy.data.lamps.new('sol', 'SUN')
sol = bpy.data.objects.new('sol', sol_data)
sol.location = (5, -5, 10)
sol.rotation_euler = (0.8, 0.2, 0.5)
scene.objects.link(sol)

cam_data = bpy.data.cameras.new('cam')
cam_data.lens = 24
cam = bpy.data.objects.new('cam', cam_data)
cam.location = (0, -14, 4)
cam.rotation_euler = (Vector((0, 0, 3)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
scene.objects.link(cam)
scene.camera = cam


def emissor(nome, x, ciclos, aleatorio):
    ob = bpy.data.objects.new(nome, None)
    ob.location = (x, 0, 0.5)
    scene.objects.link(ob)
    ob.use_gpu_particles = True
    gp = ob.gpu_particles
    gp.particle_count = 60
    gp.lifetime = 4.0
    gp.emitter_radius = 0.4
    gp.velocity = (0.0, 0.0, 1.5)
    gp.velocity_randomness = 0.3
    gp.emission_direction = (0, 0, 1)
    gp.emission_angle = 15
    gp.gravity = (0.0, 0.0, 0.0)
    gp.size = 1.0
    gp.end_size = 1.0
    gp.color = (1, 1, 1, 1)
    gp.end_color = (1, 1, 1, 1)
    gp.blend_mode = 'ALPHA'
    gp.texture = '//flipbook_atlas.png'
    gp.flipbook_columns = COLS
    gp.flipbook_rows = ROWS
    gp.flipbook_cycles = ciclos
    gp.use_flipbook_random = aleatorio
    return ob


emissor('animado', -3.5, 1.0, False)
emissor('aleatorio', 3.5, 0.0, True)

txt = bpy.data.texts.new('flipbook_teste.py')
txt.write(SCRIPT)
scene.objects.active = cam
bpy.ops.logic.sensor_add(type='ALWAYS', name='sempre', object=cam.name)
sens = cam.game.sensors['sempre']
sens.use_pulse_true_level = True
bpy.ops.logic.controller_add(type='PYTHON', name='py', object=cam.name)
ctrl = cam.game.controllers['py']
ctrl.mode = 'MODULE'
ctrl.module = 'flipbook_teste.tick'
sens.link(ctrl)

bpy.ops.wm.save_as_mainfile(filepath=saida)
print('salvo', saida)
