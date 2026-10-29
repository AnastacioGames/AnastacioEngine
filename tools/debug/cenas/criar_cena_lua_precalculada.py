"""Generate independent procedural/cached moon fixtures; never edits a user's scene.
AnastacioEngine -b --factory-startup --python this.py -- output_dir
Runtime writes JSON to ANASTACIO_MOON_RESULT and exits; omit it for manual viewing.
"""
import bpy
import json
import math
import os
import sys
from mathutils import Vector

destination = os.path.abspath(sys.argv[sys.argv.index('--') + 1])
os.makedirs(destination, exist_ok=True)
scene = bpy.context.scene
for obj in list(scene.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
scene.render.engine = 'BLENDER_GAME'
scene.render.resolution_x = 1280
scene.render.resolution_y = 720
scene.render.resolution_percentage = 100
scene.game_settings.use_frame_rate = False
scene.game_settings.use_shading_nodes = True
scene.game_settings.vsync = 'OFF'
world = bpy.data.worlds.new('Moon comparison')
assert not world.use_moon_precomputed
scene.world = world
world.use_nodes = False
world.sky_type = 'PROCEDURAL'
world.use_sky_moon = True
world.use_sky_stars = False
world.use_sky_aurora = False
world.moon_size = 0.1  # deliberately large to expose finite texture resolution
world.moon_brightness = 0.8
world.mist_settings.use_mist = False

moon_direction = Vector((0.0, 1.0, 0.5)).normalized()
lamp = bpy.data.lamps.new('WorldSun', 'SUN')
sun = bpy.data.objects.new('WorldSun', lamp)
scene.objects.link(sun)
sun.rotation_euler = (-moon_direction).to_track_quat('Z', 'Y').to_euler()
scene.world_sun_set = sun
camera = bpy.data.objects.new('Camera', bpy.data.cameras.new('Camera'))
scene.objects.link(camera)
camera.rotation_euler = moon_direction.to_track_quat('-Z', 'Y').to_euler()
camera.data.lens = 50
scene.camera = camera

probe = bpy.data.texts.new('moon_probe.py')
probe.from_string('''import bge, json, os, time
samples = []
start = None
previous = None
def tick(controller):
    global start, previous
    output = os.environ.get('ANASTACIO_MOON_RESULT')
    if not output:
        return
    now = time.perf_counter()
    if start is None:
        start = previous = now
        return
    if now - start > 2.0:
        samples.append((now - previous) * 1000.0)
    previous = now
    if now - start > 8.0:
        values = sorted(samples)
        with open(output, 'w') as stream:
            json.dump({'ticks': len(values), 'median_tick_ms': values[len(values)//2],
                       'mean_tick_ms': sum(values)/len(values), 'elapsed': now-start}, stream)
        bge.logic.endGame()
''')
scene.objects.active = camera
camera.select = True
bpy.ops.logic.sensor_add(type='ALWAYS', object=camera.name)
sensor = camera.game.sensors[-1]
sensor.use_pulse_true_level = True
bpy.ops.logic.controller_add(type='PYTHON', object=camera.name)
controller = camera.game.controllers[-1]
controller.mode = 'MODULE'
controller.module = 'moon_probe.tick'
controller.link(sensor=sensor)

manifest = []
for sky in ('PROCEDURAL', 'ATMOSPHERIC'):
    world.sky_type = sky
    for enabled in (False, True):
        world.use_moon_precomputed = enabled
        filename = 'moon_{}_{}.range'.format(sky.lower(), 'cached' if enabled else 'procedural')
        path = os.path.join(destination, filename)
        bpy.ops.wm.save_as_mainfile(filepath=path)
        manifest.append({'file': filename, 'cached': enabled, 'sky': sky})
with open(os.path.join(destination, 'manifest.json'), 'w') as stream:
    json.dump(manifest, stream, indent=2)
