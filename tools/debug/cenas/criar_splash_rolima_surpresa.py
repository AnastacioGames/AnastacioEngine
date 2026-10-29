"""Outra direcao de arte, sobre uma copia da cena aprovada; nao altera a anterior.

AnastacioEngine -b <cena-aprovada.range> --python este_script -- <saida.range>
"""
import bpy
import json
import math
import os
import sys
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from bpy_extras.object_utils import world_to_camera_view

output = os.path.abspath(sys.argv[sys.argv.index('--') + 1])
assert os.path.normcase(output) != os.path.normcase(bpy.data.filepath)
scene = bpy.context.scene
scene.name = 'Splash_060_Tempestade_Eletrica'
camera = scene.camera
ground = -1.4496893882751465
# Enquadramento da proposta Claude B, escolhido pelo usuario; referencia lida
# sem salvar no arquivo do Claude.
camera.location = (-1.0, -2.1, ground + 0.42)
camera.rotation_euler = (1.6772230863571167, 0.0694194957613945, -0.34921014308929443)
camera.data.lens = 22
camera.data.game_fx.use_dof = False
camera.data.game_fx.vignette_strength = 0.20
camera.data.gpu_dof.focus_distance = 3.5

# Iluminacao fotografica: recorte frio e preenchimento quente do rosto.
world = scene.world
world.use_sky_atmospheric = False
world.use_sky_real = False
world.horizon_color = (0.075, 0.095, 0.19)
world.zenith_color = (0.012, 0.012, 0.045)
w = world.weather_settings
w.use_rain = True
w.rain_intensity = 0.65
w.rain_darken = 0.1
w.rain_streak_width = 0.24
w.rain_wind = 0.55
w.rain_puddle_amount = 0.72
w.rain_puddle_reflection = 0.85
w.rain_ripple_intensity = 0.13
w.rain_splash_intensity = 0.35
w.use_sky_layers = True
w.sky_layer_coverage = 0.8
w.use_volumetric_clouds = False
w.vcloud_coverage = 0.8
w.vcloud_altitude = 80
w.vcloud_thickness = 45
w.vcloud_density = 0.8
w.vcloud_color = (0.18, 0.22, 0.38)
w.vcloud_quality = 'MEDIUM'
w.use_volumetric_fog = True
w.vfog_density = 0.006
w.vfog_base = ground
w.vfog_falloff = 2
w.vfog_distance = 75
w.vfog_color = (0.22, 0.32, 0.52)
w.vfog_quality = 'MEDIUM'
w.vfog_resolution = 'HALF'
w.vfog_use_lamps = True
w.vfog_max_lights = 3
w.vfog_sun_intensity = 0.0
w.vfog_use_sun_shafts = False
w.vfog_use_time_of_day = False
w.vfog_morning_boost = 0.0
sun = scene.objects['Cenario_Sun_pista1']
sun.data.energy = 0.5
sun.data.color = (0.40, 0.48, 0.85)
warm = scene.objects['Splash_Luz_quente']
warm.location = (-1.5, -1.2, ground + 2.5)
warm.data.energy = 1.8
warm.data.color = (1.0, 0.58, 0.28)
blue = scene.objects['Splash_Recorte_azul']
blue.location = (-1.2, -1.0, ground + 2.8)
blue.data.energy = 3.4
blue.data.color = (0.13, 0.42, 1.0)
blue.location = (1.6, 3.2, ground + 2.6)

# Spray de agua real, sem depender da simulacao do veiculo parado.
for obj in scene.objects:
    if obj.name.startswith('Hero_Carro_Wheel_') and obj.use_gpu_particles:
        p = obj.gpu_particles
        p.particle_look = 'DEFAULT'
        p.particle_count = 140
        p.lifetime = 0.65
        p.velocity = (0.0, -2.4, 0.15)
        p.emission_direction = (0, -1, 0.05)
        p.emission_angle = 25
        p.velocity_randomness = 0.65
        p.gravity = (0, 0, -2.5)
        p.drag = 0.4
        p.size = 0.025
        p.end_size = 0.065
        p.color = (0.55, 0.75, 1.0, 0.65)
        p.end_color = (0.45, 0.65, 1.0, 0.0)
        p.blend_mode = 'ALPHA'

