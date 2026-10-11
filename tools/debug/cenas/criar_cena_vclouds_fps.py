# Mede FPS do Volumetric Clouds por preset de qualidade: gera a mesma cena em 4 arquivos
# (off, low, medium, high) com FPS destravado e sem vsync. Cada uma grava o FPS medio de
# ~10 s (descartando os 3 primeiros) no arquivo da variavel de ambiente VCLOUD_FPS_LOG e fecha.
#   AnastacioEngine.exe -b --factory-startup --python criar_cena_vclouds_fps.py -- pasta_saida
import bpy
import bmesh
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
    "    if 'inicio' not in own:\n"
    "        own['inicio'] = agora\n"
    "        own['frames'] = 0\n"
    "        return\n"
    "    dt = agora - own['inicio']\n"
    "    if dt < 3.0:\n"
    "        return\n"
    "    if 'medida' not in own:\n"
    "        own['medida'] = agora\n"
    "        own['frames'] = 0\n"
    "        return\n"
    "    own['frames'] += 1\n"
    "    janela = agora - own['medida']\n"
    "    if janela >= 10.0:\n"
    "        fps = own['frames'] / janela\n"
    "        caminho = os.environ.get('VCLOUD_FPS_LOG')\n"
    "        if caminho:\n"
    "            with open(caminho, 'a') as f:\n"
    "                f.write('%s fps=%.1f ms=%.2f\\n' % (own['preset'], fps, 1000.0 / fps))\n"
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

    terreno = malha('terreno', lambda bm: bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=200), (0, 0, 0))
    terreno.data.materials.append(principled('chao', (0.25, 0.4, 0.15, 1.0)))
    scene.objects.link(terreno)
    monte = malha('monte', lambda bm: bmesh.ops.create_icosphere(bm, subdivisions=2, diameter=25), (0, 0, 10))
    monte.scale = (1.4, 1.4, 0.6)
    monte.data.materials.append(principled('monte', (0.4, 0.35, 0.25, 1.0)))
    scene.objects.link(monte)

    sun_loc = (0, 170, 106)
    sun = bpy.data.objects.new('sun', bpy.data.lamps.new('sun', 'SUN'))
    sun.location = sun_loc
    sun.rotation_euler = (-Vector(sun_loc)).to_track_quat('-Z', 'Y').to_euler()
    scene.objects.link(sun)

    # Camera olhando para o ceu com bastante nuvem na tela: pior caso do raymarch.
    cam = bpy.data.objects.new('camera', bpy.data.cameras.new('camera'))
    cam.data.type = 'PERSP'
    cam.data.lens = 16
    cam.location = (0, -120, 25)
    cam.rotation_euler = (Vector((0, 60, 45)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    scene.objects.link(cam)
    scene.camera = cam

    world = bpy.data.worlds.new('World')
    scene.world = world
    world.mist_settings.use_mist = False
    world.sky_type = 'GRADIENT'
    world.horizon_color = (0.5, 0.65, 0.85)
    world.zenith_color = (0.15, 0.3, 0.65)
    w = world.weather_settings
    w.use_clouds = False
    w.use_sky_layers = False
    w.use_volumetric_clouds = preset != 'off'
    if preset != 'off':
        w.vcloud_quality = preset.upper()
    w.vcloud_shadow_enable = True
    w.vcloud_shadow_strength = 0.5
    w.vcloud_coverage = 0.5
    w.vcloud_speed = 0.5
    w.vcloud_altitude = 80.0
    w.vcloud_thickness = 40.0
    w.vcloud_density = 1.0

    txt = bpy.data.texts.new('medir_fps.py')
    txt.write(SCRIPT)
    scene.objects.active = terreno
    bpy.ops.object.game_property_new(type='STRING', name='preset')
    terreno.game.properties['preset'].value = preset
    bpy.ops.logic.sensor_add(type='ALWAYS', name='always', object=terreno.name)
    sens = terreno.game.sensors['always']
    sens.use_pulse_true_level = True
    bpy.ops.logic.controller_add(type='PYTHON', name='medir', object=terreno.name)
    ctrl = terreno.game.controllers['medir']
    ctrl.mode = 'MODULE'
    ctrl.module = 'medir_fps.tick'
    sens.link(ctrl)

    out = os.path.join(pasta, 'vclouds_fps_%s.range' % preset)
    bpy.ops.wm.save_as_mainfile(filepath=out, check_existing=False)
    print('CENA VCLOUDS FPS salva', out)


for p in ('off', 'low', 'medium', 'high'):
    gerar(p)
