"""Run with RangeEngine -b --python tools/create_web_render_scene.py.

Jogo de teste visual de render avancado no runtime Web (julgamento humano, sem verificador automatico):
sombra de spot (buffer), sol, material com especular, transparencia (alpha blend), nevoa (mist),
ambient occlusion do mundo e textura procedural no chao. As teclas 1..0/Q/W/E/R/T dependem dos filtros
do jogo de smoke, entao aqui o foco e o render 3D. Saida: build-web/bin/web-render.range.
"""
import os
import bpy
from mathutils import Vector
from pathlib import Path

out_dir = Path(__file__).resolve().parents[1] / 'build-web' / 'bin'
out_dir.mkdir(parents=True, exist_ok=True)

# RENDER_OFF=rot,shadow,ao,mist,glsl,alpha (lista) desliga recursos para isolar defeitos do runtime.
OFF = set(filter(None, os.environ.get('RENDER_OFF', '').split(',')))
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.name = 'Render'
scene.render.engine = 'BLENDER_GAME'
gs = scene.game_settings
gs.resolution_x, gs.resolution_y = 960, 540
gs.use_glsl_shadows = True
gs.use_glsl_lights = True
gs.use_glsl_ramps = True
gs.use_glsl_nodes = True
gs.use_glsl_extra_textures = True
gs.use_glsl_color_management = True

world = bpy.data.worlds.new('RenderWorld')
scene.world = world
world.horizon_color = (0.45, 0.6, 0.8)
world.zenith_color = (0.1, 0.2, 0.5)
world.ambient_color = (0.15, 0.15, 0.2)
world.light_settings.use_ambient_occlusion = 'ao' not in OFF
world.mist_settings.use_mist = 'mist' not in OFF
world.mist_settings.start = 8
world.mist_settings.depth = 25

cam = bpy.data.objects.new('RenderCam', bpy.data.cameras.new('RenderCam'))
scene.objects.link(cam)
cam.location = (0, -12, 6)
cam.rotation_euler = (Vector((0, 0, 1)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
scene.camera = cam

sun = bpy.data.objects.new('Sun', bpy.data.lamps.new('Sun', 'SUN'))
scene.objects.link(sun)
sun.rotation_euler = (0.9, 0.2, 0.6)
sun.data.energy = 0.6
spot = bpy.data.objects.new('Spot', bpy.data.lamps.new('Spot', 'SPOT'))
scene.objects.link(spot)
spot.location = (3, -3, 8)
spot.rotation_euler = (Vector((0, 0, 0)) - spot.location).to_track_quat('-Z', 'Y').to_euler()
spot.data.energy = 1.5
spot.data.spot_size = 1.2
spot.data.shadow_method = 'NOSHADOW' if 'shadow' in OFF else 'BUFFER_SHADOW'
spot.data.shadow_buffer_size = 2048


def mat(name, color, spec=0.0, alpha=1.0):
    m = bpy.data.materials.new(name)
    m.diffuse_color = color
    m.specular_intensity = spec
    m.specular_hardness = 80
    if alpha < 1.0 and 'alpha' not in OFF:
        m.use_transparency = True
        m.alpha = alpha
        m.game_settings.alpha_blend = 'ALPHA'
    return m


def add(kind, name, loc, m, **kw):
    getattr(bpy.ops.mesh, 'primitive_%s_add' % kind)(location=loc, **kw)
    o = bpy.context.object
    o.name = name
    o.data.materials.append(m)
    o.game.physics_type = 'NO_COLLISION'
    return o


floor = add('plane', 'Floor', (0, 0, 0), mat('Floor', (0.6, 0.6, 0.6)), radius=40)
add('cube', 'Cube', (-2.5, 0, 1), mat('Red', (0.8, 0.1, 0.1), spec=0.8))
add('uv_sphere', 'Sphere', (0, 0, 1), mat('Metal', (0.8, 0.8, 0.9), spec=1.0))
add('cube', 'Glass', (2.5, -2, 1), mat('Glass', (0.2, 0.7, 0.9), spec=0.5, alpha=0.4))
add('cone', 'Far', (0, 12, 1), mat('Far', (0.1, 0.7, 0.2)))

# textura procedural (xadrez) no chao
img = bpy.data.images.new('Checker', 64, 64)
px = []
for y in range(64):
    for x in range(64):
        v = 0.9 if ((x // 8) + (y // 8)) % 2 == 0 else 0.3
        px += [v, v, v, 1.0]
img.pixels = px
img.pack(as_png=True)
tex = bpy.data.textures.new('Checker', 'IMAGE')
tex.image = img
slot = floor.data.materials[0].texture_slots.add()
slot.texture = tex
slot.texture_coords = 'UV'

script = bpy.data.texts.new('render.py')
script.write('''import Range
cont = Range.logic.getCurrentController()
obj = cont.owner
obj["t"] = obj.get("t", 0) + 1
if obj["t"] == 1:
    print("[render] scene running", flush=True)
if not %s:
    obj.applyRotation((0, 0, 0.01), False)
''' % ('rot' in OFF))
cube = bpy.data.objects['Cube']
bpy.ops.logic.sensor_add(type='ALWAYS', object=cube.name)
s = cube.game.sensors[-1]
s.use_pulse_true_level = True
bpy.ops.logic.controller_add(type='PYTHON', object=cube.name)
c = cube.game.controllers[-1]
c.text = script
s.link(c)

output = out_dir / ('web-render%s.range' % ('-' + '-'.join(sorted(OFF)) if OFF else ''))
bpy.ops.wm.save_as_mainfile(filepath=str(output))
print('[web-render] saved', str(output))
