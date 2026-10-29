"""Monta um tableau do splash com assets do Rolima, sem salvar no jogo original.

AnastacioEngine -b D:/ProjetoRolimaRacer/RolimaRacer.range --python este_script -- saida.range
"""
import bpy
import json
import math
import os
import sys
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

output = os.path.abspath(sys.argv[sys.argv.index('--') + 1])
source_path = bpy.data.filepath
assert os.path.normcase(output) != os.path.normcase(source_path)
# Resolva caminhos enquanto o arquivo original ainda e a base dos // relativos.
bpy.ops.file.make_paths_absolute()
track = bpy.data.scenes['Pista_1']
scene = bpy.data.scenes.new('Splash_060_Rolima')
bpy.context.screen.scene = scene
scene.render.engine = 'BLENDER_GAME'
scene.layers = [True] + [False] * 19
scene.world = track.world.copy()
scene.world.name = 'Splash_Tempestade'


def clear_logic(obj):
    scene.objects.active = obj
    for collection, op, arg in (
            (obj.game.sensors, bpy.ops.logic.sensor_remove, 'sensor'),
            (obj.game.controllers, bpy.ops.logic.controller_remove, 'controller'),
            (obj.game.actuators, bpy.ops.logic.actuator_remove, 'actuator')):
        for item in list(collection):
            op(**{arg: item.name, 'object': obj.name})
    while len(obj.game.components):
        obj.game.components.remove(obj.game.components[0])
    obj.game.physics_type = 'NO_COLLISION'
    obj.game.use_actor = False


def clone_objects(objects, prefix, transform=None):
    mapping = {}
    for src in objects:
        obj = src.copy()
        obj.name = prefix + src.name
        scene.objects.link(obj)
        obj.layers = scene.layers
        mapping[src] = obj
    for src, obj in mapping.items():
        matrix = src.matrix_world.copy()
        obj.parent = mapping.get(src.parent)
        obj.matrix_world = (transform * matrix) if transform is not None else matrix
        for modifier in obj.modifiers:
            if hasattr(modifier, 'object') and modifier.object in mapping:
                modifier.object = mapping[modifier.object]
        for constraint in list(obj.constraints):
            # O tableau nao depende da logica/constraints da corrida.
            obj.constraints.remove(constraint)
        clear_logic(obj)
    scene.update()
    return mapping


# Somente a geometria visivel da pista; sem HUD, loaders e controladores.
track_objects = [o for o in track.objects if o.layers[0] and
                 o.type in ('MESH', 'LAMP') and not o.hide_render]
environment = clone_objects(track_objects, 'Cenario_')
scene.update()
road = environment[bpy.data.objects['Road_Parte1.004']]
origin = road.matrix_world.inverted() * Vector((0, 0, 100))
direction = road.matrix_world.inverted().to_3x3() * Vector((0, 0, -1))
surface = BVHTree.FromPolygons([v.co for v in road.data.vertices],
                               [p.vertices for p in road.data.polygons])
point, normal, index, distance = surface.ray_cast(origin, direction)
assert point is not None, 'Ponto de composicao fora do asfalto'
ground_z = (road.matrix_world * point).z
base = Vector((0, 0, ground_z))
placement = Matrix.Translation(base + Vector((0.7, 0, 0.27)))
car_group = bpy.data.groups['Group_Rolima_Car']
car_sources = [o for o in car_group.objects if o.type in ('MESH', 'EMPTY')]
car = clone_objects(car_sources, 'Hero_Carro_', placement)
for src, obj in car.items():
    if obj.use_gpu_particles and obj.name.startswith('Hero_Carro_Wheel_'):
        obj.gpu_particles.velocity = (0.0, -1.2, 0.1)
        obj.gpu_particles.emission_direction = (0.0, -1.0, -0.1)
    if 'Collider' in src.name or 'collider' in src.name or src.name == 'solid_neon':
        obj.hide_render = True

pilot_sources = [o for o in bpy.data.groups['GroupFabio'].objects
                 if o.type == 'ARMATURE' or o.name.startswith('BodyGroupFabio')]
pilot = clone_objects(pilot_sources, 'Hero_Piloto_', placement)
arm = next(o for o in pilot.values() if o.type == 'ARMATURE')
arm.animation_data_create()
arm.animation_data.action = bpy.data.actions['CARRO_Main_drive_position']
for obj in pilot.values():
    obj.hide_render = False
scene.frame_set(1)
scene.update()

world = scene.world
world.horizon_color = (0.055, 0.075, 0.12)
world.zenith_color = (0.025, 0.04, 0.08)
world.mist_settings.use_mist = False
w = world.weather_settings
w.use_rain = True
w.rain_intensity = 0.55
w.rain_darken = 0.22
w.rain_streak_width = 0.4
w.rain_wind = 0.35
w.use_rain_droplets = True
w.use_rain_ripple = True
w.use_rain_splash = True
w.use_rain_puddles = True
w.use_rain_puddle_ssr = True
w.rain_puddle_amount = 0.65
w.rain_puddle_reflection = 0.75
w.use_rain_aura = True
w.use_rain_lightning = True
w.use_rain_lightning_side = True
w.rain_lightning_rate = 5.0
w.use_rain_sound = False
w.use_rain_lightning_sound = False
w.use_lens_flare = False

