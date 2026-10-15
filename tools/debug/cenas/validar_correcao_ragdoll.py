"""Gera regressão de estados, referências e integração no player real.

Uso igual a validar_diagnostico_ragdoll.py. RAGDOLL_TEST_MODE=menu gera caso de menu.
ROLIMA_RAGDOLL_SMOKE_RESULT recebe evidência explícita de sucesso/falha no runtime.
"""
import os
import runpy

import bpy

runpy.run_path(os.path.join(os.path.dirname(__file__), 'validar_diagnostico_ragdoll.py'),
               run_name='__main__')
scene = bpy.context.scene
root = bpy.data.objects['DiagnosticVehicle']
root.game.physics_type = 'RIGID_BODY'
root.game.mass = 100.0
root.game.use_collision_compound = True
root.name = 'VehicleCollider'
bpy.ops.object.add(type='EMPTY', location=(0, 0, 0))
controller_root = bpy.context.object
controller_root.name = 'DiagnosticVehicle'
for prop in root.game.properties:
    bpy.ops.object.game_property_new(type=prop.type, name=prop.name)
    controller_root.game.properties[prop.name].value = prop.value
root.parent = controller_root
rig = bpy.data.objects['DiagnosticArmature']
rig.game.components[0].properties['Active'].value = True
body = bpy.data.objects['RagdollPart-DiagnosticArmature-Bone-Dynamic']
body.name = 'RagdollPart-RenamedBody'
pivot = rig.pose.bones[0].constraints[0].target
pivot.name = 'RenamedPivot'
bpy.ops.object.add(type='EMPTY', location=(4, 0, 0))
helper = bpy.context.object
helper.name = 'UnrelatedTarget'
# Filho adicional: o código não pode escolher children[0] como pivô.
helper.parent = body
extra = rig.pose.bones[0].constraints.new('COPY_LOCATION')
extra.name = 'UserConstraint'
extra.target = helper
extra.influence = 0.37
extra.use_x = extra.use_y = extra.use_z = False
extra = rig.pose.bones[0].constraints.new('COPY_TRANSFORMS')
extra.name = 'UserCopyTransforms'
extra.target = helper
extra.influence = 0.22
# Não pode usar essa outra Copy Transforms só porque tem um target.
helper.parent = None
bpy.ops.object.add(type='EMPTY', location=(0, 0, 0))
bpy.context.object.name = 'BodyAccessory'
bpy.context.object.parent = body
for name, height in [('PilotUp', 2.0), ('PilotDown', 1.0)]:
    bpy.ops.mesh.primitive_cube_add(location=(0, 0, height))
    collider = bpy.context.object
    collider.name = name
    collider.scale = (0.1, 0.1, 0.1)
    collider.game.physics_type = 'RIGID_BODY'
    collider.parent = root
if os.environ.get('RAGDOLL_TEST_MODE') == 'menu':
    scene.name = 'MenuDiagnostic'

