# Cena de teste: Explosive > Particle Explosion nos 5 tamanhos (Tiny, Small, Medium, Large, Huge).
# Cinco caixas explosivas em fila, pavios de 1, 3, 5, 7 e 9 s, sem objeto Effect.
# Uso: AnastacioEngine.exe -b --factory-startup --python criar_cena_explosao_tamanhos.py -- <saida.range>
# No jogo: FUMACA_SHOT=<pasta> grava tamanho_<n>.png 0.4 s depois de cada explosao e fecha no fim.
import bpy
import bmesh
import sys
from math import radians
from mathutils import Vector

saida = sys.argv[sys.argv.index('--') + 1]
TAMANHOS = ('TINY', 'SMALL', 'MEDIUM', 'LARGE', 'HUGE')
PAVIOS = (1.0, 3.0, 5.0, 7.0, 9.0)

SCRIPT = (
    "import bge, os\n"
    "PAVIOS = %r\n"
    "def tick(cont):\n"
    "    own = cont.owner\n"
    "    pasta = os.environ.get('FUMACA_SHOT')\n"
    "    if not pasta:\n"
    "        return\n"
    "    t = bge.logic.getRealTime()\n"
    "    if 'inicio' not in own:\n"
    "        own['inicio'] = t\n"
    "    dt = t - own['inicio']\n"
    "    feitas = own.get('feitas', 0)\n"
    "    if feitas < len(PAVIOS) and dt > PAVIOS[feitas] + 0.4:\n"
    "        own['feitas'] = feitas + 1\n"
    "        os.makedirs(pasta, exist_ok=True)\n"
    "        bge.render.makeScreenshot(os.path.join(pasta, 'tamanho_%%d.png' %% feitas))\n"
    "    if dt > PAVIOS[-1] + 1.0:\n"
    "        bge.logic.endGame()\n"
) % (PAVIOS,)

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


def malha(nome, fazer, pos, cor):
    me = bpy.data.meshes.new(nome)
    bm = bmesh.new()
    fazer(bm)
    bm.to_mesh(me)
    bm.free()
    m = bpy.data.materials.new(nome)
    m.diffuse_color = cor
    me.materials.append(m)
    ob = bpy.data.objects.new(nome, me)
    ob.location = pos
    scene.objects.link(ob)
    return ob


malha('chao', lambda bm: bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=80.0), (0, 0, 0),
      (0.25, 0.22, 0.18))

sol_data = bpy.data.lamps.new('sol', 'SUN')
sol_data.energy = 0.8
sol = bpy.data.objects.new('sol', sol_data)
sol.rotation_euler = (radians(50), 0, radians(30))
scene.objects.link(sol)

for i, (tam, pavio) in enumerate(zip(TAMANHOS, PAVIOS)):
    bomba = malha('bomba_%s' % tam.lower(), lambda bm: bmesh.ops.create_cube(bm, size=0.8),
                  (-20 + i * 10, 0, 0.4), (0.6, 0.1, 0.05))
    bomba.game.use_explosive = True
    ex = bomba.game.explosive
    ex.fuse = pavio
    ex.use_explode_on_impact = False
    ex.use_chain_reaction = False
    ex.use_particle_explosion = True
    ex.particle_size = tam

cam_data = bpy.data.cameras.new('cam')
cam_data.lens = 22
cam = bpy.data.objects.new('cam', cam_data)
cam.location = (0, -42, 9)
cam.rotation_euler = (Vector((0, 0, 5)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
scene.objects.link(cam)
scene.camera = cam

txt = bpy.data.texts.new('tamanhos_teste.py')
txt.write(SCRIPT)
scene.objects.active = cam
bpy.ops.logic.sensor_add(type='ALWAYS', name='sempre', object=cam.name)
sens = cam.game.sensors['sempre']
sens.use_pulse_true_level = True
bpy.ops.logic.controller_add(type='PYTHON', name='py', object=cam.name)
ctrl = cam.game.controllers['py']
ctrl.mode = 'MODULE'
ctrl.module = 'tamanhos_teste.tick'
sens.link(ctrl)

bpy.ops.wm.save_as_mainfile(filepath=saida)
print('TAMANHOS_SALVO', saida)
