"""Gera cena isolada para validar os hooks Python do RolimaRacer, sem salvar o jogo.

AnastacioEngine.exe -b --factory-startup --python este.py -- cena.range pasta_do_jogo
Executar no player com ROLIMA_RAGDOLL_TRACE apontando para um JSONL novo.
"""
import bpy
import os
import sys

destination, project = sys.argv[sys.argv.index('--') + 1:]
sys.path.insert(0, project)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.resolution_x = 640
scene.game_settings.resolution_y = 360
scene.game_settings.show_fullscreen = False
scene.game_settings.use_frame_rate = True

# Um osso, um corpo rigido e um pivo, com as mesmas ligacoes do addon atual.
root = bpy.data.objects['Cube']
root.name = 'DiagnosticVehicle'
root.game.physics_type = 'NO_COLLISION'
for name, kind, value in [('has_ragdoll', 'BOOL', True),
                          ('ragdoll_system', 'BOOL', False),
                          ('trigger_ragdoll', 'BOOL', False),
                          ('player_1_2_PC', 'INT', 1)]:
    scene.objects.active = root
    bpy.ops.object.game_property_new(type=kind, name=name)
    root.game.properties[name].value = value

bpy.ops.object.armature_add(location=(0, 0, 3))
rig = bpy.context.object
rig.name = 'DiagnosticArmature'
rig.parent = root
bpy.ops.mesh.primitive_cube_add(location=(0, 0, 3.5))
body = bpy.context.object
body.name = 'RagdollPart-DiagnosticArmature-Bone-Dynamic'
body.scale = (0.1, 0.1, 0.5)
body.game.physics_type = 'RIGID_BODY'
bpy.ops.object.add(type='EMPTY', location=(0, 0, 3))
pivot = bpy.context.object
pivot.parent = body
pivot.matrix_world.translation = (0, 0, 3)
constraint = rig.pose.bones[0].constraints.new('COPY_TRANSFORMS')
constraint.target = pivot
scene.objects.active = rig
bpy.ops.logic.python_component_register(
    component_name='scripts.VehicleSystem.ragdoll_system.ragdoll.Ragdoll')

driver = r'''
import sys, os, json
sys.path.insert(0, PROJECT)
import Range
from types import SimpleNamespace
from scripts.VehicleSystem import ragdoll_controller as rc
from scripts.VehicleSystem.ragdoll_system import diagnostics as trace

ticks = 0
ctrl = None
def tick(cont):
    global ticks, ctrl
    ticks += 1
    scene = Range.logic.getCurrentScene()
    if ctrl is None:
        ctrl = SimpleNamespace(object=cont.owner, armature=scene.objects['DiagnosticArmature'],
            scene=scene, group_character=None, Animations=None, delta_time=1.0,
            delay_ragdoll=0.0, ragdoll_cooldown=0.0)
        rc._ensure_deps = lambda: True
        rc.AnimationManager = None
        rc.InputConfig = SimpleNamespace(Actions=SimpleNamespace(RAGDOLL='ragdoll'))
        rc.InputManager = SimpleNamespace(of=lambda c: SimpleNamespace(get_button_down=lambda a: ticks == 80))
        trace.event('smoke_start', ctrl)
    if ticks in (10, 80):
        ctrl.ragdoll_cooldown = 0.0
        ctrl.object['trigger_ragdoll'] = (ticks == 10)
        rc.active_ragdoll(ctrl)
    if ticks in (40, 110):
        rc.time_to_return_from_Ragdoll(ctrl)
    if ticks == 130:
        # Confirma que o decorator devolve valores e propaga erros sem os engolir.
        @trace.timed('smoke.return_value')
        def result(): return 42
        assert result() == 42
        @trace.timed('smoke.exception')
        def failure(): raise ValueError('expected-smoke-error')
        try:
            failure()
        except ValueError:
            trace.event('smoke_exception_preserved')
        else:
            raise AssertionError('diagnostic swallowed exception')
        trace.event('smoke_ok', ctrl, ragdoll=ctrl.object['ragdoll_system'])
        with open(os.environ.get('ROLIMA_RAGDOLL_SMOKE_RESULT',
                                 Range.logic.expandPath('//smoke-result.json')), 'w') as result_file:
            json.dump({'ok': True, 'enabled': trace.ENABLED,
                       'ragdoll': ctrl.object['ragdoll_system'], 'ticks': ticks}, result_file)
        trace.close()
        Range.logic.endGame()
'''.replace('PROJECT', repr(os.path.abspath(project)))
text = bpy.data.texts.new('ragdoll_diagnostic_smoke.py')
text.write(driver)
scene.objects.active = root
bpy.ops.logic.sensor_add(type='ALWAYS', object=root.name)
sensor = root.game.sensors[-1]
sensor.use_pulse_true_level = True
bpy.ops.logic.controller_add(type='PYTHON', object=root.name)
controller = root.game.controllers[-1]
controller.mode = 'MODULE'
controller.module = 'ragdoll_diagnostic_smoke.tick'
sensor.link(controller)
bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(destination))
bpy.ops.wm.open_mainfile(filepath=os.path.abspath(destination))
assert bpy.data.objects['DiagnosticArmature'].game.components[0].module == 'scripts.VehicleSystem.ragdoll_system.ragdoll'
assert bpy.data.objects['DiagnosticVehicle'].game.controllers[-1].module == 'ragdoll_diagnostic_smoke.tick'
assert bpy.data.objects['DiagnosticArmature'].pose.bones[0].constraints[0].target.parent.name == 'RagdollPart-DiagnosticArmature-Bone-Dynamic'
print('RAGDOLL_DIAGNOSTIC_SCENE_OK', destination)
