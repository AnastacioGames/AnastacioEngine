# -*- coding: utf-8 -*-
"""Gera teste do componente comum. Recebe pasta de evidência após --."""
import json
import math
import os
import sys

import bpy
from mathutils import Matrix

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
scene.game_settings.resolution_x, scene.game_settings.resolution_y = 800, 600
scene.game_settings.use_frame_rate = True
scene.game_settings.show_fullscreen = False
checks = []


def check(value, message):
    assert value, message
    checks.append(message)


def cube(name, location, scale, physics):
    bpy.ops.mesh.primitive_cube_add(location=location)
    obj = bpy.context.object
    obj.name, obj.scale = name, scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.game.physics_type = physics
    obj.game.use_collision_bounds = True
    obj.game.collision_bounds_type = 'BOX'
    material = bpy.data.materials.new(name)
    material.diffuse_color = (0.25, 0.4, 0.6)
    obj.data.materials.append(material)
    return obj


floor = cube('Floor', (0, 0, -0.25), (30, 30, 0.25), 'STATIC')
obstacle = cube('Obstacle', (50, 0, 1), (0.6, 0.6, 1), 'STATIC')
velocity_vehicle = cube('VelocityVehicle', (-8, -5, 1), (0.5, 1, 0.5), 'RIGID_BODY')
velocity_vehicle.game.mass = 1000
configs = [('Anchor', 'ANCHOR', False, -8), ('AnchorAuto', 'ANCHOR', True, -4),
           ('Free', 'FREE', False, 0), ('FreeAuto', 'FREE', True, 4),
           ('NpcPermanent', 'FREE', False, 8)]
for name, mode, automatic, x in configs:
    if mode == 'FREE':
        parent = cube(name + 'Controller', (x, 0, 0.85), (0.35, 0.35, 0.75), 'RIGID_BODY')
        parent.game.mass = 70
    else:
        parent = bpy.data.objects.new(name + 'Seat', None)
        scene.objects.link(parent)
        parent.location = (x, 0, 2)
    scene.update()
    bpy.ops.object.armature_add(location=(x, 0, 0.1 if mode == 'FREE' else 2))
    rig = bpy.context.object
    rig.name = name
    bpy.ops.object.mode_set(mode='EDIT')
    bone = rig.data.edit_bones[0]
    bone.name = 'Root'
    child = rig.data.edit_bones.new('Child')
    child.head, child.tail, child.parent = (0, 0, 1), (0, 0, 2), bone
    bpy.ops.object.mode_set(mode='OBJECT')
    world = rig.matrix_world.copy()
    rig.parent = parent
    rig.matrix_world = world
    rig.game.physics_type = 'NO_COLLISION'
    scene.update()
    addon.sync_bones(rig)
    settings = rig.anastacio_ragdoll
    settings.recovery_mode, settings.auto_recover = mode, automatic
    settings.recovery_delay = 0.35
    settings.controller = parent if mode == 'FREE' else None
    settings.anchor = parent if mode == 'ANCHOR' else None
    for preset in ('HARD', 'BALANCED', 'LIGHT'):
        settings.preset = preset
        addon.apply_preset(rig)
        expected = addon._PRESETS[preset]
        check(abs(settings.bones['Child'].joint_limits[0] - math.radians(expected[0][0])) < 1e-5,
              name + ': preset ' + preset)
    settings.preset = 'HARD' if name == 'Anchor' else 'LIGHT' if name in {'Free', 'NpcPermanent'} else 'BALANCED'
    addon.apply_preset(rig)
    addon.generate(bpy.context, rig, runtime=True)
    check(len(rig.game.components) == 1 and addon.runtime_component(rig) is not None,
          name + ': componente automático')
    addon.generate(bpy.context, rig)
    check(len(rig.game.components) == 1 and len(addon.owned(rig)) == 4,
          name + ': atualização não duplica componente/corpos')
    bodies = [obj for obj in addon.owned(rig) if obj.type == 'MESH']
    check(abs(sum(body.game.mass for body in bodies) - 70) < 1e-4,
          name + ': massa total distribuída')
    check(sum(len(body.constraints) for body in bodies) == 1, name + ': uma junta Bullet')
    check(all(abs(body.game.rotation_damping - addon._PRESETS[settings.preset][2]) < 1e-5
              for body in bodies), name + ': preset exportado para Bullet')
    if name == 'NpcPermanent':
        addon.runtime_component(rig).properties['Active'].value = True
    old_objects = set(addon.owned(rig))
    rig.data.pose_position = 'REST'
    try:
        addon.generate(bpy.context, rig)
    except ValueError:
        check(set(addon.owned(rig)) == old_objects, name + ': Rest Position exige seleção de Pose sem alterar geração')
    else:
        raise AssertionError('Rest Position foi aceito para execução')
    rig.data.pose_position = 'POSE'
    parent.scale = (1, 2, 1)
    scene.update()
    try:
        addon.generate(bpy.context, rig)
    except ValueError:
        check(set(addon.owned(rig)) == old_objects, name + ': escala inválida preserva geração anterior')
    else:
        raise AssertionError('Escala não uniforme foi aceita')
    parent.scale = (1, 1, 1)
    scene.update()

