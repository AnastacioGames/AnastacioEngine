"""Extrai os rigs do .range aberto para uma cena temporária de regressão.

Editor -b RolimaRacer.range --python este.py -- saida.range pasta_do_jogo
Não salva no arquivo original. Evidência do player: ROLIMA_RAGDOLL_SMOKE_RESULT.
"""
import os
import sys

import bpy
from mathutils import Vector

destination, project = sys.argv[sys.argv.index('--') + 1:]
assert os.path.normcase(os.path.abspath(destination)) != os.path.normcase(bpy.data.filepath)
sys.path.insert(0, project)
rigs = [obj for obj in bpy.data.objects if obj.type == 'ARMATURE' and any(
    comp.module == 'scripts.VehicleSystem.ragdoll_system.ragdoll' for comp in obj.game.components)]
assert len(rigs) == 4, [obj.name for obj in rigs]
scene = bpy.data.scenes.new('RagdollRegression')
bpy.context.screen.scene = scene
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.resolution_x = 640
scene.game_settings.resolution_y = 360
scene.game_settings.show_fullscreen = False
scene.game_settings.use_frame_rate = True
scene.game_settings.physics_gravity = 0.0
for index, rig in enumerate(rigs):
    needed = {rig}
    for bone in rig.pose.bones:
        for constraint in bone.constraints:
            if constraint.type == 'COPY_TRANSFORMS' and constraint.target:
                pivot = constraint.target
                if pivot.parent and pivot.parent.name.startswith('RagdollPart-'):
                    needed.update((pivot, pivot.parent))
    for obj in needed:
        scene.objects.link(obj)
        obj.layers = [True] + [False] * 19
    anchor = bpy.data.objects.new('RegressionAnchor-' + rig.name, None)
    scene.objects.link(anchor)
    position = rig.matrix_world.copy()
    rig.parent = anchor
    rig.matrix_world = position
    scene.objects.active = anchor
    for name, kind, value in [('has_ragdoll', 'BOOL', True),
                              ('ragdoll_system', 'BOOL', False),
                              ('trigger_ragdoll', 'BOOL', False),
                              ('player_1_2_PC', 'INT', 3)]:
        bpy.ops.object.game_property_new(type=kind, name=name)
        anchor.game.properties[name].value = value
    component = next(comp for comp in rig.game.components
                     if comp.module == 'scripts.VehicleSystem.ragdoll_system.ragdoll')
    component.properties['Active'].value = False

camera = bpy.data.objects.new('RegressionCamera', bpy.data.cameras.new('RegressionCamera'))
scene.objects.link(camera)
scene.camera = camera
camera.location = (0, -30, 15)
camera.rotation_euler = (Vector((0, 0, 0)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
controller = bpy.data.objects.new('RegressionDriver', None)
scene.objects.link(controller)
scene.objects.active = controller
bpy.ops.logic.sensor_add(type='ALWAYS', object=controller.name)
sensor = controller.game.sensors[-1]
sensor.use_pulse_true_level = True
bpy.ops.logic.controller_add(type='PYTHON', object=controller.name)
logic = controller.game.controllers[-1]
logic.mode = 'MODULE'
logic.module = 'anastacio_ragdoll_rigs_test.tick'
sensor.link(logic)
text = bpy.data.texts.new('anastacio_ragdoll_rigs_test.py')
text.write(r'''
import json, os, traceback
from types import SimpleNamespace
import Range
from scripts.VehicleSystem import ragdoll_controller as rc
from scripts.VehicleSystem.ragdoll_system import diagnostics as trace
ticks = 0
controls = []
cycles = 0

def tick(cont):
    global ticks, controls, cycles
    ticks += 1
    try:
        scene = cont.owner.scene
        if ticks == 5:
            rc._ensure_deps = lambda: False
            rc.AnimationManager = None
            for obj in scene.objects:
                if hasattr(obj, 'constraints') and hasattr(obj, 'channels'):
                    comp = next((c for c in obj.components if getattr(c, 'anastacio_ragdoll', False)), None)
                    if comp is not None:
                        assert comp.is_valid, (obj.name, comp.error)
                        assert comp.bone_cache and len(comp.bone_cache) >= 10
                        controls.append(SimpleNamespace(object=obj.parent, armature=obj,
                            scene=scene, group_character=None, Animations=None,
                            delta_time=1.0, delay_ragdoll=0.0, ragdoll_cooldown=0.0))
            assert len(controls) == 4
        if 10 <= ticks < 210:
            for ctrl in controls:
                if ticks % 2 == 0:
                    ctrl.ragdoll_cooldown = 0.0
                    ctrl.object['trigger_ragdoll'] = True
                    rc.active_ragdoll(ctrl)
                    assert ctrl.object['ragdoll_system'], (ctrl.armature.name, ctrl.object.get('ragdoll_error'))
                    ctrl.object.worldPosition.x += 0.1
                else:
                    assert rc.time_to_return_from_Ragdoll(ctrl) is True, ctrl.armature.name
                    assert not ctrl.object['ragdoll_system']
            if ticks % 2:
                cycles += 1
        if ticks == 210:
            assert cycles == 100
            finish({'ok': True, 'cycles_per_rig': cycles,
                    'rigs': {c.armature.name: len(rc._get_ragdoll_component(c).bone_cache)
                             for c in controls}})
    except Exception:
        finish({'ok': False, 'ticks': ticks, 'cycles': cycles, 'error': traceback.format_exc()})

def finish(result):
    with open(os.environ['ROLIMA_RAGDOLL_SMOKE_RESULT'], 'w') as output:
        json.dump(result, output)
    trace.close()
    Range.logic.endGame()
''')
# Exporta apenas a cena isolada. Guardar as outras cenas faria o preload global
# do jogo compilar materiais de pistas/menus sem relação com esta regressão.
bpy.data.libraries.write(os.path.abspath(destination), {scene, text})
bpy.ops.wm.open_mainfile(filepath=os.path.abspath(destination))
assert bpy.context.scene.name == 'RagdollRegression'
assert len([obj for obj in bpy.context.scene.objects if obj.type == 'ARMATURE']) == 4
# O player legado requer o bloco de janela/startup de um mainfile completo;
# um arquivo de biblioteca sozinho pode falhar antes de iniciar a cena.
bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(destination))
bpy.ops.wm.open_mainfile(filepath=os.path.abspath(destination))
assert len(bpy.data.scenes) == 1
assert bpy.data.texts.get('anastacio_ragdoll_rigs_test.py') is not None
print('RAGDOLL_REAL_RIGS_SCENE_OK', destination)
