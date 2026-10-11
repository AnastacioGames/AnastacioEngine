# Cria uma cena de teste para o efeito Volumetric Clouds (World > Weather, 3o modo
# de nuvens, junto com Clouds e Sky Layers): terreno com um monte, Sun inclinado,
# camera mirando a cena e World com use_volumetric_clouds ligado.
#   AnastacioEngine.exe -b --factory-startup --python criar_cena_vclouds.py -- saida.range [--all-modes]
import bpy
import sys
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:]
out = argv[0]
all_modes = '--all-modes' in argv[1:]

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

# Terreno grande, posicao explicita para nao nascer no cursor 3D.
bpy.ops.mesh.primitive_plane_add(radius=200, location=(0, 0, 0))
terreno = scene.objects.active
terreno.name = 'terreno'
terreno.data.materials.append(mat_chao)

# Pequeno monte (icosfera achatada) para testar oclusao por depth da sombra das nuvens.
bpy.ops.mesh.primitive_ico_sphere_add(size=25, location=(0, 0, 10))
monte = scene.objects.active
monte.name = 'monte'
monte.scale = (1.4, 1.4, 0.6)
monte.data.materials.append(mat_monte)

# Sun inclinado, posicionado para cair dentro do campo de visao da camera (ver abaixo) --
# a direcao da luz vem so da rotacao do lamp, entao a localizacao escolhida define onde o
# disco do sol aparece na tela.
lamp = bpy.data.lamps.new('sun', 'SUN')
lamp.energy = 1.0
sun = bpy.data.objects.new(lamp.name, lamp)
sun.location = (0, 170, 106)
scene.objects.link(sun)
sun.rotation_euler = (-Vector((0, 170, 106))).to_track_quat('-Z', 'Y').to_euler()

# Camera baixa, olhando quase na direcao do sol (leve inclinacao pra cima) para o disco do
# sol e o silver lining das nuvens ficarem visiveis, mantendo o monte e o terreno no quadro.
cam = bpy.data.objects.new('camera', bpy.data.cameras.new('camera'))
cam.location = (0, -120, 25)
cam.data.type = 'PERSP'
cam.data.lens = 16
cam.rotation_euler = (Vector((0, 60, 45)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
scene.objects.link(cam)
scene.camera = cam

# World com Volumetric Clouds ligado (3o modo, junto com Clouds e Sky Layers).
world = bpy.data.worlds.get('World')
if world is None:
    world = bpy.data.worlds.new('World')
scene.world = world
world.mist_settings.use_mist = False
# Usa o setter real da UI (enum sky_type), nao o bool use_sky_blend direto: setar o bool
# isoladamente deixa os bits antigos Real/Atmospheric ligados (herdados do World padrao do
# factory-startup) e cai no céu atmosférico em vez do gradiente simples -- ver fix do céu preto.
world.sky_type = 'GRADIENT'
world.horizon_color = (0.5, 0.65, 0.85)
world.zenith_color = (0.15, 0.3, 0.65)

weather = world.weather_settings
weather.use_volumetric_clouds = True
weather.vcloud_quality = 'MEDIUM'
weather.vcloud_shadow_enable = True
weather.vcloud_shadow_strength = 0.5
weather.vcloud_coverage = 0.4
weather.vcloud_scale = 1.0
weather.vcloud_speed = 0.3
weather.vcloud_color = (0.95, 0.9, 0.85)
# Altitude/thickness nas unidades da engine (defaults de blenkernel/world.c): nuvens
# claramente acima do monte (altura 10-25) e do terreno, cobrindo parte do ceu visivel.
weather.vcloud_altitude = 80.0
weather.vcloud_thickness = 40.0
weather.vcloud_density = 1.3
weather.vcloud_detail_scale = 1.0
weather.vcloud_silver_intensity = 0.3

if not all_modes:
    # Isola o efeito: desliga os outros dois modos de nuvens (o World padrao nasce com
    # use_clouds=True) para o teste "so volumetric" nao compor com Clouds por acidente.
    weather.use_clouds = False
    weather.use_sky_layers = False
else:
    # Teste de composicao aditiva: os 3 modos de nuvens ligados ao mesmo tempo.
    weather.use_clouds = True
    weather.use_sky_layers = True

# Encerramento automatico do AnastacioRuntime apos alguns segundos, para o teste
# nao depender de fechar a janela manualmente.
txt = bpy.data.texts.new('vclouds_autoclose.py')
txt.write(
    "import bge\n"
    "\n"
    "\n"
    "def tick(cont):\n"
    "    own = cont.owner\n"
    "    frames = own.get('frames', 0) + 1\n"
    "    own['frames'] = frames\n"
    "    # ~15s a 60 fps: encerra sozinho, sem depender de fechar a janela.\n"
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
print('CENA VCLOUDS salva', out, 'all_modes=', all_modes)
