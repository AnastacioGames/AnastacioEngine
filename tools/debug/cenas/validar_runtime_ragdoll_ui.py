# -*- coding: utf-8 -*-
"""Requer editor com runtime-ragdoll.range como argumento; testa Undo/Redo e encerra."""
import json
import os
import sys
import traceback

import bpy

root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, os.path.join(root, 'source', 'release', 'scripts', 'addons'))
import anastacio_ragdoll as addon
dest = os.path.abspath(sys.argv[sys.argv.index('--') + 1])
checks = []


def check(value, message):
    assert value, message
    checks.append(message)


def state():
    rig = bpy.data.objects['Free']
    bpy.context.scene.objects.active = rig
    return rig, addon.runtime_component(rig), addon.owned(rig)


def run():
    addon.register()
    bpy.context.user_preferences.edit.use_global_undo = True
    rig, component, objects = state()
    check(component is not None and len(objects) == 4, 'estado inicial com componente e quatro objetos')
    bpy.ops.ed.undo_push(message='Antes de atualizar execução')
    rig.anastacio_ragdoll.total_mass = 90
    rig.anastacio_ragdoll.auto_recover = True
    rig.anastacio_ragdoll.preset = 'HARD'
    addon.apply_preset(rig)
    check('FINISHED' in bpy.ops.anastacio.ragdoll_runtime(), 'operador prepara execução')
    bpy.ops.ed.undo_push(message='Depois de atualizar execução')
    rig, component, objects = state()
    check(len(rig.game.components) == 1, 'atualização mantém um componente')
    check(component.properties['Auto Recover'].value, 'opção de NPC sincronizada no componente')
    check(abs(sum(obj.game.mass for obj in objects if obj.type == 'MESH') - 90) < 1e-4,
          'nova massa aplicada')
    bpy.ops.ed.undo()
    rig, component, objects = state()
    check(not component.properties['Auto Recover'].value, 'Undo restaura recuperação anterior')
    check(abs(sum(obj.game.mass for obj in objects if obj.type == 'MESH') - 70) < 1e-4,
          'Undo restaura massa anterior')
    bpy.ops.ed.redo()
    rig, component, objects = state()
    check(component.properties['Auto Recover'].value, 'Redo restaura opção de recuperação')
    check(all(abs(obj.game.rotation_damping - 0.8) < 1e-5 for obj in objects if obj.type == 'MESH'),
          'Redo restaura preset duro')
    bpy.ops.ed.undo_push(message='Antes de remover execução')
    check('FINISHED' in bpy.ops.anastacio.ragdoll_remove(), 'operador remove execução')
    bpy.ops.ed.undo_push(message='Depois de remover execução')
    rig, component, objects = state()
    check(component is None and not objects, 'remoção limpa corpos e componente')
    check(addon.ragdoll_folder(bpy.context.scene, rig)[0] is None, 'remoção limpa pasta vazia')
    bpy.ops.ed.undo()
    rig, component, objects = state()
    check(component is not None and len(objects) == 4, 'Undo restaura componente, corpos e pivôs')
    check(addon.ragdoll_folder(bpy.context.scene, rig)[0] is not None, 'Undo restaura pasta')
    bpy.ops.ed.redo()
    rig, component, objects = state()
    check(component is None and not objects, 'Redo limpa execução novamente')
    check(bpy.data.objects.get('FreeController') is not None, 'controlador do jogo preservado')
    check(len(bpy.data.objects['Anchor'].game.components) == 1, 'outros rigs preservados')


result = {'ok': False, 'checks': checks}
try:
    run()
except Exception:
    result['error'] = traceback.format_exc()
else:
    result['ok'] = True
with open(os.path.join(dest, 'runtime-ui-result.json'), 'w', encoding='utf-8') as output:
    json.dump(result, output, indent=2)
bpy.context.user_preferences.view.use_quit_dialog = False
bpy.ops.wm.quit_blender()