for obj in environment.values():
    if obj.type == 'LAMP':
        obj.data = obj.data.copy()
        obj.data.energy = 0.55
        obj.data.color = (0.5, 0.65, 1.0)


def light(name, position, color, energy):
    data = bpy.data.lamps.new(name, 'POINT')
    data.color = color
    data.energy = energy
    data.distance = 18
    obj = bpy.data.objects.new(name, data)
    scene.objects.link(obj)
    obj.location = base + Vector(position)


light('Splash_Luz_quente', (-3, -1, 3), (1.0, 0.52, 0.19), 2.2)
light('Splash_Recorte_azul', (2, 4, 4), (0.3, 0.55, 1.0), 2.8)
camera_data = bpy.data.cameras.new('Splash_Camera')
camera = bpy.data.objects.new('Splash_Camera', camera_data)
scene.objects.link(camera)
camera.location = base + Vector((-2.1, -3.1, 1.25))
target = base + Vector((-0.35, 1.0, 0.9))
camera.rotation_euler = (target-camera.location).to_track_quat('-Z', 'Y').to_euler()
camera_data.lens = 30
camera_data.clip_start = 0.05
camera_data.clip_end = 1800
camera_data.gpu_dof.focus_distance = (base + Vector((0.7, 0, 0.9)) - camera.location).length
camera_data.game_fx.use_vignette = True
camera_data.game_fx.vignette_strength = 0.22
camera_data.game_fx.use_dof = True
camera_data.game_fx.dof_quality = 'HIGH'
camera_data.game_fx.dof_blur = 2.5
camera_data.game_fx.focus_range = 2.5
scene.camera = camera
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from splash_rolima_impacto import setup as setup_impact
setup_impact(scene)
fx = scene.scenefx_settings
fx.quality_preset = 'HIGH'
fx.use_ssr = True
fx.use_ssao = True
fx.use_bloom = True
fx.use_tonemap = True
fx.use_fxaa = True
gs = scene.game_settings
gs.resolution_x = 1672
gs.resolution_y = 941
gs.show_fullscreen = False
gs.borderless_window = False
gs.use_desktop = False
gs.show_debug_properties = False
gs.show_debug_mode = False
gs.show_framerate_profile = False
gs.use_activity_culling = False
gs.use_occlusion_culling = False
gs.use_frame_rate = True
gs.exit_key = 'ESC'
from splash_rolima_arte import setup as setup_art
setup_art(scene)
scene.render.resolution_x = 1672
scene.render.resolution_y = 941
scene.render.resolution_percentage = 100

runtime_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'splash_rolima_runtime.py')
text = bpy.data.texts.new('splash_rolima_runtime.py')
with open(runtime_path, encoding='utf8') as f:
    text.write(f.read())
shader = bpy.data.texts.new('splash_rolima_speed.glsl')
with open(os.path.join(os.path.dirname(runtime_path), 'splash_rolima_speed.glsl'), encoding='utf8') as f:
    shader.write(f.read())
shader_data = bpy.data.texts.new('splash_rolima_speed_data.py')
shader_data.write('SHADER = ' + repr(shader.as_string()) + '\n')
scene.objects.active = camera
bpy.ops.logic.sensor_add(type='ALWAYS', object=camera.name)
bpy.ops.logic.controller_add(type='PYTHON', object=camera.name)
sensor = camera.game.sensors[-1]
sensor.use_pulse_true_level = True
controller = camera.game.controllers[-1]
controller.mode = 'MODULE'
controller.module = 'splash_rolima_runtime.tick'
sensor.link(controller)

# Remova cenas e templates alheios ao tableau na copia, inclusive seus loaders.
for other in list(bpy.data.scenes):
    if other != scene:
        bpy.data.scenes.remove(other)
for group in list(bpy.data.groups):
    bpy.data.groups.remove(group)
keep = set(scene.objects)
for obj in list(bpy.data.objects):
    if obj not in keep:
        bpy.data.objects.remove(obj, do_unlink=True)
scene.update()
for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        area.spaces.active.region_3d.view_perspective = 'CAMERA'
bpy.ops.wm.save_as_mainfile(filepath=output)
report = {'source': source_path, 'output': output, 'scene': scene.name,
          'ground_z': ground_z, 'objects': len(scene.objects),
          'pilot': arm.name, 'action': arm.animation_data.action.name,
          'car': [o.name for o in car.values()], 'camera': list(camera.location),
          'textures_missing': [i.filepath for i in bpy.data.images if i.source == 'FILE'
                               and not i.packed_file and i.filepath and not os.path.isfile(bpy.path.abspath(i.filepath))]}
with open(os.path.join(os.path.dirname(output), 'creation.json'), 'w') as f:
    json.dump(report, f, indent=2)
print('SPLASH_CREATED', output)
