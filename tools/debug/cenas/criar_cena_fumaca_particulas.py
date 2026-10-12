# Cena de teste: chamine de dia soltando fumaca com particulas GPU (look SMOKE).
# Uso: AnastacioEngine.exe -b --factory-startup --python criar_cena_fumaca_particulas.py -- <saida.range>
# No jogo: FUMACA_SHOT=<pasta> grava uma captura aos FUMACA_T s (padrao 6) e fecha 1 s depois; sem ela roda normal.
import bpy
import bmesh
import sys
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
    "    if dt > float(os.environ.get('FUMACA_T', '6')) and 'foto' not in own:\n"
    "        own['foto'] = 1\n"
    "        os.makedirs(pasta, exist_ok=True)\n"
    "        bge.render.makeScreenshot(os.path.join(pasta, 'fumaca.png'))\n"
    "    if dt > float(os.environ.get('FUMACA_T', '6')) + 1.0:\n"
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
world.horizon_color = (0.62, 0.66, 0.72)
world.zenith_color = (0.38, 0.5, 0.7)
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


chao = malha('chao', lambda bm: bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=60.0), (0, 0, 0))
chao.data.materials.append(mat('chao', (0.3, 0.32, 0.28)))
parede = malha('parede', lambda bm: bmesh.ops.create_cube(bm, size=1.0), (0, 25, 15))
parede.scale = (24, 1, 30)
parede.data.materials.append(mat('parede', (0.2, 0.35, 0.25)))
chamine = malha('chamine', lambda bm: bmesh.ops.create_cone(bm, cap_ends=True, segments=24, diameter1=1.1,
                                                            diameter2=0.8, depth=14.0), (0, 0, 7.0))
chamine.data.materials.append(mat('tijolo', (0.55, 0.12, 0.08)))

sol_data = bpy.data.lamps.new('sol', 'SUN')
sol_data.energy = 1.2
sol = bpy.data.objects.new('sol', sol_data)
sol.location = (10, -10, 30)
sol.rotation_euler = (0.9, 0.2, 0.6)
scene.objects.link(sol)

cam_data = bpy.data.cameras.new('cam')
cam_data.lens = 24
cam = bpy.data.objects.new('cam', cam_data)
cam.location = (0, -34, 12)
cam.rotation_euler = (Vector((0, 0, 17)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
scene.objects.link(cam)
scene.camera = cam

# Emissor: um Empty no topo da chamine.
fumaca = bpy.data.objects.new('fumaca', None)
fumaca.location = (0, 0, 14.0)
scene.objects.link(fumaca)
fumaca.use_gpu_particles = True
gp = fumaca.gpu_particles
gp.particle_look = 'SMOKE'
gp.particle_count = 240
gp.emit_from = 'VOLUME'
gp.emitter_position = (0, 0, 0)
gp.enabled = True
gp.collision_mode = 'NONE'
gp.billboard_mode = 'CAMERA_FACING'
gp.use_debug_ui = False
gp.lifetime = 10.0
gp.emitter_radius = 0.3
gp.velocity = (0.3, 0.0, 1.8)
gp.velocity_randomness = 0.7
gp.emission_direction = (0, 0, 1)
gp.emission_angle = 25
gp.gravity = (0.35, 0.0, -0.05)
gp.size = 1.3
gp.end_size = 9.0
gp.color = (0.92, 0.92, 0.94, 0.85)
gp.end_color = (0.7, 0.72, 0.76, 0.0)
gp.blend_mode = 'ALPHA'

txt = bpy.data.texts.new('fumaca_teste.py')
txt.write(SCRIPT)
scene.objects.active = cam
bpy.ops.logic.sensor_add(type='ALWAYS', name='sempre', object=cam.name)
sens = cam.game.sensors['sempre']
sens.use_pulse_true_level = True
bpy.ops.logic.controller_add(type='PYTHON', name='py', object=cam.name)
ctrl = cam.game.controllers['py']
ctrl.mode = 'MODULE'
ctrl.module = 'fumaca_teste.tick'
sens.link(ctrl)

bpy.ops.wm.save_as_mainfile(filepath=saida)
print('FUMACA_SALVA', saida)
