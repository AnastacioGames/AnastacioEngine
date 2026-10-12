# Volumetric Fog: mesma cena em off/low/medium/high (+ medium so com Fog Volume). Noite, chao,
# colunas, lampada vermelha e azul, Spot com sombra e um cubo dentro do cone (raios de luz).
# FPS medio de ~10 s (descarta 3 s) vai para o arquivo da variavel VFOG_FPS_LOG e o jogo fecha.
#   AnastacioEngine.exe -b --factory-startup --python criar_cena_vfog.py -- pasta_saida
import bpy
import bmesh
import math
import os
import sys
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:]
pasta = argv[0]

SCRIPT = (
    "import bge, os, time\n"
    "\n"
    "\n"
    "def tick(cont):\n"
    "    own = cont.owner\n"
    "    agora = time.perf_counter()\n"
    "    world = bge.logic.getCurrentScene().world\n"
    "    if own['preset'] == 'medium_script':\n"
    "        fase = agora * 0.8\n"
    "        world.setWeather('vfog', True)\n"
    "        world.setWeather('vfog_density', 0.04 + 0.03 * (1.0 + __import__('math').sin(fase)))\n"
    "        world.setWeather('vfog_color_r', 0.35 + 0.35 * (1.0 + __import__('math').sin(fase)))\n"
    "        world.setWeather('vfog_color_g', 0.30 + 0.20 * (1.0 + __import__('math').sin(fase + 2.1)))\n"
    "        world.setWeather('vfog_color_b', 0.45 + 0.20 * (1.0 + __import__('math').sin(fase + 4.2)))\n"
    "    if own['preset'] == 'medium_abre':\n"
    "        bola = bge.logic.getCurrentScene().objects['bola_push']\n"
    "        bola.worldPosition.x = 8.0 * __import__('math').sin(agora * 0.6)\n"
    "    if own['preset'] == 'medium_explosao':\n"
    "        explosao = bge.logic.getCurrentScene().objects['explosao']\n"
    "        fase = (agora % 1.5) / 1.5\n"
    "        explosao['fog_fire'] = 1.0 - fase\n"
    "        escala = 0.35 + 2.15 * fase\n"
    "        explosao.localScale = (escala, escala, escala)\n"
    "    if 'inicio' not in own:\n"
    "        own['inicio'] = agora\n"
    "        own['frames'] = 0\n"
    "        return\n"
    "    dt = agora - own['inicio']\n"
    "    if dt < 3.0:\n"
    "        return\n"
    "    foto = os.environ.get('VFOG_SHOT')\n"
    "    if foto and 'foto' not in own:\n"
    "        own['foto'] = 1\n"
    "        from bge import render\n"
    "        render.makeScreenshot(os.path.join(foto, own['preset'] + '.png'))\n"
    "    if 'medida' not in own:\n"
    "        own['medida'] = agora\n"
    "        own['frames'] = 0\n"
    "        return\n"
    "    own['frames'] += 1\n"
    "    janela = agora - own['medida']\n"
    "    if janela >= 10.0:\n"
    "        fps = own['frames'] / janela\n"
    "        caminho = os.environ.get('VFOG_FPS_LOG')\n"
    "        if caminho:\n"
    "            with open(caminho, 'a') as f:\n"
    "                f.write('%s fps=%.1f ms=%.2f\\n' % (own['preset'], fps, 1000.0 / fps))\n"
    "                if own['preset'] == 'medium_script':\n"
    "                    f.write('VFOG_SCRIPT enabled=%r density=%.4f color=(%.4f, %.4f, %.4f) property_density=%r\\n' % (world.getWeather('vfog'), world.getWeather('vfog_density'), world.getWeather('vfog_color_r'), world.getWeather('vfog_color_g'), world.getWeather('vfog_color_b'), world['vfog_density']))\n"
    "                if own['preset'] == 'medium_explosao':\n"
    "                    explosao = bge.logic.getCurrentScene().objects['explosao']\n"
    "                    f.write('VFOG_EXPLOSAO fire=%.3f scale=%.3f\\n' % (explosao['fog_fire'], explosao.localScale.x))\n"
    "        bge.logic.endGame()\n"
)


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


def malha(name, criar, location):
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    criar(bm)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    obj.location = location
    return obj



def lampada(name, tipo, location, color, energy, dist, alvo=None):
    la = bpy.data.lamps.new(name, tipo)
    la.color = color
    la.energy = energy
    la.distance = dist
    ob = bpy.data.objects.new(name, la)
    ob.location = location
    if alvo is not None:
        ob.rotation_euler = (Vector(alvo) - Vector(location)).to_track_quat('-Z', 'Y').to_euler()
    bpy.context.scene.objects.link(ob)
    return ob


