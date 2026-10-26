"""Cena isolada para a revisao dos bindings de KX_GameObject.

AnastacioEngine.exe -b --factory-startup --python este_script -- <pasta> [inspect]
GAMEOBJECT_PYTHON_CASE=basic|half_one|half_two|soft_pose|verify
AnastacioRuntime.exe --server <pasta>/revisao_gameobject_python.range
Os dois ultimos modos verificam chamadas suspeitas e podem encerrar o player.
"""
import json
import os
import runpy
import sys

import bpy


out_dir = os.path.abspath(sys.argv[sys.argv.index('--') + 1])
os.makedirs(out_dir, exist_ok=True)
scene_path = os.path.join(out_dir, 'revisao_gameobject_python.range')
if sys.argv[-1] == 'inspect':
    bpy.ops.wm.open_mainfile(filepath=scene_path)
    scene = bpy.context.scene
    data = {'camera': scene.camera.name, 'objects': {}, 'controllers': []}
    for obj in scene.objects:
        data['objects'][obj.name] = {
            'physics': obj.game.physics_type,
            'materials': [m.name for m in obj.data.materials] if obj.type == 'MESH' else [],
        }
        for controller in obj.game.controllers:
            module, function = controller.module.split('.')
            data['controllers'].append({
                'object': obj.name, 'module': controller.module, 'mode': controller.mode,
                'sensors': [s.name for s in obj.game.sensors if controller in list(s.controllers)],
                'function_present': 'def ' + function + '(' in bpy.data.texts[module + '.py'].as_string(),
            })
    with open(os.path.join(out_dir, 'inspection.json'), 'w') as output:
        json.dump(data, output, indent=2)