# Câmera e iluminação apenas para permitir inspeção manual da mesma cena.
from mathutils import Vector
bpy.ops.object.camera_add(location=(12, -20, 14))
scene.camera = bpy.context.object
scene.camera.rotation_euler = (Vector((0, 0, 1)) - scene.camera.location).to_track_quat('-Z', 'Y').to_euler()
bpy.ops.object.lamp_add(type='SUN', location=(0, 0, 10))
bpy.context.object.rotation_euler = (0.4, 0.3, -0.4)
if scene.world:
    scene.world.mist_settings.use_mist = False

driver = r'''
import hashlib, json, os, sys, traceback
import Range
from mathutils import Matrix, Vector
ticks = 0
cycles = 0
finished = False
checks = []
names = ['Anchor', 'AnchorAuto', 'Free', 'FreeAuto', 'NpcPermanent']
initial = {}
initial_root_positions = {}

def check(value, message):
    assert value, message
    checks.append(message)

def finish(error=None):
    global finished
    finished = True
    result = {'ok': error is None, 'ticks': ticks, 'cycles': cycles, 'checks': checks}
    module = sys.modules['anastacio_ragdoll_runtime']
    result['module_file'] = module.__file__
    result['runtime_version'] = list(module.RUNTIME_VERSION)
    with open(module.__file__, 'rb') as runtime_source:
        result['module_sha256'] = hashlib.sha256(runtime_source.read()).hexdigest()
    if error:
        result['error'] = error
    with open(os.environ.get('ANASTACIO_RAGDOLL_RESULT', Range.logic.expandPath('//runtime-result.json')), 'w') as output:
        json.dump(result, output, indent=2)
    print('ANASTACIO_RAGDOLL_RESULT', result)
    Range.logic.endGame()

def run(cont):
    global ticks, cycles
    ticks += 1
    scene = cont.owner.scene
    rigs = {name: scene.objects[name] for name in names}
    comps = {name: rigs[name].components[0] for name in names}
    if ticks == 5:
        for name, comp in comps.items():
            check(comp.is_valid and comp._ready and comp.active == (name == 'NpcPermanent'),
                  name + ': estado inicial válido: ' + comp.error)
            initial[name] = comp.world_transform(comp.controller) if comp.controller else rigs[name].worldTransform.copy()
            initial_root_positions[name] = comp.world_transform(comp._root['body']).translation.z
    if ticks == 10:
        for name, comp in comps.items():
            source = scene.objects['VelocityVehicle'] if name == 'Anchor' else None
            if source is not None:
                source.worldLinearVelocity = (3, 2, 0)
                source.worldAngularVelocity = (0, 0, 1)
            check(comp.activate(source) and comp.active, name + ': ativação')
            if source is not None:
                for item in comp.entries:
                    radius = comp.world_transform(item['body']).translation - comp.world_transform(source).translation
                    expected = source.worldLinearVelocity + source.worldAngularVelocity.cross(radius)
                    check((item['body'].worldLinearVelocity - expected).length < 1e-4,
                          'herança linear e angular por ponto do corpo')
            check(comp.activate(), name + ': ativação idempotente')
            check(rigs[name].parent is None, name + ': rig destacado')
    if ticks == 18:
        npc = comps['NpcPermanent']
        check(npc.world_transform(npc._root['body']).translation.z < initial_root_positions['NpcPermanent'] - 0.01,
              'NPC permanente realmente cai por gravidade')
    if 20 <= ticks < 120:
        anchor = comps['Anchor']
        if anchor.active:
            check(anchor.recover(), 'retorno à âncora')
        seat = anchor.anchor
        position = seat.worldPosition.copy()
        position.x += 0.01
        seat.worldPosition = position
        seat.worldOrientation = Matrix.Rotation(0.01 * cycles, 3, 'Z')
        local = rigs['Anchor'].localTransform.copy()
        check(anchor.activate(), 'reativação âncora')
        seat.worldPosition.z += 0.005
        expected = anchor.world_transform(seat) * local
        check(anchor.recover() and not anchor.active, 'recuperação âncora confirmada')
        check((anchor.world_transform(rigs['Anchor']).translation - expected.translation).length < 1e-4,
              'retorno acompanha translação e rotação do assento: %r / %r' %
              (tuple(rigs['Anchor'].worldPosition), tuple(expected.translation)))
        check(anchor.recover(), 'retorno idempotente')
        free = comps['Free']
        candidate = initial['Free'].copy()
        candidate.translation = (0, 0, 0.85)
        if free.active:
            check(free.recover(candidate), 'retorno livre com volume desocupado')
        check(free.activate(), 'reativação livre')
        check(free.recover(candidate), 'recuperação livre confirmada: ' + free.blocked_reason + free.error)
        for item in free.entries:
            expected_body = free.world_transform(free.object) * free._initial['matrices'][item['bone']] * item['offset']
            check((free.world_transform(item['body']).translation - expected_body.translation).length < 1e-4,
                  'corpo realinhado após retorno: %r / %r' %
                  (tuple(free.world_transform(item['body']).translation), tuple(expected_body.translation)))
        cycles += 1
    if ticks == 130:
        check(cycles == 100, '100 ciclos por modo')
        check(not comps['AnchorAuto'].active, 'recuperação automática em âncora')
        check(not comps['FreeAuto'].active, 'recuperação automática livre: ' + comps['FreeAuto'].blocked_reason)
        check(comps['NpcPermanent'].active, 'NPC sem recuperação automática permanece caído')
        for comp in comps.values():
            check(comp.is_valid, 'componentes continuam válidos: ' + comp.error)
        npc = comps['NpcPermanent']
        a, b = [item['body'].worldPosition for item in npc.entries]
        check((a-b).length < 2.0, 'junta mantém cadeia física conectada')
        free = comps['Free']
        check(free.activate(), 'ativação para testar bloqueio')
        candidate = initial['Free'].copy()
        candidate.translation = (0, 0, 0.85)
        scene.objects['Obstacle'].worldPosition = (0, 0, 1)
        old = free.controller.worldPosition.copy()
        check(not free.recover(candidate) and free.active, 'obstáculo impede recuperação')
        check((free.controller.worldPosition-old).length < 1e-5, 'falha não move controlador')
        scene.objects['Obstacle'].worldPosition = (50, 0, 1)
        free.recovery_validator = lambda comp, target: False
        check(not free.recover(candidate) and free.active, 'jogo pode recusar destino sem confirmar retorno')
        free.recovery_validator = None
        check(free.recover(candidate), 'retorno liberado após remover obstáculo')
        anchor = comps['Anchor']
        check(anchor.activate(), 'ativação para testar alvo inválido')
        anchor.entries[0]['constraint'].target = scene.objects['AnchorSeat']
        check(not anchor.recover() and anchor.active and not anchor.is_valid,
              'alvo inválido não confirma recuperação')
        finish()
    if ticks > 180:
        raise AssertionError('Timeout da regressão')

def tick(cont):
    if finished:
        return
    try:
        run(cont)
    except Exception:
        finish(traceback.format_exc())
'''
text = bpy.data.texts.new('anastacio_ragdoll_test.py')
text.write(driver)
owner = bpy.data.objects['AnchorSeat']
scene.objects.active = owner
bpy.ops.logic.sensor_add(type='ALWAYS', object=owner.name)
sensor = owner.game.sensors[-1]
sensor.use_pulse_true_level = True
bpy.ops.logic.controller_add(type='PYTHON', object=owner.name)
controller = owner.game.controllers[-1]
controller.mode = 'MODULE'
controller.module = 'anastacio_ragdoll_test.tick'
sensor.link(controller)
path = os.path.join(dest, 'runtime-ragdoll.range')
bpy.ops.wm.save_as_mainfile(filepath=path)
bpy.ops.wm.open_mainfile(filepath=path)
check(all(len(bpy.data.objects[name].game.components) == 1 for name, _, _, _ in configs),
      'componentes persistem ao reabrir')
with open(os.path.join(dest, 'editor-result.json'), 'w', encoding='utf-8') as output:
    json.dump({'ok': True, 'checks': checks, 'file': path}, output, indent=2)
print('EDITOR_RAGDOLL_OK', path)