def gerar(preset):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_GAME'
    gs = scene.game_settings
    gs.use_shading_nodes = True
    gs.use_frame_rate = False
    gs.vsync = 'OFF'
    gs.resolution_x = 1280
    gs.resolution_y = 720

    chao = malha('chao', lambda bm: bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=60), (0, 0, 0))
    chao.data.materials.append(principled('chao', (0.35, 0.35, 0.38, 1.0)))
    scene.objects.link(chao)
    for i, x in enumerate((-12, -4, 4, 12)):
        col = malha('coluna%d' % i, lambda bm: bmesh.ops.create_cube(bm, size=1.0), (x, 18, 6))
        col.scale = (2.5, 2.5, 12)
        col.data.materials.append(principled('coluna%d' % i, (0.5, 0.45, 0.4, 1.0)))
        scene.objects.link(col)
    cubo = malha('cubo_no_cone', lambda bm: bmesh.ops.create_cube(bm, size=1.5), (6, 4, 4))
    cubo.data.materials.append(principled('cubo', (0.2, 0.6, 0.2, 1.0)))
    scene.objects.link(cubo)

    sun = lampada('sun', 'SUN', (0, 60, 40), (1.0, 0.95, 0.85), 0.3, 100, alvo=(0, 0, 0))
    lampada('vermelha', 'POINT', (-8, 6, 2.5), (1.0, 0.15, 0.1), 4.0, 12)
    lampada('azul', 'POINT', (-2, 12, 2.5), (0.15, 0.3, 1.0), 4.0, 12)
    spot = lampada('spot', 'SPOT', (6, 4, 12), (1.0, 0.9, 0.7), 6.0, 30, alvo=(6, 4, 0))
    spot.data.spot_size = math.radians(50)
    spot.data.spot_blend = 0.3
    spot.data.use_shadow = True
    spot.data.shadow_buffer_size = 1024

    cam = bpy.data.objects.new('camera', bpy.data.cameras.new('camera'))
    cam.data.type = 'PERSP'
    cam.data.lens = 16
    cam.location = (0, -16, 6)
    cam.rotation_euler = (Vector((0, 8, 3)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    scene.objects.link(cam)
    scene.camera = cam

    world = bpy.data.worlds.new('World')
    scene.world = world
    world.mist_settings.use_mist = False
    world.horizon_color = (0.05, 0.06, 0.1)
    world.zenith_color = (0.01, 0.01, 0.03)
    w = world.weather_settings
    w.use_clouds = False
    w.use_sky_layers = False
    w.use_volumetric_clouds = False
    w.use_volumetric_fog = preset not in ('off', 'medium_script')
    if preset != 'off':
        w.vfog_quality = preset.split('_')[0].upper()
    w.vfog_density = 0.08
    w.vfog_base = 0.0
    w.vfog_falloff = 6.0
    w.vfog_distance = 80.0
    w.vfog_noise_amount = 0.5
    w.vfog_ambient = 0.5
    w.vfog_light_intensity = 2.0

    if preset == 'medium_script':
        # Starts disabled: the runtime script below must create and enable the filter.
        if not world.properties.get('vfog_enabled'):
            bpy.ops.world.game_property_new(type='BOOL', name='vfog_enabled')
        if not world.properties.get('vfog_density'):
            bpy.ops.world.game_property_new(type='FLOAT', name='vfog_density')
        world.properties['vfog_enabled'].value = False
        world.properties['vfog_density'].value = w.vfog_density

    if preset.endswith('_noshaft'):
        w.vfog_use_shafts = False

    if preset.endswith('_dia'):
        # Mar de neblina de dia, denso e claro (como a referencia do usuario): camera alta.
        sun.data.energy = 1.2
        world.horizon_color = (0.8, 0.85, 0.75)
        world.zenith_color = (0.35, 0.55, 0.85)
        w.vfog_density = 0.35
        w.vfog_falloff = 4.0
        w.vfog_distance = 150.0
        w.vfog_noise_amount = 0.6
        w.vfog_noise_scale = 0.08
        w.vfog_ambient = 1.0
        w.vfog_sun_intensity = 1.5
        w.vfog_color = (0.95, 0.95, 0.92)
        cam.location = (0, -22, 14)
        cam.rotation_euler = (Vector((0, 10, 2)) - cam.location).to_track_quat('-Z', 'Y').to_euler()

    if preset.endswith('_volume'):
        w.vfog_volumes_only = True
        vol = malha('fog_volume', lambda bm: bmesh.ops.create_cube(bm, size=2.0), (-5, 9, 3))
        vol.scale = (8, 6, 3)
        vol.game.physics_type = 'NO_COLLISION'
        vol.hide_render = True
        scene.objects.link(vol)
        scene.objects.active = vol
        bpy.ops.object.game_property_new(type='FLOAT', name='fog_volume')
        vol.game.properties['fog_volume'].value = 2.0

    # Itens 1-3 do docs/plano-volumetric.md.
    if preset == 'medium_sol':
        # Sol baixo atras das colunas, com sombra: raios de sol (Sun Shafts) vindo para a camera.
        sun.location = (0, 45, 10)
        sun.rotation_euler = (Vector((0, 0, 0)) - sun.location).to_track_quat('-Z', 'Y').to_euler()
        sun.data.energy = 1.5
        sun.data.use_shadow = True
        sun.data.shadow_buffer_size = 2048
        sun.data.shadow_frustum_size = 70.0
        sun.data.shadow_buffer_clip_start = 1.0
        sun.data.shadow_buffer_clip_end = 120.0
        world.horizon_color = (0.5, 0.4, 0.3)
        w.vfog_density = 0.12
        w.vfog_falloff = 10.0
        w.vfog_ambient = 0.15
        w.vfog_sun_intensity = 2.5
        w.vfog_anisotropy = 0.6
        w.vfog_use_sun_shafts = True
    if preset == 'medium_vento':
        w.vfog_use_wind = True
        w.vfog_wind_direction = 30.0
        world.weather_settings.rain_wind = 0.5
        w.vfog_noise_amount = 0.9
    if preset == 'medium_manha':
        w.vfog_use_time_of_day = True
        w.vfog_morning_boost = 2.0
        if not world.properties.get('sun_hour'):
            bpy.ops.world.game_property_new(type='FLOAT', name='sun_hour')
        world.properties['sun_hour'].value = 6.0
    if preset == 'medium_volumes':
        w.vfog_volumes_only = True
        w.vfog_edge = 0.5
        formas = (('fog_esfera', 'sphere', (-6, 8, 3), (4, 4, 4), (1.0, 0.45, 0.2, 1.0)),
                  ('fog_caixa', 'box', (6, 10, 2.5), (5, 4, 2.5), (0.3, 0.9, 0.5, 1.0)))
        for nome, forma, loc, escala, cor in formas:
            vol = malha(nome, lambda bm: bmesh.ops.create_cube(bm, size=2.0), loc)
            vol.scale = escala
            vol.color = cor
            vol.game.physics_type = 'NO_COLLISION'
            vol.hide_render = True
            scene.objects.link(vol)
            scene.objects.active = vol
            bpy.ops.object.game_property_new(type='FLOAT', name='fog_volume')
            vol.game.properties['fog_volume'].value = 3.0
            bpy.ops.object.game_property_new(type='STRING', name='fog_shape')
            vol.game.properties['fog_shape'].value = forma
    if preset == 'medium_fumaca':
        w.vfog_volumes_only = True
        w.vfog_density = 0.22
        w.vfog_noise_amount = 0.0
        w.vfog_edge = 0.45
        w.vfog_ambient = 0.8
        chaminé = malha('chamine', lambda bm: bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False,
                                                                  segments=20, diameter1=1.4, diameter2=1.0,
                                                                  depth=7.0), (0, 8, 3.5))
        chaminé.data.materials.append(principled('tijolo_chamine', (0.18, 0.09, 0.05, 1.0)))
        scene.objects.link(chaminé)
        vol = malha('fumaca', lambda bm: bmesh.ops.create_cube(bm, size=2.0), (0, 8, 10.0))
        vol.scale = (1.5, 1.5, 5.0)
        vol.color = (0.72, 0.74, 0.76, 1.0)
        vol.game.physics_type = 'NO_COLLISION'
        vol.hide_render = True
        scene.objects.link(vol)
        scene.objects.active = vol
        bpy.ops.object.game_property_new(type='FLOAT', name='fog_volume')
        vol.game.properties['fog_volume'].value = 3.0
        bpy.ops.object.game_property_new(type='STRING', name='fog_shape')
        vol.game.properties['fog_shape'].value = 'sphere'
        bpy.ops.object.game_property_new(type='FLOAT', name='fog_smoke')
        vol.game.properties['fog_smoke'].value = 1.5
    if preset == 'medium_abre':
        # Neblina baixa e densa; a bola com fog_push vai e volta abrindo um buraco.
        w.vfog_density = 0.25
        w.vfog_falloff = 2.0
        bola = malha('bola_push', lambda bm: bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=12,
                                                                       diameter=1.0), (0, 6, 1.0))
        bola.data.materials.append(principled('bola_amarela', (1.0, 0.8, 0.1, 1.0)))
        bola.game.physics_type = 'NO_COLLISION'
        scene.objects.link(bola)
        scene.objects.active = bola
        bpy.ops.object.game_property_new(type='FLOAT', name='fog_push')
        bola.game.properties['fog_push'].value = 3.5
    if preset == 'medium_fogo':
        w.vfog_volumes_only = True
        w.vfog_density = 0.28
        w.vfog_noise_amount = 0.0
        w.vfog_ambient = 0.0
        fogo = malha('fogueira', lambda bm: bmesh.ops.create_cube(bm, size=2.0), (0, 8, 2.0))
        fogo.scale = (1.4, 1.4, 2.4)
        fogo.game.physics_type = 'NO_COLLISION'
        fogo.hide_render = True
        scene.objects.link(fogo)
        scene.objects.active = fogo
        bpy.ops.object.game_property_new(type='FLOAT', name='fog_volume')
        fogo.game.properties['fog_volume'].value = 3.0
        bpy.ops.object.game_property_new(type='STRING', name='fog_shape')
        fogo.game.properties['fog_shape'].value = 'sphere'
        bpy.ops.object.game_property_new(type='FLOAT', name='fog_smoke')
        fogo.game.properties['fog_smoke'].value = 1.2
        bpy.ops.object.game_property_new(type='FLOAT', name='fog_fire')
        fogo.game.properties['fog_fire'].value = 0.9
    if preset == 'medium_explosao':
        w.vfog_volumes_only = True
        w.vfog_density = 0.32
        w.vfog_noise_amount = 0.0
        w.vfog_ambient = 0.0
        explosao = malha('explosao', lambda bm: bmesh.ops.create_cube(bm, size=2.0), (0, 8, 2.2))
        explosao.scale = (0.35, 0.35, 0.35)
        explosao.game.physics_type = 'NO_COLLISION'
        explosao.hide_render = True
        scene.objects.link(explosao)
        scene.objects.active = explosao
        bpy.ops.object.game_property_new(type='FLOAT', name='fog_volume')
        explosao.game.properties['fog_volume'].value = 3.5
        bpy.ops.object.game_property_new(type='STRING', name='fog_shape')
        explosao.game.properties['fog_shape'].value = 'sphere'
        bpy.ops.object.game_property_new(type='FLOAT', name='fog_fire')
        explosao.game.properties['fog_fire'].value = 1.0

    txt =bpy.data.texts.new('medir_fps.py')
    txt.write(SCRIPT)
    scene.objects.active = chao
    bpy.ops.object.game_property_new(type='STRING', name='preset')
    chao.game.properties['preset'].value = preset
    bpy.ops.logic.sensor_add(type='ALWAYS', name='always', object=chao.name)
    sens = chao.game.sensors['always']
    sens.use_pulse_true_level = True
    bpy.ops.logic.controller_add(type='PYTHON', name='medir', object=chao.name)
    ctrl = chao.game.controllers['medir']
    ctrl.mode = 'MODULE'
    ctrl.module = 'medir_fps.tick'
    sens.link(ctrl)

    if preset == 'medium_script':
        # Exercise the World Property path too, independently of setWeather().
        bpy.ops.logic.sensor_add(type='DELAY', name='vfog_property_delay', object=chao.name)
        sens = chao.game.sensors['vfog_property_delay']
        sens.delay = 2
        bpy.ops.logic.controller_add(type='LOGIC_AND', name='vfog_property', object=chao.name)
        ctrl = chao.game.controllers['vfog_property']
        bpy.ops.logic.actuator_add(type='PROPERTY', name='vfog_density_property', object=chao.name)
        act = chao.game.actuators['vfog_density_property']
        act.actuator_mode = 'GLOBAL_PROPERTY'
        act.mode = 'ASSIGN'
        act.property = 'vfog_density'
        act.value = '0.11'
        sens.link(ctrl)
        act.link(ctrl)

    out = os.path.join(pasta, 'vfog_%s.range' % preset)
    bpy.ops.wm.save_as_mainfile(filepath=out, check_existing=False)
    print('CENA VFOG salva', out)


for p in ('off', 'low', 'medium', 'high', 'medium_volume', 'low_dia', 'medium_dia', 'medium_noshaft', 'medium_script',
          'medium_sol', 'medium_vento', 'medium_manha', 'medium_volumes', 'medium_fumaca',
          'medium_abre', 'medium_fogo', 'medium_explosao'):
    gerar(p)
