"""Gera e inspeciona cena isolada para revisar o nucleo de KX_GameObject.

AnastacioEngine.exe -b --factory-startup --python este_script -- <pasta> [inspect]
GAMEOBJECT_REVIEW_CASE=basic|culling|lod_self|lod_control
AnastacioRuntime.exe --server <pasta>/revisao_gameobject.range
lod_self exercita uma possivel liberacao prematura e pode encerrar o player.
"""
import json
import os
import sys

import bpy
from mathutils import Vector


out_dir = os.path.abspath(sys.argv[sys.argv.index('--') + 1])
os.makedirs(out_dir, exist_ok=True)
scene_path = os.path.join(out_dir, 'revisao_gameobject.range')
inspect = sys.argv[-1] == 'inspect'

if inspect:
    bpy.ops.wm.open_mainfile(filepath=scene_path)
    scene = bpy.context.scene
    data = {'camera': scene.camera.name,
            'activity_culling': scene.game_settings.use_activity_culling,
            'camera_activity_culling': scene.camera.data.use_object_activity_culling,
            'objects': {}, 'controllers': []}
    for obj in scene.objects:
        data['objects'][obj.name] = {
            'materials': [mat.name for mat in obj.data.materials] if obj.type == 'MESH' else [],
            'inactive': obj.layers[19],
            'physics': obj.game.physics_type,
            'physics_culling': obj.game.activity_culling.use_physics,
            'logic_culling': obj.game.activity_culling.use_logic,
            'lod_levels': len(obj.lod_levels),
        }
        for controller in obj.game.controllers:
            data['controllers'].append({
                'object': obj.name, 'module': controller.module, 'mode': controller.mode,
                'sensors': [sensor.name for sensor in obj.game.sensors
                            if controller in list(sensor.controllers)],
                'function_present': 'def ' + controller.module.split('.')[-1] + '(' in
                                    bpy.data.texts[controller.module.split('.')[0] + '.py'].as_string(),
            })
    with open(os.path.join(out_dir, 'inspection.json'), 'w') as output:
        json.dump(data, output, indent=2)
else:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_GAME'
    scene.game_settings.use_frame_rate = True
    scene.game_settings.use_activity_culling = True
    scene.render.resolution_x = 320
    scene.render.resolution_y = 240
    scene.world = bpy.data.worlds.new('ObjectReviewWorld')
    scene.world.mist_settings.use_mist = False
    camera = bpy.data.objects.new('ReviewCamera', bpy.data.cameras.new('ReviewCamera'))
    scene.objects.link(camera)
    camera.location = (0, -8, 5)
    camera.rotation_euler = (-camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera.data.lens = 16
    camera.data.use_object_activity_culling = True
    scene.camera = camera
    sun = bpy.data.objects.new('ReviewSun', bpy.data.lamps.new('ReviewSun', 'SUN'))
    scene.objects.link(sun)
    sun.rotation_euler = (0.4, -0.3, -0.5)

    def cube(name, location, color):
        bpy.ops.mesh.primitive_cube_add(radius=0.25, location=location)
        obj = scene.objects.active
        obj.name = name
        obj.game.physics_type = 'STATIC'
        material = bpy.data.materials.new(name + 'Material')
        material.diffuse_color = color
        obj.data.materials.append(material)
        return obj

    def logic(obj, function):
        scene.objects.active = obj
        bpy.ops.logic.sensor_add(type='ALWAYS', name='ReviewAlways', object=obj.name)
        bpy.ops.logic.controller_add(type='PYTHON', name='ReviewPython', object=obj.name)
        sensor = obj.game.sensors['ReviewAlways']
        sensor.use_pulse_true_level = True
        controller = obj.game.controllers['ReviewPython']
        controller.mode = 'MODULE'
        controller.module = 'object_review.' + function
        controller.link(sensor=sensor)

    target = cube('PhysicsOnly', (-1, 0, 0), (0.8, 0.1, 0.1))
    target.game.activity_culling.use_physics = True
    target.game.activity_culling.physics_radius = 15
    logic(target, 'count')
    control = cube('LogicOnly', (1, 0, 0), (0.1, 0.8, 0.1))
    control.game.activity_culling.use_logic = True
    control.game.activity_culling.logic_radius = 15
    logic(control, 'count')
    template = cube('ReviewTemplate', (0, 4, 0), (0.1, 0.2, 0.8))
    template.layers = [False] * 19 + [True]
    lod = cube('ReviewLod', (0, 2, 0), (0.8, 0.6, 0.1))
    bpy.ops.object.lod_add()
    bpy.ops.object.lod_add()
    lod.lod_levels[1].object = lod
    lod.lod_levels[1].distance = 1000
    for name in ('ReviewParent', 'ReviewChild', 'ReviewProbe'):
        scene.objects.link(bpy.data.objects.new(name, None))
    logic(scene.objects['ReviewProbe'], 'tick')
    text = bpy.data.texts.new('object_review.py')
    text.write('''import json
import math
import os
import traceback
import Range

FRAME = 0
COUNTS = {}
RESULTS = {}
MODE = os.environ.get('GAMEOBJECT_REVIEW_CASE', 'basic')
PATH = os.path.join(Range.logic.expandPath('//'), 'result_' + MODE + '.json')

def save():
    with open(PATH, 'w') as output:
        json.dump(RESULTS, output, indent=2)

def count(cont):
    name = cont.owner.name
    COUNTS[name] = COUNTS.get(name, 0) + 1

def callback(*args):
    pass

def tick(cont):
    global FRAME
    FRAME += 1
    scene = Range.logic.getCurrentScene()
    try:
        if FRAME == 1:
            RESULTS['mode'] = MODE
            RESULTS['started'] = True
            save()
            if MODE == 'basic':
                template = scene.objectsInactive['ReviewTemplate']
                template.setVehicleMaxTorque(321)
                template.setVehicleMaxRPM(7654)
                template.setVehicleGearRatios([3.0, 2.0, 1.0])
                template.collisionCallbacks.append(callback)
                first = scene.addObject(template)
                second = scene.addObject(template)
                RESULTS['replica_vehicle'] = {
                    'template_torque': template.getVehicleMaxTorque(),
                    'replica_torque': first.getVehicleMaxTorque(),
                    'template_rpm': template.getVehicleMaxRPM(),
                    'replica_rpm': first.getVehicleMaxRPM(),
                    'template_gears': list(template.getVehicleGearRatios()),
                    'replica_gears': list(first.getVehicleGearRatios()),
                }
                RESULTS['callbacks_same_list'] = first.collisionCallbacks is second.collisionCallbacks
                first.collisionCallbacks.clear()
                RESULTS['callback_counts_after_first_clear'] = [len(obj.collisionCallbacks)
                                                                for obj in (template, first, second)]
                parent = scene.objects['ReviewParent']
                child = scene.objects['ReviewChild']
                child.setParent(parent)
                child.worldPosition = (2, 3, 4)
                RESULTS['normal_parent_position'] = list(child.localPosition)
                parent.localScale = (0, 1, 1)
                child.worldPosition = (2, 3, 4)
                RESULTS['zero_axis_parent_local_position'] = [x if math.isfinite(x) else str(x)
                                                              for x in child.localPosition]
                RESULTS['zero_axis_position_finite'] = all(math.isfinite(x) for x in child.localPosition)
                child.worldScale = (2, 3, 4)
                RESULTS['zero_axis_parent_local_scale'] = [x if math.isfinite(x) else str(x)
                                                           for x in child.localScale]
                RESULTS['zero_axis_scale_finite'] = all(math.isfinite(x) for x in child.localScale)
                if os.environ.get('GAMEOBJECT_REVIEW_VERIFY') == '1':
                    assert RESULTS['zero_axis_position_finite'] and RESULTS['zero_axis_scale_finite']
                    assert list(child.localPosition) == [2, 3, 4]
                    assert list(child.localScale) == [1, 1, 1]
                    for axis in range(3):
                        scale = [1, 1, 1]
                        scale[axis] = 0
                        parent.localScale = scale
                        child.worldPosition = (5, 6, 7)
                        child.worldScale = (5, 6, 7)
                        assert list(child.localPosition) == [2, 3, 4]
                        assert list(child.localScale) == [1, 1, 1]
                    child.removeParent()
                    child.setParent(parent)
                    assert child.parent is None
                    RESULTS['singular_transforms_preserved'] = True
                parent.localScale = (1, 1, 1)
                child.localPosition = (2, 3, 4)
                child.localScale = (1, 1, 1)
                save()
            elif MODE in ('lod_self', 'lod_control'):
                obj = scene.objects['ReviewLod']
                manager = obj.lodManager
                RESULTS['lod_levels_before'] = len(manager.levels)
                if MODE == 'lod_self':
                    RESULTS['self_assignment_entered'] = True
                    save()
                    obj.lodManager = manager
                    RESULTS['self_assignment_returned'] = True
                    save()
                RESULTS['lod_levels_after'] = len(manager.levels)
                if os.environ.get('GAMEOBJECT_REVIEW_VERIFY') == '1':
                    assert RESULTS['lod_levels_after'] == RESULTS['lod_levels_before']
                    assert obj.lodManager is manager
                save()
        if MODE == 'culling':
            objects = [scene.objects[name] for name in ('PhysicsOnly', 'LogicOnly')]
            if FRAME == 10:
                for index, obj in enumerate(objects):
                    obj.worldPosition = (100, index * 2, 0)
            if FRAME == 20:
                objects[0].physicsCulling = False
                objects[1].logicCulling = False
            if FRAME == 30:
                for index, obj in enumerate(objects):
                    obj.worldPosition = (index * 2, 0, 0)
            if FRAME in (9, 15, 21, 29, 40):
                RESULTS.setdefault('samples', []).append({
                    'frame': FRAME, 'counts': dict(COUNTS),
                    'states': [obj.state for obj in objects],
                    'physics_flags': [obj.physicsCulling for obj in objects],
                    'logic_flags': [obj.logicCulling for obj in objects],
                })
                save()
        if FRAME >= 45:
            if MODE == 'culling' and os.environ.get('GAMEOBJECT_REVIEW_VERIFY') == '1':
                assert all(scene.objects[name].state == 1 and COUNTS[name] > 20
                           for name in ('PhysicsOnly', 'LogicOnly'))
                RESULTS['culling_logic_resumed'] = True
            RESULTS['completed'] = True
            RESULTS['frames'] = FRAME
            save()
            Range.logic.endGame()
    except Exception:
        RESULTS['exception'] = traceback.format_exc()
        save()
        Range.logic.endGame()
''')
    bpy.ops.wm.save_as_mainfile(filepath=scene_path, check_existing=False)
    print('GAMEOBJECT_REVIEW_SAVED', scene_path)
