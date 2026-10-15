# -*- coding: utf-8 -*-
"""Cena manual: três presets e um NPC permanente. Recebe pasta após --."""
import math
import os
import sys

import bpy
from mathutils import Vector

root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, os.path.join(root, 'source', 'release', 'scripts', 'addons'))
import anastacio_ragdoll as addon

dest = os.path.abspath(sys.argv[sys.argv.index('--') + 1])
os.makedirs(dest, exist_ok=True)
addon.register()
scene = bpy.context.scene
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.resolution_x, scene.game_settings.resolution_y = 1100, 700
scene.game_settings.show_fullscreen = False
scene.game_settings.use_frame_rate = True


def material(name, color):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = color
    return mat


floor_mat = material('Chao cinza', (0.2, 0.23, 0.25))
bpy.ops.mesh.primitive_cube_add(location=(0, 0, -0.25))
floor = bpy.context.object
floor.name, floor.scale = 'Chao', (14, 10, 0.25)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
floor.game.physics_type = 'STATIC'
floor.data.materials.append(floor_mat)

for index, (name, preset, color, automatic, mode) in enumerate([
        ('Duro', 'HARD', (0.9, 0.25, 0.15), True, 'FREE'),
        ('Equilibrado', 'BALANCED', (0.15, 0.65, 0.25), True, 'FREE'),
        ('Leve', 'LIGHT', (0.15, 0.4, 0.95), True, 'FREE'),
        ('NPC permanente', 'BALANCED', (0.65, 0.25, 0.7), False, 'FREE'),
        ('Ancora', 'BALANCED', (0.95, 0.65, 0.15), True, 'ANCHOR')]):
    x = (index - 2) * 4
    mat = material(name, color)
    if mode == 'FREE':
        bpy.ops.mesh.primitive_cube_add(location=(x, 0, 0.95))
        controller = bpy.context.object
        controller.name, controller.scale = name + ' - Colisor', (0.45, 0.4, 0.9)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        controller.game.physics_type = 'RIGID_BODY'
        controller.game.use_collision_bounds = True
        controller.game.collision_bounds_type = 'BOX'
        controller.game.mass = 70
        controller.hide_render = True
        controller.draw_type = 'WIRE'
    else:
        controller = bpy.data.objects.new('Assento de demonstracao', None)
        scene.objects.link(controller)
        controller.location = (x, 0, 0.1)
    scene.update()
    bpy.ops.object.armature_add(location=(x, 0, 0.1))
    rig = bpy.context.object
    rig.name = name
    rig.game.physics_type = 'NO_COLLISION'
    bpy.ops.object.mode_set(mode='EDIT')
    root_bone = rig.data.edit_bones[0]
    root_bone.name, root_bone.head, root_bone.tail = 'Tronco', (0, 0, 0.9), (0, 0, 1.4)
    bones = [('Cabeca', (0, 0, 1.4), (0, 0, 1.8), 'Tronco')]
    for sign, side in [(-1, 'E'), (1, 'D')]:
        bones += [('Braco' + side, (sign * 0.12, 0, 1.35), (sign * 0.55, 0, 1.3), 'Tronco'),
                  ('Antebraco' + side, (sign * 0.55, 0, 1.3), (sign * 0.95, 0.05, 1.1), 'Braco' + side),
                  ('Coxa' + side, (sign * 0.14, 0, 0.9), (sign * 0.17, 0, 0.5), 'Tronco'),
                  ('Perna' + side, (sign * 0.17, 0, 0.5), (sign * 0.17, 0, 0.05), 'Coxa' + side)]
    for bone_name, head, tail, parent in bones:
        bone = rig.data.edit_bones.new(bone_name)
        bone.head, bone.tail, bone.parent = head, tail, rig.data.edit_bones[parent]
    bpy.ops.object.mode_set(mode='OBJECT')
    world = rig.matrix_world.copy()
    rig.parent, rig.matrix_world = controller, world
    scene.update()
    addon.sync_bones(rig)
    settings = rig.anastacio_ragdoll
    settings.preset = preset
    addon.apply_preset(rig)
    settings.bones['Tronco'].width, settings.bones['Tronco'].depth = 0.35, 0.22
    settings.bones['Cabeca'].width = settings.bones['Cabeca'].depth = 0.22
    settings.recovery_mode, settings.auto_recover = mode, automatic
    settings.recovery_delay = 4.0
    settings.controller = controller if mode == 'FREE' else None
    settings.anchor = controller if mode == 'ANCHOR' else None
    addon.generate(bpy.context, rig, runtime=True)
    for obj in addon.owned(rig):
        if obj.type == 'MESH':
            # Só na demonstração: os corpos representam o personagem visível.
            obj.hide_render = False
            obj.data.materials.append(mat)
    bpy.ops.object.text_add(location=(x - 1, -1.5, 0.03), rotation=(math.pi / 2, 0, 0))
    label = bpy.context.object
    label.name, label.data.body, label.data.size = name + ' - Legenda', name, 0.3
    label.data.materials.append(mat)

