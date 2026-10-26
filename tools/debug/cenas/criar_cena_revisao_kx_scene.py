"""Gera/inspeciona cena isolada para revisar contratos de KX_Scene.

AnastacioEngine.exe -b --factory-startup --python este_script -- <pasta> [inspect]
AnastacioRuntime.exe --server <pasta>/revisao_kx_scene.range
SCENE_REVIEW_CASE: basic (padrao), callback_mutation ou explode_sequence.
Os dois ultimos exercitam entradas que podem encerrar o processo nativo.
"""
import json
import os
import sys

import bpy
from mathutils import Vector

args = sys.argv[sys.argv.index('--') + 1:]
out_dir = os.path.abspath(args[0])
os.makedirs(out_dir, exist_ok=True)
scene_path = os.path.join(out_dir, 'revisao_kx_scene.range')

if len(args) > 1 and args[1] == 'inspect':
    bpy.ops.wm.open_mainfile(filepath=scene_path)
    scene = bpy.context.scene
    probe = scene.objects['ReviewProbe']
    controller = probe.game.controllers['ReviewPython']
    data = {
        'scene': scene.name,
        'camera': scene.camera.name,
        'engine': scene.render.engine,
        'objects': [obj.name for obj in scene.objects],
        'template_inactive': bpy.data.objects['ReviewTemplate'].layers[19],
        'mode': controller.mode,
        'module': controller.module,
        'sensor_links': [sensor.name for sensor in probe.game.sensors
                         if controller in list(sensor.controllers)],
        'tick_defined': 'def tick(cont):' in bpy.data.texts['scene_review.py'].as_string(),
    }
    with open(os.path.join(out_dir, 'inspection.json'), 'w') as output:
        json.dump(data, output, indent=2)
else:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_GAME'
    scene.game_settings.use_frame_rate = True
    scene.render.resolution_x = 320
    scene.render.resolution_y = 240
    world = bpy.data.worlds.new('ReviewWorld')
    scene.world = world
    world.mist_settings.use_mist = False
    camera = bpy.data.objects.new('ReviewCamera', bpy.data.cameras.new('ReviewCamera'))
    scene.objects.link(camera)
    camera.location = (0, -8, 5)
    camera.rotation_euler = (Vector((0, 0, 0)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera.data.lens = 16
    scene.camera = camera
    sun = bpy.data.objects.new('ReviewSun', bpy.data.lamps.new('ReviewSun', 'SUN'))
    scene.objects.link(sun)
    sun.rotation_euler = (0.4, -0.3, -0.5)
    template = bpy.data.objects.new('ReviewTemplate', None)
    scene.objects.link(template)
    template.layers = [False] * 19 + [True]
    probe = bpy.data.objects.new('ReviewProbe', None)
    scene.objects.link(probe)
    scene.objects.active = probe
    text = bpy.data.texts.new('scene_review.py')
    text.write('''import json
import os
import traceback
import Range

FRAME = 0
RESULTS = {}
MODE = os.environ.get('SCENE_REVIEW_CASE', 'basic')
PATH = os.path.join(Range.logic.expandPath('//'), 'result_' + MODE + '.json')

def save():
    with open(PATH, 'w') as output:
        json.dump(RESULTS, output, indent=2)

def clear_callbacks():
    RESULTS['callback_entered'] = True
    save()
    Range.logic.getCurrentScene().thread_logic_1.clear()

def next_callback():
    RESULTS['next_callback'] = True
    save()

class BrokenSequence:
    def __len__(self):
        return 1
    def __getitem__(self, index):
        raise RuntimeError('review deliberate sequence failure')

def tick(cont):
    global FRAME
    FRAME += 1
    scene = Range.logic.getCurrentScene()
    try:
        RESULTS.setdefault('ticks', []).append({'frame': FRAME, 'gravity': list(scene.gravity)})
        if FRAME == 1:
            RESULTS['started'] = True
            RESULTS['mode'] = MODE
            RESULTS['gravity_initial'] = list(scene.gravity)
            save()
            if MODE == 'callback_mutation':
                scene.thread_logic_1 = [clear_callbacks, next_callback]
            elif MODE == 'explode_sequence':
                RESULTS['explode_entered'] = True
                save()
                try:
                    scene.explode((0, 0, 0), ignore=BrokenSequence())
                except Exception as error:
                    RESULTS['explode_exception'] = type(error).__name__ + ': ' + str(error)
        if MODE == 'basic' and FRAME == 3:
            scene.gravity = (0, 0, -3.0)
            RESULTS['gravity_immediately_after_set'] = list(scene.gravity)
            template = scene.objectsInactive['ReviewTemplate']
            template.name = 'RenamedTemplate'
            RESULTS['template_current_name'] = template.name
            for name in ['RenamedTemplate', 'ReviewTemplate']:
                try:
                    clone = scene.addObject(name)
                    RESULTS['add_' + name] = clone.name
                    clone.endObject()
                except Exception as error:
                    RESULTS['add_' + name] = type(error).__name__ + ': ' + str(error)
        if FRAME >= 4:
            RESULTS['gravity_next_tick'] = list(scene.gravity)
        if FRAME >= 8:
            RESULTS['completed'] = True
            RESULTS['frames'] = FRAME
            save()
            Range.logic.endGame()
    except Exception:
        RESULTS['unexpected_exception'] = traceback.format_exc()
        save()
        Range.logic.endGame()
''')
    bpy.ops.logic.sensor_add(type='ALWAYS', name='ReviewAlways', object=probe.name)
    bpy.ops.logic.controller_add(type='PYTHON', name='ReviewPython', object=probe.name)
    sensor = probe.game.sensors['ReviewAlways']
    sensor.use_pulse_true_level = True
    controller = probe.game.controllers['ReviewPython']
    controller.mode = 'MODULE'
    controller.module = 'scene_review.tick'
    controller.link(sensor=sensor)
    bpy.ops.wm.save_as_mainfile(filepath=scene_path)
    print('SCENE_REVIEW_SAVED', scene_path)
