# Cena de teste: fogueira ao entardecer com particulas GPU, fogo (look FIRE) no emissor principal e
# fumaca escura (look SMOKE) no emissor Mix do mesmo Empty.
# Uso: AnastacioEngine.exe -b --factory-startup --python criar_cena_fogo_particulas.py -- <saida.range>
# No jogo: FUMACA_SHOT=<pasta> grava uma captura aos FUMACA_T s (padrao 6) e fecha 1 s depois.
import bpy
import bmesh
import sys
from math import radians
from mathutils import Vector

saida = sys.argv[sys.argv.index('--') + 1]

SCRIPT = (
    "import bge, os\n"
    "def tick(cont):\n"
    "    own = cont.owner\n"
    "    pasta = os.environ.get('FUMACA_SHOT')\n"
    "    if not pasta:\n"
    "        return\n"
    "    t = bge.logic.getRealTime()\n"
    "    if 'inicio' not in own:\n"
    "        own['inicio'] = t\n"
    "    dt = t - own['inicio']\n"
    "    limite = float(os.environ.get('FUMACA_T', '6'))\n"
    "    if dt > limite and 'foto' not in own:\n"
    "        own['foto'] = 1\n"
    "        os.makedirs(pasta, exist_ok=True)\n"
    "        bge.render.makeScreenshot(os.path.join(pasta, 'fogo.png'))\n"
    "    if dt > limite + 1.0:\n"
    "        bge.logic.endGame()\n"
)

scene = bpy.context.scene
for ob in list(scene.objects):
    scene.objects.unlink(ob)
scene.render.engine = 'BLENDER_GAME'
scene.render.resolution_x = 1280
scene.render.resolution_y = 720
scene.game_settings.use_frame_rate = False

world = scene.world or bpy.data.worlds.new('World')
scene.world = world
world.horizon_color = (0.3, 0.22, 0.25)
world.zenith_color = (0.08, 0.1, 0.2)
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


chao = malha('chao', lambda bm: bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=30.0), (0, 0, 0))
chao.data.materials.append(mat('terra', (0.18, 0.14, 0.1)))
madeira = mat('madeira', (0.2, 0.1, 0.05))
for i, ang in enumerate((0, 60, 120)):
    tora = malha('tora_%d' % i, lambda bm: bmesh.ops.create_cone(bm, cap_ends=True, segments=10, diameter1=0.18,
                                                                 diameter2=0.18, depth=1.8), (0, 0, 0.18))
    tora.rotation_euler = (radians(90), 0, radians(ang))
    tora.data.materials.append(madeira)
pedra = mat('pedra', (0.35, 0.35, 0.33))
for i in range(8):
    v = Vector((1.15, 0, 0))
    v.rotate(__import__('mathutils').Euler((0, 0, radians(i * 45))))
    p = malha('pedra_%d' % i, lambda bm: bmesh.ops.create_icosphere(bm, subdivisions=1, diameter=0.22), (v.x, v.y, 0.15))
    p.data.materials.append(pedra)

sol_data = bpy.data.lamps.new('sol', 'SUN')
sol_data.energy = 0.35
sol_data.color = (1.0, 0.6, 0.4)
sol = bpy.data.objects.new('sol', sol_data)
sol.location = (10, -10, 20)
sol.rotation_euler = (radians(75), 0, radians(40))
scene.objects.link(sol)

luz_data = bpy.data.lamps.new('brasa', 'POINT')
luz_data.energy = 3.0
luz_data.color = (1.0, 0.5, 0.15)
luz_data.distance = 8.0
luz = bpy.data.objects.new('brasa', luz_data)
luz.location = (0, 0, 0.8)
scene.objects.link(luz)
# Luz que tremula como a chama (propriedade de jogo light_flicker, 0..2).
scene.objects.active = luz
bpy.ops.object.game_property_new(type='FLOAT', name='light_flicker')
luz.game.properties['light_flicker'].value = 1.0

cam_data = bpy.data.cameras.new('cam')
cam_data.lens = 24
cam = bpy.data.objects.new('cam', cam_data)
cam.location = (0, -7.5, 2.4)
cam.rotation_euler = (Vector((0, 0, 1.8)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
scene.objects.link(cam)
scene.camera = cam

fogo = bpy.data.objects.new('fogo', None)
fogo.location = (0, 0, 0.25)
scene.objects.link(fogo)
fogo.use_gpu_particles = True
gp = fogo.gpu_particles
gp.particle_look = 'FIRE'
gp.emit_from = 'VOLUME'
gp.emitter_position = (0, 0, 0)
gp.enabled = True
gp.collision_mode = 'NONE'
gp.use_debug_ui = False

fogo.use_gpu_particles_mix = True
gm = fogo.gpu_particles_mix
gm.particle_look = 'SMOKE'
gm.emit_from = 'VOLUME'
gm.emitter_position = (0, 0, 1.4)
gm.enabled = True
gm.collision_mode = 'NONE'
gm.use_debug_ui = False
gm.billboard_mode = 'CAMERA_FACING'
gm.particle_count = 90
gm.lifetime = 7.0
gm.emitter_radius = 0.25
gm.velocity = (0.15, 0.0, 1.0)
gm.velocity_randomness = 0.35
gm.emission_direction = (0, 0, 1)
gm.emission_angle = 20
gm.gravity = (0.12, 0.0, 0.05)
gm.size = 0.6
gm.end_size = 3.5
gm.color = (0.5, 0.48, 0.47, 0.4)
gm.end_color = (0.62, 0.6, 0.6, 0.0)
gm.blend_mode = 'ALPHA'

# Fagulhas: micro particulas num segundo Empty (cada objeto tem so 2 emissores).
fagulhas = bpy.data.objects.new('fagulhas', None)
fagulhas.location = (0, 0, 0.4)
scene.objects.link(fagulhas)
fagulhas.use_gpu_particles = True
gs = fagulhas.gpu_particles
gs.particle_look = 'SPARKLE'
gs.emit_from = 'VOLUME'
gs.emitter_position = (0, 0, 0)
gs.enabled = True
gs.collision_mode = 'NONE'
gs.use_debug_ui = False
gs.billboard_mode = 'CAMERA_FACING'
gs.particle_count = 90
gs.lifetime = 1.8
gs.emitter_radius = 0.4
gs.velocity = (0.1, 0.0, 2.6)
gs.velocity_randomness = 1.1
gs.emission_direction = (0, 0, 1)
gs.emission_angle = 35
gs.gravity = (0.2, 0.0, -0.6)
gs.size = 0.07
gs.end_size = 0.02
gs.color = (1.0, 0.6, 0.15, 1.0)
gs.end_color = (1.0, 0.2, 0.02, 0.0)
gs.blend_mode = 'ADDITIVE'

txt = bpy.data.texts.new('fogo_teste.py')
txt.write(SCRIPT)
scene.objects.active = cam
bpy.ops.logic.sensor_add(type='ALWAYS', name='sempre', object=cam.name)
sens = cam.game.sensors['sempre']
sens.use_pulse_true_level = True
bpy.ops.logic.controller_add(type='PYTHON', name='py', object=cam.name)
ctrl = cam.game.controllers['py']
ctrl.mode = 'MODULE'
ctrl.module = 'fogo_teste.tick'
sens.link(ctrl)

bpy.ops.wm.save_as_mainfile(filepath=saida)
print('FOGO_SALVO', saida)
