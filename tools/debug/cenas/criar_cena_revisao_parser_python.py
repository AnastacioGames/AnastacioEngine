"""Regressao do parser compartilhado; gera/inspeciona cena isolada.

AnastacioEngine.exe -b --factory-startup --python este_script -- <pasta> [inspect]
PARSER_REVIEW_ORDER=parent_first|mesh_first AnastacioRuntime.exe --server <cena>
"""
import json
import os
import runpy
import sys

import bpy


out_dir = os.path.abspath(sys.argv[sys.argv.index('--') + 1])
os.makedirs(out_dir, exist_ok=True)
scene_path = os.path.join(out_dir, 'revisao_parser_python.range')
if sys.argv[-1] == 'inspect':
    bpy.ops.wm.open_mainfile(filepath=scene_path)
    scene = bpy.context.scene
    data = {'camera': scene.camera.name, 'objects': {}, 'controllers': []}
    for obj in scene.objects:
        data['objects'][obj.name] = {
            'materials': [m.name for m in obj.data.materials] if obj.type == 'MESH' else [],
        }
        for controller in obj.game.controllers:
            module, function = controller.module.split('.')
            data['controllers'].append({
                'module': controller.module, 'mode': controller.mode,
                'sensors': [s.name for s in obj.game.sensors if controller in list(s.controllers)],
                'function_present': 'def ' + function + '(' in bpy.data.texts[module + '.py'].as_string(),
            })
    with open(os.path.join(out_dir, 'inspection.json'), 'w') as output:
        json.dump(data, output, indent=2)
else:
    runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               'criar_cena_revisao_gameobject_python.py'), run_name='__main__')
    text = bpy.data.texts['object_review.py']
    text.clear()
    text.write('''import json
import os
import traceback
import Range

ORDER = os.environ.get('PARSER_REVIEW_ORDER', 'parent_first')
OUT = os.path.join(Range.logic.expandPath('//'), 'result_' + ORDER + '.json')
RESULTS = {'order': ORDER, 'checks': {}}
FRAME = 0

def save():
    with open(OUT, 'w') as output:
        json.dump(RESULTS, output, indent=2)

def count(cont):
    pass

def check(name, function, error=None):
    try:
        function()
        RESULTS['checks'][name] = {'passed': error is None}
    except Exception as exc:
        RESULTS['checks'][name] = {
            'passed': error is not None and isinstance(exc, error),
            'error': type(exc).__name__, 'message': str(exc),
        }
    save()

def tick(cont):
    global FRAME
    FRAME += 1
    try:
        if FRAME == 1:
            scene = Range.logic.getCurrentScene()
            obj = scene.objects['PhysicsOnly']
            probe = scene.objects['ReviewProbe']
            parent = scene.objects['LogicOnly']
            mesh = obj.meshes[0]
            # First use selects the old static parser's names for both methods.
            if ORDER == 'parent_first':
                probe.setParent(None)
            elif ORDER == 'mesh_first':
                obj.replaceMesh(mesh, False, False)
            else:
                raise ValueError(ORDER)
            for i in range(8):
                check('parent_keywords_' + str(i),
                      lambda: probe.setParent(parent=parent, compound=0, ghost=0))
                check('parent_identity_' + str(i), lambda: require(probe.parent is parent))
                probe.removeParent()
                check('mesh_keywords_' + str(i),
                      lambda: obj.replaceMesh(mesh=mesh, useDisplayMesh=0, usePhysicsMesh=0))
            check('parent_mixed', lambda: probe.setParent(parent, ghost=0))
            probe.removeParent()
            check('mesh_mixed', lambda: obj.replaceMesh(mesh, useDisplayMesh=0, usePhysicsMesh=0))
            check('parent_duplicate', lambda: probe.setParent(parent, parent=parent), TypeError)
            check('mesh_duplicate', lambda: obj.replaceMesh(mesh, mesh=mesh), TypeError)
            check('parent_foreign_keyword', lambda: probe.setParent(mesh=mesh), TypeError)
            check('mesh_foreign_keyword', lambda: obj.replaceMesh(parent=parent), TypeError)
            check('parent_bad_integer', lambda: probe.setParent(parent, ghost='invalid'), TypeError)
            check('mesh_bad_integer', lambda: obj.replaceMesh(mesh, usePhysicsMesh='invalid'), TypeError)
            check('parent_missing', lambda: probe.setParent(), TypeError)
            check('mesh_missing', lambda: obj.replaceMesh(), TypeError)
            check('parent_extra', lambda: probe.setParent(None, 0, 0, 0), TypeError)
            check('mesh_extra', lambda: obj.replaceMesh(mesh, 0, 0, 0), TypeError)
            check('curve_bool', lambda: probe.getCurvePoints(world=False))
            check('axis_keywords', lambda: probe.alignAxisToVect(vect=(0, 0, 1), axis=2, factor=0))
            check('look_keywords', lambda: probe.lookAt(vect=(0, 0, 1), axis=2, factor=0))
            check('ray_keywords', lambda: obj.rayCast(objto=(50, 50, 50), poly=2))
            check('bvh_keywords', lambda: mesh.constructBvh(epsilon=0))
            RESULTS['all_passed'] = all(c['passed'] for c in RESULTS['checks'].values())
            save()
        if FRAME >= 10:
            RESULTS['completed'] = True
            RESULTS['frames'] = FRAME
            save()
            Range.logic.endGame()
    except Exception:
        RESULTS['exception'] = traceback.format_exc()
        save()
        Range.logic.endGame()

def require(condition):
    assert condition
''')
    bpy.ops.wm.save_as_mainfile(filepath=scene_path, check_existing=False)
    print('PARSER_REVIEW_SAVED', scene_path)