driver = r'''
import json, os, traceback
from types import SimpleNamespace
import Range
from mathutils import Vector, Matrix
from scripts.VehicleSystem import ragdoll_controller as rc
from scripts.VehicleSystem.ragdoll_system import diagnostics as trace

ticks = 0
ctrl = None
button = False
cycles = 0
completed = False

def finish(result):
    global completed
    completed = True
    with open(os.environ['ROLIMA_RAGDOLL_SMOKE_RESULT'], 'w') as output:
        json.dump(result, output)
    trace.close()
    Range.logic.endGame()

def run(cont):
    global ticks, ctrl, button, cycles
    ticks += 1
    scene = cont.owner.scene
    rig = scene.objects['DiagnosticArmature']
    body = scene.objects['RagdollPart-RenamedBody']
    comp = rig.components[0]
    if ctrl is None:
        ctrl = SimpleNamespace(object=scene.objects['DiagnosticVehicle'], armature=rig, scene=scene,
            group_character=None, Animations=None, delta_time=1.0,
            delay_ragdoll=0.0, ragdoll_cooldown=0.0,
            pilot_collisioBox=scene.objects['PilotUp'],
            pilot_collisioBox_down=scene.objects['PilotDown'],
            VehicleComponent=SimpleNamespace(Vehicle=SimpleNamespace(Collider=cont.owner)))
        rc._ensure_deps = lambda: True
        rc.AnimationManager = None
        rc.InputConfig = SimpleNamespace(Actions=SimpleNamespace(RAGDOLL='ragdoll'))
        rc.InputManager = SimpleNamespace(of=lambda c: SimpleNamespace(get_button_down=lambda a: button))
    unrelated = rig.constraints['Bone:UserConstraint']
    other_copy = rig.constraints['Bone:UserCopyTransforms']
    assert abs(unrelated.enforce - 0.37) < 1e-6
    assert abs(other_copy.enforce - 0.22) < 1e-6
    if ticks == 5:
        assert comp.is_valid, comp.error
        if 'menu' in scene.name.lower():
            assert not comp.active
            assert not rig['active_ragdoll']
            assert not comp.set_active(True)
            assert rig.constraints['Bone:Copy Transforms'].enforce == 0.0
            finish({'ok': True, 'case': 'menu', 'ticks': ticks})
            return
        assert comp.active, 'Active=True deve ligar a física na primeira atualização'
        assert body.getLinearVelocity().z < 0.0, 'Corpo inicial ficou suspenso'
        assert comp.set_active(False)
        # Duplicidade é idempotente e não recoloca física em simulação.
        assert comp.set_active(False)
    if 10 <= ticks < 210:
        if ticks % 2 == 0:
            ctrl.ragdoll_cooldown = 0.0
            ctrl.object['trigger_ragdoll'] = (cycles % 2 == 0)
            button = not ctrl.object['trigger_ragdoll']
            cont.owner.setLinearVelocity((3, 2, 0), False)
            rc.active_ragdoll(ctrl)
            button = False
            assert ctrl.object['ragdoll_system'] and comp.active
            expected = cont.owner.getLinearVelocity() * 0.4
            assert (body.getLinearVelocity() - expected).length < 1e-5
            assert ctrl.pilot_collisioBox.parent is None
            assert ctrl.pilot_collisioBox_down.parent is None
            # Assento deve acompanhar translação e rotação do veículo.
            cont.owner.worldPosition.x += 0.1
            cont.owner.worldOrientation = Matrix.Rotation(0.01 * cycles, 3, 'Z')
        else:
            assert rc.time_to_return_from_Ragdoll(ctrl) is True
            assert not ctrl.object['ragdoll_system'] and not comp.active
            expected = cont.owner.worldTransform * ctrl._ragdoll_seat_transform
            assert (rig.worldPosition - expected.translation).length < 1e-4
            assert rig.parent == cont.owner
            assert ctrl.pilot_collisioBox.parent is None
            assert ctrl.pilot_collisioBox_down.parent == cont.owner
            position = rig.localPosition.copy()
            rc._apply_mesh_rendering_refresh(ctrl, 10)
            # Interromper o refresh não pode deixar 1 mm acumulado no assento.
            assert (rig.localPosition - position).length < 1e-6
            cycles += 1
    if ticks == 210:
        assert cycles == 100
        # Uma falha real de referência não pode liberar o controle do jogo.
        ctrl.ragdoll_cooldown = 0.0
        ctrl.object['trigger_ragdoll'] = True
        rc.active_ragdoll(ctrl)
        assert comp.active
        rig.constraints['Bone:Copy Transforms'].target = scene.objects['UnrelatedTarget']
        assert rc.time_to_return_from_Ragdoll(ctrl) is False
        assert ctrl.object['ragdoll_system']
        assert ctrl.object['ragdoll_error']
        assert not comp.is_valid
        finish({'ok': True, 'case': 'cycles', 'cycles': cycles, 'ticks': ticks,
                'reference_failure_preserved_flags': True,
                'unrelated_constraints_preserved': True})

def tick(cont):
    if completed:
        return
    try:
        run(cont)
    except Exception:
        finish({'ok': False, 'ticks': ticks, 'cycles': cycles, 'error': traceback.format_exc()})
'''
bpy.data.texts['ragdoll_diagnostic_smoke.py'].clear()
bpy.data.texts['ragdoll_diagnostic_smoke.py'].write(driver)
destination = bpy.data.filepath
bpy.ops.wm.save_as_mainfile(filepath=destination)
bpy.ops.wm.open_mainfile(filepath=destination)
assert bpy.data.objects['DiagnosticArmature'].game.components[0].properties['Active'].value
assert len(bpy.data.objects['DiagnosticArmature'].pose.bones[0].constraints) == 3
assert bpy.data.objects.get('RagdollPart-RenamedBody') is not None
print('RAGDOLL_CORRECTION_SCENE_OK', destination)
