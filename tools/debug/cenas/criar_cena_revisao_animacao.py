"""Create ANI-01 background regressions; pass an exclusive output folder after --."""
import json
import os
import sys

import bpy
from mathutils import Vector

out_dir = os.path.abspath(sys.argv[sys.argv.index('--') + 1])
os.makedirs(out_dir, exist_ok=True)

GAME = r'''import json, os, time
import Range
STATE = {'rows': [], 'events': [], 'tick': 0}
CASE = %r

def event(obj, arg):
    STATE['events'].append({'tick': STATE['tick'], 'frame': obj.getActionFrame(), 'arg': arg})

def tick(cont):
    try:
        scene = Range.logic.getCurrentScene()
        cube, arm = scene.objects['Animated'], scene.objects['Armature']
        n = STATE['tick']
        if n == 0:
            Range.logic.setLogicTicRate(64)
            Range.logic.setAnimationRate(1000 if CASE != 'slow_rate' else 16)
            Range.logic.setMaxLogicFrame(5)
            cube.playAction('ObjectMotion', 1, 1001)
            arm.playAction('BoneMotion', 1, 1001)
            assert cube.isPlayingAction() and arm.isPlayingAction(), 'Missing test action'
            if CASE == 'half':
                cube.setHalfAnimations(True)
                arm.setHalfAnimations(True)
        STATE['rows'].append({'tick': n, 'real': time.perf_counter(),
                              'logic': Range.logic.getFrameTime(),
                              'frame': cube.getActionFrame(), 'bone_frame': arm.getActionFrame(),
                              'bone_child': list(scene.objects['BoneChild'].worldPosition)})
        if n in (12, 30):
            time.sleep(0.09)
        STATE['tick'] += 1
        if n >= 55:
            finish()
    except Exception as exc:
        STATE['error'] = repr(exc)
        finish()

def finish():
    with open(Range.logic.expandPath('//result_anim_' + CASE + '.json'), 'w') as out:
        json.dump(STATE, out, indent=2)
    Range.logic.endGame()
'''

for case in ('normal', 'restricted', 'half', 'slow_rate'):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_GAME'
    scene.render.fps = 64 if case != 'restricted' else 24
    scene.game_settings.use_fixed_timestep = True
    scene.game_settings.use_restrict_animation_updates = case == 'restricted'
    world = bpy.data.worlds.new('TestWorld')
    world.mist_settings.use_mist = False
    scene.world = world
    bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0))
    cube = bpy.context.object
    cube.name = 'Animated'
    cube.game.physics_type = 'NO_COLLISION'
    mat = bpy.data.materials.new('CubeOrange')
    mat.diffuse_color = (0.8, 0.2, 0.05)
    cube.data.materials.append(mat)
    cube.keyframe_insert('location', frame=1)
    cube.location.x = 10
    cube.keyframe_insert('location', frame=1001)
    action = cube.animation_data.action
    action.name = 'ObjectMotion'
    for curve in action.fcurves:
        for key in curve.keyframe_points:
            key.interpolation = 'LINEAR'
    cube.animation_data_clear()
    cube.location.x = 0
    bpy.ops.object.animation_event_add()
    evt = cube.anim_events[len(cube.anim_events) - 1]
    evt.anim = action
    evt.eventcall = 'anim_review.event'
    # Triggers are dense around both deliberately stalled frames.
    for frame in range(2, 56):
        scene.frame_current = frame
        bpy.ops.object.animation_event_trigger_add(index=len(cube.anim_events) - 1)
        evt.triggers[-1].custom_arg = str(frame)
    scene.frame_current = 1

    bpy.ops.object.armature_add(location=(2, 0, 0))
    arm = bpy.context.object
    arm.name = 'Armature'
    arm.game.physics_type = 'NO_COLLISION'
    arm.data.culling_method = 'NONE'
    bone = arm.pose.bones[0]
    bone.location = (0, 0, 0)
    bone.keyframe_insert('location', frame=1)
    bone.location = (0, 0, 10)
    bone.keyframe_insert('location', frame=1001)
    arm.animation_data.action.name = 'BoneMotion'
    arm.animation_data.action.use_fake_user = True
    for curve in arm.animation_data.action.fcurves:
        for key in curve.keyframe_points:
            key.interpolation = 'LINEAR'
    arm.animation_data_clear()
    bone.location = (0, 0, 0)
    bpy.ops.mesh.primitive_cube_add(location=(2, 0, 1))
    child = bpy.context.object
    child.name = 'BoneChild'
    child.game.physics_type = 'NO_COLLISION'
    child.scale = (0.2, 0.2, 0.2)
    child.parent = arm
    child.parent_type = 'BONE'
    child.parent_bone = bone.name
    child.location = (0, 0, 0)
    child_mat = bpy.data.materials.new('ChildBlue')
    child_mat.diffuse_color = (0.05, 0.2, 0.8)
    child.data.materials.append(child_mat)

    bpy.ops.object.lamp_add(type='SUN', location=(0, 0, 5))
    bpy.context.object.rotation_euler = (0.4, -0.5, 0.2)
    bpy.ops.object.camera_add(location=(6, -10, 6))
    camera = bpy.context.object
    camera.rotation_euler = (Vector((1, 0, 1)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera.data.lens = 16
    scene.camera = camera
    text = bpy.data.texts.new('anim_review.py')
    text.write(GAME % case)
    scene.objects.active = camera
    bpy.ops.logic.sensor_add(type='ALWAYS', object=camera.name)
    bpy.ops.logic.controller_add(type='PYTHON', object=camera.name)
    sensor = camera.game.sensors[-1]
    sensor.use_pulse_true_level = True
    controller = camera.game.controllers[-1]
    controller.mode = 'MODULE'
    controller.module = 'anim_review.tick'
    sensor.link(controller)
    path = os.path.join(out_dir, 'anim_' + case + '.range')
    bpy.ops.wm.save_as_mainfile(filepath=path)
    # Reopen and inspect the serialized scene and logic wiring.
    bpy.ops.wm.open_mainfile(filepath=path)
    restored = bpy.context.scene
    ctrl = restored.camera.game.controllers[-1]
    assert ctrl.module == 'anim_review.tick'
    assert restored.objects['BoneChild'].parent_bone
    assert bpy.data.actions.get('BoneMotion') is not None
    assert len(restored.objects['Animated'].anim_events[-1].triggers) > 1
    compile(bpy.data.texts['anim_review.py'].as_string(), 'anim_review.py', 'exec')
    with open(os.path.join(out_dir, 'inspection_' + case + '.json'), 'w') as out:
        json.dump({'camera': restored.camera.name, 'module': ctrl.module,
                   'objects': [obj.name for obj in restored.objects],
                   'fixed': restored.game_settings.use_fixed_timestep,
                   'restricted': restored.game_settings.use_restrict_animation_updates}, out, indent=2)
print('ANI_SCENES_CREATED_AND_REOPENED')