# Desloca o impacto para o fundo da NOVA camera.
road = scene.objects['Cenario_Road_Parte1.004']
bvh = BVHTree.FromPolygons([v.co for v in road.data.vertices], [p.vertices for p in road.data.polygons])
point, _, _, _ = bvh.ray_cast(road.matrix_world.inverted() * Vector((-1.2, 6.0, 100)),
                             road.matrix_world.inverted().to_3x3() * Vector((0, 0, -1)))
assert point is not None, 'Impacto fora da pista'
impact = road.matrix_world * point + Vector((0, 0, 0.08))
scene.objects['Splash_Impacto_Alvo'].location = impact
emitter = scene.objects['Splash_Raio_Impacto']
emitter.location = impact + Vector((0.0, 0.0, 14))
emitter.lightning.width = 0.85
emitter.lightning.intensity = 0.85
emitter.lightning.color = (0.50, 0.40, 1.0)
bomb = scene.objects['Splash_Explosao_Template']
bomb.location = impact
bomb.game.explosive.particle_size = 'SMALL'
bomb.game.explosive.particle_style = 'ELECTRIC'

scene.update()
# O centro da mascara e o ponto de fuga acompanham esta camera.
subject = world_to_camera_view(scene, camera, Vector((0.7, 0.0, ground + 0.95)))
vanish = world_to_camera_view(scene, camera, Vector((0.7, -8.0, ground + 0.4)))
root = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(root, 'splash_rolima_speed.glsl'), encoding='utf8') as f:
    shader = f.read()
shader = shader.replace('vec2(0.82, 0.28)', 'vec2(0.79, 0.45)')
shader = shader.replace('vec2(0.25, 0.36)', 'vec2(0.24, 0.37)')
shader = shader.replace('vec2(0.32, 0.52)', 'vec2(0.27, 0.38)')
impact_uv = world_to_camera_view(scene, camera, impact)
shader = shader.replace('return 1.0 - smoothstep(0.82, 1.12, d);',
    'float bolt = length((uv - vec2(%.6f, %.6f)) / vec2(0.13, 0.48));\n'
    '    return max(1.0 - smoothstep(0.82, 1.12, d), 1.0 - smoothstep(0.7, 1.0, bolt));'
    % (impact_uv.x, impact_uv.y + 0.25))
shader_text = bpy.data.texts.new('splash_surpresa_speed.glsl')
shader_text.write(shader)
data = bpy.data.texts.new('splash_surpresa_speed_data.py')
data.write('SHADER = ' + repr(shader) + '\n')
with open(os.path.join(root, 'splash_rolima_runtime.py'), encoding='utf8') as f:
    runtime = f.read()
runtime = runtime.replace('splash_rolima_speed_data', 'splash_surpresa_speed_data')
runtime = runtime.replace("0.10", "0.075")
runtime = runtime.replace("now + 0.12", "now + 0.23")
runtime = runtime.replace("'//captura-splash-060.png'", "'//captura-tempestade-eletrica.png'")
runtime_text = bpy.data.texts.new('splash_surpresa_runtime.py')
runtime_text.write(runtime)
camera.game.controllers[0].module = 'splash_surpresa_runtime.tick'

for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        area.spaces.active.region_3d.view_perspective = 'CAMERA'
bpy.ops.wm.save_as_mainfile(filepath=output)
report = {'scene':scene.name, 'camera':list(camera.location), 'subject_uv':list(subject),
          'vanish_uv':list(vanish), 'impact':list(impact), 'objects':len(scene.objects)}
with open(os.path.join(os.path.dirname(output),'creation.json'),'w') as f:json.dump(report,f,indent=2)
print('SURPRISE_CREATED', output)
