# Volumetric Fog item 8: camada (Layer) e Reach Clouds. Terreno 80x80 com relevo, camera alta.
# Variantes: altura (neblina exponencial antiga), camada, camada_nuvens (camada + nuvens volumetricas).
# FPS medio de ~10 s (descarta 3 s) vai para VFOG_FPS_LOG; foto em VFOG_SHOT; o jogo fecha.
#   AnastacioEngine.exe -b --factory-startup --python criar_cena_vfog_camada.py -- pasta_saida
import bpy
import bmesh
import os
import sys
from mathutils import Vector, noise

argv = sys.argv[sys.argv.index('--') + 1:]
pasta = argv[0]

for _p in ('vfog_use_layer', 'vfog_use_reach_clouds'):
    _ok = False
    try:
        _ok = _p in bpy.types.World.bl_rna.properties['weather_settings'].fixed_type.properties
    except Exception:
        pass
    if not _ok:
        print('ERRO VFOG CAMADA: propriedade weather_settings.%s ausente neste binario; recompile o editor.' % _p)
        sys.exit(2)

SCRIPT = (
    "import bge, os, time\n"
    "\n"
    "\n"
    "def tick(cont):\n"
    "    own = cont.owner\n"
    "    agora = time.perf_counter()\n"
    "    if 'inicio' not in own:\n"
    "        own['inicio'] = agora\n"
    "        return\n"
    "    if agora - own['inicio'] < 3.0:\n"
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


def altura(x, y):
    h = 0.0
    amp, freq = 1.0, 0.025
    for _ in range(4):
        h += amp * noise.noise(Vector((x * freq, y * freq, 0.37)))
        amp *= 0.5
        freq *= 2.0
    # noise ~[-1,1] -> 0..1, realcado: vales 0-2 m, picos 8-12 m
    t = max(0.0, min(1.0, (h + 0.9) / 1.8))
    return 12.0 * t * t


def terreno():
    mesh = bpy.data.meshes.new('terreno')
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=80, y_segments=80, size=40)
    for v in bm.verts:
        v.co.z = altura(v.co.x, v.co.y)
    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()
    for p in mesh.polygons:
        p.use_smooth = True
    obj = bpy.data.objects.new('terreno', mesh)
    return obj


def gerar(preset):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_GAME'
    gs = scene.game_settings
    gs.use_shading_nodes = True
    gs.use_frame_rate = False
    gs.fps = 2000
    gs.vsync = 'OFF'
    gs.resolution_x = 1280
    gs.resolution_y = 720

    chao = terreno()
    chao.data.materials.append(principled('grama', (0.18, 0.42, 0.12, 1.0)))
    scene.objects.link(chao)

    cx, cy = 10.0, 6.0
    cz = altura(cx, cy)
    cubo_mesh = bpy.data.meshes.new('cubo')
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=3.0)
    bm.to_mesh(cubo_mesh)
    bm.free()
    cubo = bpy.data.objects.new('cubo', cubo_mesh)
    cubo.location = (cx, cy, cz + 1.0)
    cubo.data.materials.append(principled('escuro', (0.05, 0.05, 0.06, 1.0)))
    scene.objects.link(cubo)

    la = bpy.data.lamps.new('sun', 'SUN')
    la.color = (1.0, 0.95, 0.85)
    la.energy = 1.2
    la.use_shadow = True
    la.shadow_buffer_size = 2048
    la.shadow_frustum_size = 90.0
    la.shadow_buffer_clip_start = 1.0
    la.shadow_buffer_clip_end = 150.0
    sun = bpy.data.objects.new('sun', la)
    sun.location = (-30, 30, 50)
    sun.rotation_euler = (Vector((0, 0, 0)) - sun.location).to_track_quat('-Z', 'Y').to_euler()
    scene.objects.link(sun)

    cam = bpy.data.objects.new('camera', bpy.data.cameras.new('camera'))
    cam.data.type = 'PERSP'
    cam.data.lens = 20
    cam.data.clip_end = 500.0
    cam.location = (0, -45, 30)
    cam.rotation_euler = (Vector((0, 0, 2)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    scene.objects.link(cam)
    scene.camera = cam

    world = bpy.data.worlds.new('World')
    scene.world = world
    world.mist_settings.use_mist = False
    world.horizon_color = (0.75, 0.85, 0.95)
    world.zenith_color = (0.35, 0.55, 0.9)
    w = world.weather_settings
    w.use_clouds = False
    w.use_sky_layers = False
    w.use_volumetric_clouds = preset == 'camada_nuvens'
    w.use_volumetric_fog = True
    w.vfog_quality = 'MEDIUM'
    w.vfog_resolution = 'HALF'
    w.vfog_color = (0.95, 0.95, 0.95)
    w.vfog_density = 0.35
    w.vfog_base = 3.0
    w.vfog_falloff = 1.5
    w.vfog_distance = 200.0
    w.vfog_noise_amount = 0.4
    w.vfog_ambient = 0.6
    w.vfog_use_layer = preset != 'altura'
    w.vfog_use_reach_clouds = preset == 'camada_nuvens'
    if preset == 'camada_nuvens':
        w.vcloud_altitude = 120.0

    txt = bpy.data.texts.new('medir_fps.py')
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

    out = os.path.join(pasta, 'vfog_camada_%s.range' % preset)
    bpy.ops.wm.save_as_mainfile(filepath=out, check_existing=False)
    print('CENA VFOG CAMADA salva', out)


os.makedirs(pasta, exist_ok=True)
for p in ('altura', 'camada', 'camada_nuvens'):
    gerar(p)
