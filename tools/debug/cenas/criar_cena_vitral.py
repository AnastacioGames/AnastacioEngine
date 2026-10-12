"""Colored shadows (stained glass) scene. Usage:
editor -b --factory-startup --python this.py -- out.range [mode]
mode: sun (default), spot, csm (legacy materials, Sun with cascades), nodes_off (Colored Shadows
unchecked, old black shadow), legacy (Blender Internal materials instead of nodes).
A Sun or Spot shines through 3 glass panes (red, green, blue), a checker "stained glass" and an
opaque cube for comparison, in a thin Volumetric Fog with Dust so the beams show the glass color.
Appearance is judged by the user in the real game.
"""
import bpy
import sys
import os
from mathutils import Vector

args = sys.argv[sys.argv.index('--') + 1:]
destination = os.path.abspath(args[0])
mode = args[1] if len(args) > 1 else 'sun'
nodes = mode not in ('legacy', 'csm')
colored = mode != 'nodes_off'

scene = bpy.context.scene
for ob in list(scene.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.use_shading_nodes = nodes
scene.game_settings.resolution_x = 1280
scene.game_settings.resolution_y = 720
world = bpy.data.worlds.new('Vitral World')
world.horizon_color = (0.02, 0.02, 0.03)
world.ambient_color = (0.03, 0.03, 0.04)
scene.world = world
# SSGI on so the colored light bounces onto the walls around
scene['ae_ssgi_use'] = os.environ.get('VITRAL_SSGI', '1') == '1'
scene['ae_ssgi_strength'] = 1.0
weather = world.weather_settings
weather.use_volumetric_fog = os.environ.get('VITRAL_FOG', '1') == '1'
weather.vfog_quality = 'HIGH'
weather.vfog_density = 0.05
weather.vfog_use_sun_shafts = True
weather.vfog_use_lamps = True
weather.vfog_use_shafts = True
weather.vfog_dust = float(os.environ.get('VITRAL_DUST', '0.5'))


def node_material(name, rgba, glass=False, checker=None):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    tree = mat.node_tree
    for node in list(tree.nodes):
        tree.nodes.remove(node)
    shader = tree.nodes.new('ShaderNodeBsdfPrincipled')
    shader.inputs['Base Color'].default_value = rgba
    shader.inputs['Roughness'].default_value = 0.3
    out = tree.nodes.new('ShaderNodeOutputMaterial')
    if checker:
        tex = tree.nodes.new('ShaderNodeTexChecker')
        tex.inputs['Color1'].default_value = checker[0]
        tex.inputs['Color2'].default_value = checker[1]
        tex.inputs['Scale'].default_value = 4.0
        tree.links.new(tex.outputs['Color'], shader.inputs['Base Color'])
    if glass:
        transparent = tree.nodes.new('ShaderNodeBsdfTransparent')
        mix = tree.nodes.new('ShaderNodeMixShader')
        mix.inputs['Fac'].default_value = 0.45
        tree.links.new(shader.outputs[0], mix.inputs[1])
        tree.links.new(transparent.outputs[0], mix.inputs[2])
        tree.links.new(mix.outputs[0], out.inputs['Surface'])
    else:
        tree.links.new(shader.outputs[0], out.inputs['Surface'])
    return mat


def legacy_material(name, rgba, glass=False):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = rgba[:3]
    if glass:
        mat.use_transparency = True
        mat.alpha = 0.5
    return mat


def material(name, rgba, glass=False, checker=None):
    mat = node_material(name, rgba, glass, checker) if nodes else legacy_material(name, rgba, glass)
    if glass:
        mat.use_transparency = True
        mat.alpha = 0.5
        mat.game_settings.alpha_blend = 'ALPHA'
        mat.game_settings.use_backface_culling = False
        mat.use_cast_shadows = True
        mat.use_colored_shadows = colored
        mat.colored_shadow_glow = 1.5
    return mat


def box(name, loc, scale, mat):
    bpy.ops.mesh.primitive_cube_add(radius=1, location=loc)
    ob = scene.objects.active
    ob.name = name
    ob.scale = scale
    ob.data.materials.append(mat)
    ob.game.physics_type = 'STATIC'
    return ob


floor = material('Floor', (0.7, 0.7, 0.7, 1))
box('Floor', (0, 0, -0.05), (12, 12, 0.05), floor)
box('BackWall', (0, 6, 3), (12, 0.1, 3), floor)
box('OpaqueCube', (-6, 0, 1), (0.6, 0.6, 1), material('Opaque', (0.4, 0.4, 0.4, 1)))

panes = (('Red', (1.0, 0.05, 0.02, 1)), ('Green', (0.05, 1.0, 0.1, 1)), ('Blue', (0.05, 0.2, 1.0, 1)))
for i, (name, rgba) in enumerate(panes):
    box('Glass' + name, (-3 + i * 2.2, 0, 1.6), (0.9, 0.04, 1.4), material('Glass' + name, rgba, glass=True))
if nodes:
    box('StainedGlass', (4.2, 0, 1.6), (0.9, 0.04, 1.4),
        material('StainedGlass', (1, 1, 1, 1), glass=True,
                 checker=((1.0, 0.75, 0.05, 1), (0.6, 0.05, 0.9, 1))))

if mode == 'spot':
    lamp = bpy.data.lamps.new('Spot', 'SPOT')
    lamp.spot_size = 1.4
    lamp.energy = 1.0
    lamp.distance = 40
    lamp_ob = bpy.data.objects.new('Spot', lamp)
    lamp_ob.location = (9, -6, 9)
else:
    lamp = bpy.data.lamps.new('Sun', 'SUN')
    lamp.energy = 1.5
    lamp.use_csm_shadow = mode == 'csm'
    lamp.shadow_frustum_size = 20
    lamp_ob = bpy.data.objects.new('Sun', lamp)
    lamp_ob.location = (9, -6, 9)
scene.objects.link(lamp_ob)
lamp.use_shadow = True
lamp.shadow_buffer_size = 2048
lamp_ob.rotation_euler = (Vector((-1, 2, 0)) - lamp_ob.location).to_track_quat('-Z', 'Y').to_euler()

cam = bpy.data.objects.new('Camera', bpy.data.cameras.new('Camera'))
scene.objects.link(cam)
cam.location = (0, -12, 7)
cam.rotation_euler = (Vector((0, 2, 0.5)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
cam.data.lens = 24
scene.camera = cam

# Measurement (VITRAL_BENCH=file): no frame cap, average frame rate after a warm-up appended to the file.
bench = os.environ.get('VITRAL_BENCH')
if bench:
    scene.game_settings.use_frame_rate = False
    scene.game_settings.vsync = 'OFF'
    text = bpy.data.texts.new('vitral_bench.py')
    text.write('''import Range, time, json
s = Range.logic.globalDict.setdefault('vitral_bench', {'t0': time.perf_counter(), 'fps': []})
t = time.perf_counter() - s['t0']
if t > 3.0:
    s['fps'].append(Range.logic.getAverageFrameRate())
if t > 10.0:
    with open(%r, 'a') as f:
        f.write(json.dumps({'label': %r, 'fps': sum(s['fps']) / max(len(s['fps']), 1)}) + chr(10))
    Range.logic.endGame()
''' % (bench, os.environ.get('VITRAL_LABEL', mode)))
    bpy.context.scene.objects.active = cam
    bpy.ops.logic.sensor_add(type='ALWAYS', name='Bench', object=cam.name)
    bpy.ops.logic.controller_add(type='PYTHON', name='Bench', object=cam.name)
    cam.game.sensors['Bench'].use_pulse_true_level = True
    cam.game.controllers['Bench'].text = text
    cam.game.sensors['Bench'].link(cam.game.controllers['Bench'])

bpy.ops.wm.save_as_mainfile(filepath=destination, check_existing=False)
print('Vitral scene saved:', destination, mode)
