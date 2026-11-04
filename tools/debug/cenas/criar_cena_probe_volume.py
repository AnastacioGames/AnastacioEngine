"""Probe Volume GI test scene: a closed room with a window, a sun, a red and a green wall, scattered
static boxes, one dynamic box and an Empty-box "probe_volume". Principled materials (Shading Nodes)
so the grid's diffuse shows. Saves one .range per quality (off/low/med/high) in the folder given
after "--". The game saves shot_<file>.png next to the .range at 8 s and quits itself after 10 s.

  AnastacioEngine.exe -b -P criar_cena_probe_volume.py -- <out_dir>
"""
import bpy
import os
import random
import sys

out_dir = sys.argv[sys.argv.index('--') + 1]
os.makedirs(out_dir, exist_ok=True)

QUIT = '''import bge, time
own = bge.logic.getCurrentController().owner
if 't0' not in own:
    own['t0'] = time.perf_counter()
t = time.perf_counter() - own['t0']
if t > 8.0 and 'shot' not in own:
    own['shot'] = True
    bge.render.makeScreenshot('//shot_' + bge.logic.getCurrentScene().name + '.png')
if t > 10.0:
    bge.logic.endGame()
'''


MATS = {}


def material(name, color):
    if name not in MATS:
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        nt = mat.node_tree
        nt.nodes.clear()
        p = nt.nodes.new('ShaderNodeBsdfPrincipled')
        p.inputs['Base Color'].default_value = color + (1,)
        p.inputs['Roughness'].default_value = 0.8
        out = nt.nodes.new('ShaderNodeOutputMaterial')
        nt.links.new(p.outputs[0], out.inputs['Surface'])
        MATS[name] = mat
    return MATS[name]


def box(name, loc, size, dynamic=False, mat=('Gray', (0.6, 0.6, 0.6))):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    ob = bpy.context.object
    ob.name = name
    ob.scale = size
    ob.data.materials.append(material(*mat))
    if dynamic:
        ob.game.physics_type = 'RIGID_BODY'
    return ob


def build(quality):
    bpy.ops.wm.read_homefile(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_GAME'
    scene.name = 'probe_volume_%s' % (quality.lower() if quality else 'off')
    gs = scene.game_settings
    gs.use_shading_nodes = True
    gs.resolution_x, gs.resolution_y = 960, 540
    gs.vsync = 'OFF'
    gs.use_frame_rate = False
    MATS.clear()
    w = bpy.data.worlds.new('Sky')
    scene.world = w
    w.horizon_color = (0.5, 0.65, 0.9)
    w.zenith_color = (0.2, 0.35, 0.8)
    w.light_settings.use_environment_light = True
    w.light_settings.environment_energy = 1.0
    random.seed(1)

    box('Floor', (0, 0, -0.1), (10, 10, 0.1))
    box('Ceiling', (0, 0, 4.1), (10, 10, 0.1))
    box('WallN', (0, 10, 2), (10, 0.1, 2))
    box('WallE', (10, 0, 2), (0.1, 10, 2), mat=('Green', (0.1, 0.7, 0.1)))
    box('WallW', (-10, 0, 2), (0.1, 10, 2), mat=('Red', (0.8, 0.1, 0.1)))
    # South wall with a window gap in the middle.
    box('WallS1', (-6, -10, 2), (4, 0.1, 2))
    box('WallS2', (6, -10, 2), (4, 0.1, 2))
    for i in range(150):
        box('Prop%d' % i, (random.uniform(-9, 9), random.uniform(-9, 9), 0.4), (0.4, 0.4, 0.4))
    box('Dynamic', (0, 0, 3), (0.5, 0.5, 0.5), dynamic=True)

    bpy.ops.object.lamp_add(type='SUN', location=(0, -20, 10), rotation=(1.0, 0, 0))
    # Shadows: only the window lets the sun in, the rest of the room lives on the bounce.
    bpy.context.object.data.shadow_method = 'RAY_SHADOW'
    # Toward the red west wall, so its bounce on the boxes shows.
    bpy.ops.object.camera_add(location=(6, -8, 2), rotation=(1.45, 0, 0.9))
    cam = bpy.context.object
    scene.camera = cam

    bpy.ops.object.add(type='EMPTY', location=(0, 0, 2))
    vol = bpy.context.object
    vol.name = 'ProbeVolume'
    vol.empty_draw_type = 'CUBE'
    # The whole room: the probes on the floor, ceiling and walls are pushed out by the engine (F3).
    vol.scale = (10.0, 10.0, 2.0)
    if quality is not None:
        bpy.ops.object.game_property_new(type='FLOAT', name='probe_volume')
        vol.game.properties['probe_volume'].value = 0.0
        bpy.ops.object.game_property_new(type='STRING', name='probe_volume_quality')
        vol.game.properties['probe_volume_quality'].value = quality
        if os.environ.get('PV_BOUNCE'):
            # Gain of each bounce (engine default 0.5).
            bpy.ops.object.game_property_new(type='FLOAT', name='probe_volume_bounce')
            vol.game.properties['probe_volume_bounce'].value = float(os.environ['PV_BOUNCE'])

    # Quit timer on the camera.
    text = bpy.data.texts.new('quit.py')
    text.write(QUIT)
    scene.objects.active = cam
    bpy.ops.logic.sensor_add(type='ALWAYS', object=cam.name)
    cam.game.sensors[-1].use_pulse_true_level = True
    bpy.ops.logic.controller_add(type='PYTHON', object=cam.name)
    cam.game.controllers[-1].text = text
    cam.game.controllers[-1].link(sensor=cam.game.sensors[-1])

    name = 'probe_volume_%s.range' % (quality.lower() if quality else 'off')
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out_dir, name), check_existing=False)


for q in (None, 'Low', 'Medium', 'High'):
    build(q)
