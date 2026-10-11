# Debug: 1 unica cena com os mesmos parametros de uma variante de criar_cena_vclouds_luz.py
# (sem troca de cena via ator), pra isolar se a tela preta vem da construcao da variante ou
# do encadeamento multi-cena.
#   AnastacioEngine.exe -b --factory-settings --python criar_cena_vclouds_debug1.py -- saida.range
import bpy
import sys
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:]
out = argv[0]

scene = bpy.context.scene
for ob in list(scene.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.use_shading_nodes = True


def principled(name, color):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    for n in list(nodes):
        nodes.remove(n)
    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = color
    out_node = nodes.new('ShaderNodeOutputMaterial')
    mat.node_tree.links.new(bsdf.outputs[0], out_node.inputs[0])
    return mat


mat_chao = principled('chao', (0.25, 0.4, 0.15, 1.0))
mat_monte = principled('monte', (0.4, 0.35, 0.25, 1.0))

bpy.ops.mesh.primitive_plane_add(radius=200, location=(0, 0, 0))
terreno = scene.objects.active
terreno.name = 'terreno'
terreno.data.materials.append(mat_chao)

bpy.ops.mesh.primitive_ico_sphere_add(size=25, location=(0, 0, 10))
monte = scene.objects.active
monte.name = 'monte'
monte.scale = (1.4, 1.4, 0.6)
monte.data.materials.append(mat_monte)

lamp = bpy.data.lamps.new('sun', 'SUN')
lamp.energy = 1.0
sun_loc = (0, 170, 106)
sun = bpy.data.objects.new(lamp.name, lamp)
sun.location = sun_loc
scene.objects.link(sun)
sun.rotation_euler = (-Vector(sun_loc)).to_track_quat('-Z', 'Y').to_euler()

cam = bpy.data.objects.new('camera', bpy.data.cameras.new('camera'))
cam.data.type = 'PERSP'
cam.data.lens = 16
cam.location = (0, -120, 25)
alvo = Vector((0, 60, 45))
cam.rotation_euler = (alvo - cam.location).to_track_quat('-Z', 'Y').to_euler()
scene.objects.link(cam)
scene.camera = cam

# Placa de texto 3D -- mesmo elemento novo da versao multi-cena, pra testar se ELA que
# quebra o render (curva FONT nao linkada direito, por exemplo).
txt_curve = bpy.data.curves.new('label', 'FONT')
txt_curve.body = 'TESTE DEBUG1: silver 0.6 (para o sol)'
txt_curve.size = 6.0
txt_curve.align_x = 'CENTER'
placa = bpy.data.objects.new('label', txt_curve)
placa.location = (0, 20, 45)
placa.rotation_euler = (1.5708, 0, 0)
scene.objects.link(placa)

world = bpy.data.worlds.get('World')
if world is None:
    world = bpy.data.worlds.new('World')
scene.world = world
world.mist_settings.use_mist = False
world.sky_type = 'GRADIENT'
world.horizon_color = (0.5, 0.65, 0.85)
world.zenith_color = (0.15, 0.3, 0.65)

weather = world.weather_settings
weather.use_volumetric_clouds = True
weather.use_clouds = False
weather.use_sky_layers = False
weather.vcloud_quality = 'MEDIUM'
weather.vcloud_shadow_enable = True
weather.vcloud_shadow_strength = 0.5
weather.vcloud_coverage = 0.4
weather.vcloud_scale = 1.0
weather.vcloud_speed = 0.0
weather.vcloud_color = (0.95, 0.9, 0.85)
weather.vcloud_altitude = 80.0
weather.vcloud_thickness = 40.0
weather.vcloud_density = 1.0
weather.vcloud_detail_scale = 1.0
weather.vcloud_silver_intensity = 0.6

txt = bpy.data.texts.new('vclouds_autoclose.py')
txt.write(
    "import bge\n"
    "\n"
    "\n"
    "def tick(cont):\n"
    "    own = cont.owner\n"
    "    frames = own.get('frames', 0) + 1\n"
    "    own['frames'] = frames\n"
    "    if frames > 900:\n"
    "        bge.logic.endGame()\n"
)

scene.objects.active = terreno
bpy.ops.logic.sensor_add(type='ALWAYS', name='always', object='terreno')
terreno.game.sensors['always'].use_pulse_true_level = True
bpy.ops.logic.controller_add(type='PYTHON', name='autoclose', object='terreno')
ctrl = terreno.game.controllers['autoclose']
ctrl.mode = 'MODULE'
ctrl.module = 'vclouds_autoclose.tick'
terreno.game.sensors['always'].link(terreno.game.controllers['autoclose'])

bpy.ops.wm.save_as_mainfile(filepath=out, check_existing=False)
print('CENA DEBUG1 salva', out)