else:
    # Reaproveita camera, materiais e ligacoes ja validados na revisao do nucleo.
    runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               'criar_cena_revisao_gameobject.py'), run_name='__main__')
    scene = bpy.context.scene
    scene.game_settings.use_activity_culling = False
    bpy.data.objects['PhysicsOnly'].game.physics_type = 'RIGID_BODY'
    text = bpy.data.texts['object_review.py']
    text.clear()
    text.write('''import json
import math
import os
import sys
import traceback
import Range

MODE = os.environ.get('GAMEOBJECT_PYTHON_CASE', 'basic')
OUT = os.path.join(Range.logic.expandPath('//'), 'result_' + MODE + '.json')
FRAME = 0
RESULTS = {'mode': MODE, 'python': sys.version}

def save():
    with open(OUT, 'w') as output:
        json.dump(RESULTS, output, indent=2, allow_nan=False)

def count(cont):
    pass

def attempt(name, function):
    try:
        value = function()
        RESULTS[name] = {'returned': repr(value)}
    except Exception as error:
        RESULTS[name] = {'error': type(error).__name__, 'message': str(error)}
    save()

def expect_error(error_type, function):
    try:
        function()
    except error_type:
        return
    raise AssertionError('expected ' + error_type.__name__)

def verify(obj, scene):
    mesh = obj.meshes[0]
    before = sys.getrefcount(mesh)
    for i in range(100):
        transient = obj.meshes
        del transient
    assert sys.getrefcount(mesh) == before
    empty = scene.objects['ReviewProbe']
    # Aquece o acesso antes de medir referencias (lookup/especializacao do Python).
    for i in range(30):
        transient = empty.lodManager
        del transient
    before = sys.getrefcount(None)
    for i in range(30):
        transient = empty.lodManager
        del transient
    RESULTS['none_ref_delta'] = sys.getrefcount(None) - before
    save()
    assert RESULTS['none_ref_delta'] == 0
    RESULTS['references_balanced'] = True
    for attribute, initial in [('linearDamping', 0.4), ('angularDamping', 0.3)]:
        setattr(obj, attribute, initial)
        before = getattr(obj, attribute)
        expect_error(TypeError, lambda: setattr(obj, attribute, 'invalid'))
        assert getattr(obj, attribute) == before
    RESULTS['damping_preserved_on_error'] = True
    for setter, getter in [(obj.setVehicleMaxTorque, obj.getVehicleMaxTorque),
                           (obj.setVehicleMaxRPM, obj.getVehicleMaxRPM)]:
        setter(321)
        for invalid, error in [(1e100, OverflowError), (float('inf'), ValueError),
                               (float('nan'), ValueError), (-1, ValueError), ('bad', TypeError)]:
            expect_error(error, lambda: setter(invalid))
            assert getter() == 321
        setter(3.4e38)
        assert math.isfinite(getter())
        setter(321)
    obj.setVehicleGearRatios([-3, 2])
    for invalid, error in [([2, 1e100], OverflowError), ([-1e100], OverflowError),
                           ([float('inf')], ValueError), (['bad'], TypeError)]:
        expect_error(error, lambda: obj.setVehicleGearRatios(invalid))
        assert tuple(obj.getVehicleGearRatios()) == (-3, 2)
    RESULTS['vehicle_ranges_atomic'] = True
    origin = tuple(obj.worldPosition)
    for poly, size in [(0, 3), (1, 4), (2, 5)]:
        for distance in (0, 10):
            result = obj.rayCast(origin, dist=distance, poly=poly)
            assert len(result) == size and all(x is None for x in result)
        assert len(obj.rayCast((50, 50, 50), poly=poly)) == size
        result = obj.rayCast(scene.objects['LogicOnly'], poly=poly)
        assert len(result) == size and result[0] is scene.objects['LogicOnly']
    RESULTS['raycast_contract'] = True
    for key in (7, ('tuple', 2), 'text'):
        obj[key] = ['stored']
        assert obj[key] == obj.get(key) == ['stored'] and key in obj
        del obj[key]
        expect_error(KeyError, lambda: obj[key])
    expect_error(TypeError, lambda: obj[[]])
    RESULTS['mapping_contract'] = True
    obj.setActionLayerSpeed(layer=0, speed=1)
    obj.setActionLayerWeight(layer=0, layerWeight=1)
    obj.setActionLayerSpeed(0, speed=1)
    obj.setActionLayerWeight(0, layerWeight=1)
    obj.setActionLayerSpeed(0, 1)
    obj.setActionLayerWeight(0, 1)
    expect_error(TypeError, lambda: obj.setActionLayerSpeed(layer=0, unknown=1))
    RESULTS['action_keywords'] = True
    obj.setHalfAnimations(True)
    obj.setHalfAnimations(False)
    expect_error(TypeError, lambda: obj.setHalfAnimations())
    expect_error(TypeError, lambda: obj.setHalfAnimations(True, False))
    obj.setSoftPoseMatching(True)
    obj.setSoftPoseMatching(False)
    class InvalidTruth:
        def __bool__(self):
            raise RuntimeError('test truth conversion')
    expect_error(RuntimeError, lambda: obj.setSoftPoseMatching(InvalidTruth()))
    RESULTS['parser_contracts'] = True
    save()

def tick(cont):
    global FRAME
    FRAME += 1
    try:
        scene = Range.logic.getCurrentScene()
        obj = scene.objects['PhysicsOnly']
        if FRAME == 1:
            RESULTS['started'] = True
            save()
            if MODE == 'verify':
                verify(obj, scene)
            elif MODE == 'basic':
                obj.gravity = (0, 0, 0)
                origin = tuple(obj.worldPosition)
                RESULTS['ray_lengths_zero'] = [len(obj.rayCast(origin, poly=p)) for p in (0, 1, 2)]
                RESULTS['ray_lengths_miss'] = [len(obj.rayCast((50, 50, 50), poly=p)) for p in (0, 1, 2)]
                mesh = obj.meshes[0]
                before = sys.getrefcount(mesh)
                for i in range(100):
                    transient = obj.meshes
                    del transient
                RESULTS['mesh_proxy_ref_growth_100'] = sys.getrefcount(mesh) - before
                empty = scene.objects['ReviewProbe']
                before = sys.getrefcount(None)
                for i in range(30):
                    transient = empty.animationEventManager
                    del transient
                RESULTS['none_ref_control_30'] = sys.getrefcount(None) - before
                before = sys.getrefcount(None)
                for i in range(30):
                    transient = empty.lodManager
                    del transient
                RESULTS['none_ref_lod_30'] = sys.getrefcount(None) - before
                obj.linearDamping = 0.4
                RESULTS['damping_before'] = obj.linearDamping
                attempt('invalid_damping', lambda: setattr(obj, 'linearDamping', 'invalid'))
                RESULTS['damping_after'] = obj.linearDamping
                obj.angularDamping = 0.3
                attempt('invalid_angular_damping', lambda: setattr(obj, 'angularDamping', 'invalid'))
                RESULTS['angular_damping_after'] = obj.angularDamping
                obj.setVehicleMaxTorque(1e100)
                RESULTS['torque_overflow_finite'] = math.isfinite(obj.getVehicleMaxTorque())
                obj.setVehicleGearRatios([1e100])
                RESULTS['gears_overflow_finite'] = math.isfinite(obj.getVehicleGearRatios()[0])
                obj.setVehicleMaxTorque(0)
                obj.setVehicleGearRatios([])
                obj[7] = ['stored']
                attempt('mapping_integer_key', lambda: obj[7])
                attempt('get_integer_key', lambda: obj.get(7))
                attempt('layer_speed_keywords', lambda: obj.setActionLayerSpeed(layer=0, speed=1))
                attempt('layer_weight_keywords', lambda: obj.setActionLayerWeight(layer=0, layerWeight=1))
                save()
            elif MODE in ('half_one', 'half_two', 'soft_pose'):
                RESULTS['call_entered'] = True
                save()
                if MODE == 'half_one':
                    obj.setHalfAnimations(True)
                elif MODE == 'half_two':
                    obj.setHalfAnimations(True, False)
                else:
                    obj.setSoftPoseMatching(True)
                RESULTS['call_returned'] = True
                save()
            else:
                raise ValueError('unknown case ' + MODE)
        if FRAME >= 10:
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
    print('GAMEOBJECT_PYTHON_REVIEW_SAVED', scene_path)