driver = r'''
import Range
from mathutils import Vector

def tick(cont):
    keyboard, events = Range.logic.keyboard.events, Range.events
    for obj in cont.owner.scene.objects:
        for comp in obj.components:
            if getattr(comp, 'is_valid', False) and getattr(comp, 'anastacio_ragdoll', False) and comp._ready and not comp.active:
                for item in comp.entries:
                    item['body'].worldTransform = comp.world_transform(obj) * item['channel'].pose_matrix * item['offset']
    if keyboard[events.VKEY] == Range.logic.KX_INPUT_JUST_ACTIVATED:
        for obj in cont.owner.scene.objects:
            for comp in obj.components:
                if getattr(comp, 'is_valid', False) and getattr(comp, 'anastacio_ragdoll', False) and not comp.active and comp.activate():
                    for item in comp.entries:
                        body = item['body']
                        body.applyImpulse(comp.world_transform(body).translation,
                                          Vector((0, -1.5, 0.3)) * body.mass, False)
    if keyboard[events.RKEY] == Range.logic.KX_INPUT_JUST_ACTIVATED:
        for obj in cont.owner.scene.objects:
            for comp in obj.components:
                if getattr(comp, 'is_valid', False) and getattr(comp, 'anastacio_ragdoll', False):
                    comp.recover()
'''
if os.environ.get('ANASTACIO_RAGDOLL_DEMO_SMOKE'):
    driver += r'''
import json, traceback
manual_tick = tick
frames = 0

def tick(cont):
    global frames
    frames += 1
    try:
        manual_tick(cont)
        comps = [comp for obj in cont.owner.scene.objects for comp in obj.components
                 if getattr(comp, 'anastacio_ragdoll', False)]
        if frames == 10:
            assert len(comps) == 5
            for comp in comps:
                assert comp.activate(), comp.error
                for item in comp.entries:
                    body = item['body']
                    body.applyImpulse(comp.world_transform(body).translation,
                                      Vector((0, -1.5, 0.3)) * body.mass, False)
        if frames == 370:
            for comp in comps:
                assert comp.is_valid, comp.error
                assert comp.active == (comp.object.name == 'NPC permanente'), comp.object.name + ': ' + comp.blocked_reason
            result = {'ok': True, 'frames': frames, 'rigs': len(comps), 'bodies': sum(len(c.entries) for c in comps)}
            with open(Range.logic.expandPath('//demo-smoke-result.json'), 'w') as output:
                json.dump(result, output)
            Range.logic.endGame()
    except Exception:
        with open(Range.logic.expandPath('//demo-smoke-result.json'), 'w') as output:
            json.dump({'ok': False, 'frames': frames, 'error': traceback.format_exc()}, output)
        Range.logic.endGame()
'''
text = bpy.data.texts.new('demo_ragdoll_input.py')
text.write(driver)
owner = bpy.data.objects.new('Demo - V cair - R recuperar', None)
scene.objects.link(owner)
scene.objects.active = owner
bpy.ops.logic.sensor_add(type='ALWAYS', object=owner.name)
sensor = owner.game.sensors[-1]
sensor.use_pulse_true_level = True
bpy.ops.logic.controller_add(type='PYTHON', object=owner.name)
controller = owner.game.controllers[-1]
controller.mode, controller.module = 'MODULE', 'demo_ragdoll_input.tick'
sensor.link(controller)
bpy.ops.object.camera_add(location=(1, -16, 11))
scene.camera = bpy.context.object
scene.camera.data.lens = 30
scene.camera.rotation_euler = (Vector((0, 0, 1)) - scene.camera.location).to_track_quat('-Z', 'Y').to_euler()
bpy.ops.object.lamp_add(type='SUN', location=(0, 0, 10))
bpy.context.object.rotation_euler = (0.4, 0.3, -0.4)
scene.world.mist_settings.use_mist = False
for obj in scene.objects:
    obj.select = False
rig = bpy.data.objects['Equilibrado']
rig.select = True
scene.objects.active = rig
for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        area.spaces.active.region_3d.view_perspective = 'CAMERA'
    elif area.type == 'PROPERTIES':
        area.spaces.active.context = 'PHYSICS'
path = os.path.join(dest, 'demo-smoke.range' if os.environ.get('ANASTACIO_RAGDOLL_DEMO_SMOKE') else 'demo-ragdoll.range')
bpy.ops.wm.save_as_mainfile(filepath=path)
print('DEMO_RAGDOLL_SAVED', path)
