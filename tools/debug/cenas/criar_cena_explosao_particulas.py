# Cena de teste: explosao com particulas GPU em modo Burst. Bola de fogo (look FIRE) no emissor
# principal e fumaca (look SMOKE) no Mix do mesmo Empty, estilhacos (SPARKLE) num segundo Empty.
# Os tres repetem a rajada a cada 3 s; um clarao na lampada acompanha cada rajada.
# Uso: AnastacioEngine.exe -b --factory-startup --python criar_cena_explosao_particulas.py -- <saida.range> [--explosivo]
# --explosivo: em vez de repetir, o efeito fica na camada 2 e e o Effect de uma caixa Explosive
# (painel de fisica) com pavio de 1.5 s -- testa o caminho real de jogo (Burst on Start).
# No jogo: FUMACA_SHOT=<pasta> grava capturas 0.1/0.3/0.7/1.5/2.8 s depois da 2a rajada e fecha.
import bpy
import bmesh
import sys
from math import radians
from mathutils import Vector

args = sys.argv[sys.argv.index('--') + 1:]
saida = args[0]
EXPLOSIVO = '--explosivo' in args
PAVIO = 1.5
# Com Explosive a rajada nasce uma vez no pavio; as fotos contam a partir dele.
INTERVALO = PAVIO if EXPLOSIVO else 3.0

SCRIPT = (
    "import bge, os\n"
    "INTERVALO = %r\n"
    "EXPLOSIVO = %r\n"
    "FOTOS = (0.1, 0.3, 0.7, 1.5, 2.8)\n"
    "def tick(cont):\n"
    "    own = cont.owner\n"
    "    t = bge.logic.getRealTime()\n"
    "    if 'inicio' not in own:\n"
    "        own['inicio'] = t\n"
    "    dt = t - own['inicio']\n"
    "    fase = (dt - INTERVALO) if EXPLOSIVO else dt %% INTERVALO\n"
    "    luz = own.scene.objects['clarao']\n"
    "    luz.energy = 12.0 * max(0.0, 1.0 - fase / 0.6) ** 2 if fase >= 0.0 else 0.0\n"
    "    pasta = os.environ.get('FUMACA_SHOT')\n"
    "    if not pasta:\n"
    "        return\n"
    "    feitas = own.get('feitas', 0)\n"
    "    if feitas < len(FOTOS) and dt > INTERVALO + FOTOS[feitas]:\n"
    "        own['feitas'] = feitas + 1\n"
    "        os.makedirs(pasta, exist_ok=True)\n"
    "        bge.render.makeScreenshot(os.path.join(pasta, 'explosao_%%d.png' %% feitas))\n"
    "    if dt > INTERVALO + FOTOS[-1] + 0.5:\n"
    "        bge.logic.endGame()\n"
) % (INTERVALO, EXPLOSIVO)

scene = bpy.context.scene
for ob in list(scene.objects):
    scene.objects.unlink(ob)
scene.render.engine = 'BLENDER_GAME'
scene.render.resolution_x = 1280
scene.render.resolution_y = 720
scene.game_settings.use_frame_rate = False

world = scene.world or bpy.data.worlds.new('World')
scene.world = world
world.horizon_color = (0.45, 0.5, 0.6)
world.zenith_color = (0.2, 0.3, 0.5)
world.mist_settings.use_mist = False


def mat(nome, cor):
    m = bpy.data.materials.new(nome)
    m.diffuse_color = cor
    return m


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


chao = malha('chao', lambda bm: bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=40.0), (0, 0, 0))
chao.data.materials.append(mat('terra', (0.25, 0.22, 0.18)))
caixa = mat('caixa', (0.35, 0.3, 0.25))
for i, (x, y) in enumerate(((-4, 2), (4.5, 1), (-2, 5))):
    c = malha('caixa_%d' % i, lambda bm: bmesh.ops.create_cube(bm, size=1.2), (x, y, 0.6))
    c.data.materials.append(caixa)

sol_data = bpy.data.lamps.new('sol', 'SUN')
sol_data.energy = 0.8
sol = bpy.data.objects.new('sol', sol_data)
sol.location = (10, -10, 20)
sol.rotation_euler = (radians(50), 0, radians(30))
scene.objects.link(sol)

luz_data = bpy.data.lamps.new('clarao', 'POINT')
luz_data.energy = 0.0
luz_data.color = (1.0, 0.55, 0.2)
luz_data.distance = 14.0
luz = bpy.data.objects.new('clarao', luz_data)
luz.location = (0, 0, 1.2)
scene.objects.link(luz)

