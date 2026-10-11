# Cena de teste para validar o novo modelo de luz do Volumetric Clouds (silver lining mais
# forte + nuvem embranquecendo no lado iluminado em vez de so escalar um cinza) em varias
# variantes dentro do MESMO .range: 4 cenas com parametros diferentes de silver_intensity e
# angulo camera/sol, alternando automaticamente a cada ~6s via Scene Actuator (SET), cada uma
# com uma placa de texto 3D identificando a variante.
#   AnastacioEngine.exe -b --factory-startup --python criar_cena_vclouds_luz.py -- saida.range
import bpy
import sys
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:]
out = argv[0]

bpy.ops.wm.read_factory_settings(use_empty=True)

CICLO_FRAMES = 360  # ~6s a 60fps


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


def montar_variante(nome, label, sun_loc, silver_intensity, coverage, density, cam_para_sol):
    scene = bpy.data.scenes.new(nome)
    scene.render.engine = 'BLENDER_GAME'
    scene.game_settings.use_shading_nodes = True
    bpy.context.screen.scene = scene

    mat_chao = principled(nome + '_chao', (0.25, 0.4, 0.15, 1.0))
    mat_monte = principled(nome + '_monte', (0.4, 0.35, 0.25, 1.0))

    bpy.ops.mesh.primitive_plane_add(radius=200, location=(0, 0, 0))
    terreno = scene.objects.active
    terreno.name = nome + '_terreno'
    terreno.data.materials.append(mat_chao)

    bpy.ops.mesh.primitive_ico_sphere_add(size=25, location=(0, 0, 10))
    monte = scene.objects.active
    monte.name = nome + '_monte'
    monte.scale = (1.4, 1.4, 0.6)
    monte.data.materials.append(mat_monte)

    lamp = bpy.data.lamps.new(nome + '_sun', 'SUN')
    lamp.energy = 1.0
    sun = bpy.data.objects.new(lamp.name, lamp)
    sun.location = sun_loc
    scene.objects.link(sun)
    sun.rotation_euler = (-Vector(sun_loc)).to_track_quat('-Z', 'Y').to_euler()

    cam = bpy.data.objects.new(nome + '_camera', bpy.data.cameras.new(nome + '_camera'))
    cam.data.type = 'PERSP'
    cam.data.lens = 16
    if cam_para_sol:
        # Camera olhando quase na direcao do sol -- silver lining (forward scatter) visivel.
        cam.location = (0, -120, 25)
        alvo = Vector((0, 60, 45))
    else:
        # Camera de costas pro sol -- so back-scatter e o ambiente frio das sombras visiveis.
        cam.location = (0, 120, 25)
        alvo = Vector((0, -60, 45))
    cam.rotation_euler = (alvo - cam.location).to_track_quat('-Z', 'Y').to_euler()
    scene.objects.link(cam)
    scene.camera = cam

    # Placa de texto 3D com o nome da variante, flutuando acima do monte, dentro do quadro.
    txt_curve = bpy.data.curves.new(nome + '_label', 'FONT')
    txt_curve.body = label
    txt_curve.size = 6.0
    txt_curve.align_x = 'CENTER'
    placa = bpy.data.objects.new(nome + '_label', txt_curve)
    placa.location = (0, 20, 45)
    placa.rotation_euler = (1.5708, 0, 0)
    scene.objects.link(placa)

    world = bpy.data.worlds.new(nome + '_world')
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
    weather.vcloud_coverage = coverage
    weather.vcloud_scale = 1.0
    weather.vcloud_speed = 0.0  # cena parada: nao mascara a comparacao com movimento das nuvens
    weather.vcloud_color = (0.95, 0.9, 0.85)
    weather.vcloud_altitude = 80.0
    weather.vcloud_thickness = 40.0
    weather.vcloud_density = density
    weather.vcloud_detail_scale = 1.0
    weather.vcloud_silver_intensity = silver_intensity

    return scene, terreno


# vcloud_density e PROP_FACTOR com range [0.0, 1.0] (rna_world.c) -- 1.0 e o maximo valido.
variantes = [
    montar_variante('A_silver_baixo', 'A: silver 0.1 (para o sol)', (0, 170, 106), 0.1, 0.4, 1.0, True),
    montar_variante('B_silver_alto', 'B: silver 0.6 (para o sol)', (0, 170, 106), 0.6, 0.4, 1.0, True),
    montar_variante('C_contraluz', 'C: silver 0.3 (de costas p/ sol)', (0, 170, 106), 0.3, 0.4, 1.0, False),
    montar_variante('D_denso', 'D: denso, silver 0.3 (para o sol)', (0, 170, 106), 0.3, 0.7, 1.0, True),
]

# Encadeia as 4 cenas num ciclo: cada uma troca pra proxima apos CICLO_FRAMES frames via
# Scene Actuator (mode SET); a ultima volta pra primeira. Encerramento automatico apos 1 volta
# completa, pra nao depender de fechar a janela manualmente.
total = len(variantes)
for i, (scene, terreno) in enumerate(variantes):
    proxima = variantes[(i + 1) % total][0]
    scene.objects.active = terreno
    bpy.ops.logic.sensor_add(type='DELAY', name='espera', object=terreno.name)
    sens = terreno.game.sensors['espera']
    sens.delay = CICLO_FRAMES
    sens.use_repeat = False

    bpy.ops.logic.controller_add(type='LOGIC_AND', name='and', object=terreno.name)
    ctrl = terreno.game.controllers['and']

    bpy.ops.logic.actuator_add(type='SCENE', name='troca', object=terreno.name)
    act = terreno.game.actuators['troca']
    act.mode = 'SET'
    act.scene = proxima

    sens.link(ctrl)
    ctrl.link(actuator=act)

    if i == total - 1:
        # Ultima variante: alem de trocar de cena, usa um modulo Python pra contar quantas
        # voltas completas e encerrar o jogo sozinho depois de 1 volta.
        txt = bpy.data.texts.new(scene.name + '_autoclose.py')
        txt.write(
            "import bge\n"
            "\n"
            "\n"
            "def tick(cont):\n"
            "    own = cont.owner\n"
            "    voltas = own.get('voltas', 0) + 1\n"
            "    own['voltas'] = voltas\n"
            "    if voltas >= 1:\n"
            "        bge.logic.endGame()\n"
        )
        bpy.ops.logic.sensor_add(type='DELAY', name='espera_fim', object=terreno.name)
        sens_fim = terreno.game.sensors['espera_fim']
        sens_fim.delay = CICLO_FRAMES - 5
        sens_fim.use_repeat = False
        bpy.ops.logic.controller_add(type='PYTHON', name='autoclose', object=terreno.name)
        ctrl_fim = terreno.game.controllers['autoclose']
        ctrl_fim.mode = 'MODULE'
        ctrl_fim.module = txt.name.replace('.py', '') + '.tick'
        sens_fim.link(ctrl_fim)

# Remove a cena vazia "Scene" criada pelo read_factory_settings(use_empty=True), se restou.
if 'Scene' in bpy.data.scenes and bpy.data.scenes['Scene'] not in [v[0] for v in variantes]:
    bpy.data.scenes.remove(bpy.data.scenes['Scene'])

bpy.context.screen.scene = variantes[0][0]

bpy.ops.wm.save_as_mainfile(filepath=out, check_existing=False)
print('CENA VCLOUDS LUZ salva', out, '| variantes:', [v[0].name for v in variantes])