cam_data = bpy.data.cameras.new('cam')
cam_data.lens = 24
cam = bpy.data.objects.new('cam', cam_data)
cam.location = (0, -13, 3.0)
cam.rotation_euler = (Vector((0, 0, 2.2)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
scene.objects.link(cam)
scene.camera = cam


def rajada(g, quantas, vida):
    g.emission_mode = 'BURST'
    g.use_burst_on_start = True
    g.burst_interval = 0.0 if EXPLOSIVO else INTERVALO
    g.emit_from = 'VOLUME'
    g.emitter_position = (0, 0, 0)
    g.enabled = True
    g.use_debug_ui = False
    g.particle_count = quantas
    g.lifetime = vida
    g.velocity = (0, 0, 0)
    g.emission_direction = (0, 0, 1)
    g.emission_angle = 179.9  # esfera inteira


expl = bpy.data.objects.new('explosao', None)
expl.location = (0, 0, 0.6)
scene.objects.link(expl)

expl.use_gpu_particles = True
gf = expl.gpu_particles
gf.particle_look = 'FIRE'
rajada(gf, 160, 1.1)
gf.collision_mode = 'NONE'
gf.billboard_mode = 'CAMERA_FACING'
gf.emitter_radius = 0.4
gf.velocity = (0, 0, 1.0)
gf.velocity_randomness = 9.0
gf.drag = 4.5
gf.gravity = (0, 0, 2.0)
gf.size = 1.4
gf.end_size = 2.6
gf.color = (1.0, 1.0, 1.0, 0.7)
gf.end_color = (1.0, 1.0, 1.0, 0.0)
gf.blend_mode = 'ADDITIVE'

expl.use_gpu_particles_mix = True
gm = expl.gpu_particles_mix
gm.particle_look = 'SMOKE'
rajada(gm, 120, 4.5)
gm.collision_mode = 'NONE'
gm.billboard_mode = 'CAMERA_FACING'
gm.emitter_radius = 0.5
gm.velocity = (0, 0, 0.8)
gm.velocity_randomness = 6.0
gm.drag = 2.5
gm.gravity = (0.15, 0, 0.5)
gm.size = 1.2
gm.end_size = 4.5
gm.color = (0.18, 0.16, 0.15, 0.75)
gm.end_color = (0.4, 0.39, 0.38, 0.0)
gm.blend_mode = 'ALPHA'

estilhacos = bpy.data.objects.new('estilhacos', None)
estilhacos.location = (0, 0, 0.6)
scene.objects.link(estilhacos)
estilhacos.use_gpu_particles = True
gs = estilhacos.gpu_particles
gs.particle_look = 'SPARKLE'
rajada(gs, 220, 1.8)
gs.billboard_mode = 'CAMERA_FACING'
gs.emitter_radius = 0.3
gs.velocity = (0, 0, 3.0)
gs.velocity_randomness = 14.0
gs.drag = 0.8
gs.gravity = (0, 0, -9.8)
gs.collision_mode = 'GROUND'
gs.collision_height = 0.0
gs.collision_bounce = 0.3
gs.collision_friction = 0.6
gs.size = 0.09
gs.end_size = 0.03
gs.color = (1.0, 0.75, 0.3, 1.0)
gs.end_color = (1.0, 0.25, 0.05, 0.0)
gs.blend_mode = 'ADDITIVE'

if EXPLOSIVO:
    # Efeito na camada 2 (inativa), criado pelo Explosive no lugar da caixa.
    camada2 = [i == 1 for i in range(20)]
    expl.layers = camada2
    estilhacos.parent = expl
    estilhacos.location = (0, 0, 0)
    estilhacos.layers = camada2
    bomba = malha('bomba', lambda bm: bmesh.ops.create_cube(bm, size=0.8), (0, 0, 0.4))
    bomba.data.materials.append(mat('bomba', (0.6, 0.1, 0.05)))
    bomba.game.use_explosive = True
    ex = bomba.game.explosive
    ex.fuse = PAVIO
    ex.effect = expl
    ex.effect_life = 5.0  # o padrao (0.25 s) mata o efeito antes da fumaca

txt = bpy.data.texts.new('explosao_teste.py')
txt.write(SCRIPT)
scene.objects.active = cam
bpy.ops.logic.sensor_add(type='ALWAYS', name='sempre', object=cam.name)
sens = cam.game.sensors['sempre']
sens.use_pulse_true_level = True
bpy.ops.logic.controller_add(type='PYTHON', name='py', object=cam.name)
ctrl = cam.game.controllers['py']
ctrl.mode = 'MODULE'
ctrl.module = 'explosao_teste.tick'
sens.link(ctrl)

bpy.ops.wm.save_as_mainfile(filepath=saida)
print('EXPLOSAO_SALVO', saida)
