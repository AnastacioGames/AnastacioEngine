"""Regressao do LibLoad/LibFree (frente 5).

AnastacioEngine.exe -b --factory-startup --python este_script -- <pasta>
AnastacioRuntime.exe --server <pasta>/libload_<caso>.range  -> <pasta>/result_libload_<caso>.json

Casos:
  duplo      LibFree chamado 2x no mesmo frame (antes: liberava a mesma Main duas vezes).
  livre_async LibFree durante LibLoad assincrono (antes: pedido descartado, biblioteca ficava carregada).
  remove_cena cena alvo de LibLoad assincrono removida antes do merge (antes: merge em cena liberada).
"""
import os
import sys

import bpy

out_dir = os.path.abspath(sys.argv[sys.argv.index('--') + 1])
os.makedirs(out_dir, exist_ok=True)


def reset():
    bpy.ops.wm.read_factory_settings()
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_GAME'
    return scene


# Biblioteca: muitos objetos com material proprio, para o merge assincrono durar alguns frames.
scene = reset()
scene.name = 'Lib'
for ob in list(scene.objects):
    scene.objects.unlink(ob)
for i in range(150):
    bpy.ops.mesh.primitive_cube_add(location=(i % 15 * 3.0, i // 15 * 3.0, 0.0))
    mat = bpy.data.materials.new('mat_%d' % i)
    mat.diffuse_color = (i / 150.0, 0.5, 1.0 - i / 150.0)
    bpy.context.object.data.materials.append(mat)
bpy.ops.object.lamp_add(type='POINT', location=(0, 0, 5))
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out_dir, 'libload_lib.range'))

COMMON = '''import json
import Range

LIB = Range.logic.expandPath('//libload_lib.range')
STATE = {'frame': 0}

def log(*args):
    with open(Range.logic.expandPath('//log_libload.txt'), 'a') as out:
        out.write(' '.join(str(a) for a in args) + '\\n')

def done(res):
    res['libs'] = [p for p in Range.logic.LibList() if 'libload_lib' in p]
    with open(Range.logic.expandPath('//result_libload_%s.json'), 'w') as out:
        json.dump(res, out, indent=2)
    Range.logic.endGame()
'''

CASES = {
    'duplo': '''
def run(cont):
    f = STATE['frame']
    STATE['frame'] += 1
    if f == 0:
        Range.logic.LibLoad(LIB, 'Scene')
    elif f == 2:
        STATE['a'] = Range.logic.LibFree(LIB)
        STATE['b'] = Range.logic.LibFree(LIB)
    elif f == 6:
        done({'free1': STATE['a'], 'free2': STATE['b'], 'ok': True})
''',
    'controle': '''
def run(cont):
    f = STATE['frame']
    STATE['frame'] += 1
    if f == 0:
        STATE['st'] = Range.logic.LibLoad(LIB, 'Scene', asynchronous=True)
    if f % 30 == 0:
        log('[libload] frame', f, 'progress', STATE['st'].progress, 'finished', STATE['st'].finished)
    if STATE['st'].finished or f > 300:
        done({'finished': STATE['st'].finished, 'frame': f})
''',
    'livre_async': '''
def run(cont):
    f = STATE['frame']
    STATE['frame'] += 1
    if f == 0:
        # O status some junto com a biblioteca liberada: o teste so olha o LibList.
        Range.logic.LibLoad(LIB, 'Scene', asynchronous=True)
        STATE['free'] = Range.logic.LibFree(LIB)
    elif not any('libload_lib' in p for p in Range.logic.LibList()):
        done({'free': STATE['free'], 'liberada_no_frame': f, 'ok': True})
    elif f > 900:
        done({'timeout': True})
''',
    'remove_cena': '''
def run(cont):
    f = STATE['frame']
    STATE['frame'] += 1
    if f == 0:
        Range.logic.addScene('B', 1)
    elif f == 120:
        names = [s.name for s in Range.logic.getSceneList()]
        done({'cenas': names, 'ok': True})

def run_b(cont):
    sc = Range.logic.getCurrentScene()
    n = sc.get('n', 0)
    sc['n'] = n + 1
    if n == 0:
        sc['st'] = Range.logic.LibLoad(LIB, 'Scene', asynchronous=True)
    elif sc['st'].progress > 0.0 and not sc['st'].finished:
        log('[libload] removendo B com progress', sc['st'].progress)
        sc.end()
    elif sc['st'].finished:
        log('[libload] terminou antes de remover B')
        sc.end()
''',
}


def add_logic(obj, module):
    bpy.context.scene.objects.active = obj
    bpy.ops.logic.sensor_add(type='ALWAYS', object=obj.name)
    bpy.ops.logic.controller_add(type='PYTHON', object=obj.name)
    sens = obj.game.sensors[-1]
    sens.use_pulse_true_level = True
    cont = obj.game.controllers[-1]
    cont.mode = 'MODULE'
    cont.module = module
    sens.link(cont)


for case, body in CASES.items():
    scene = reset()
    scene.name = 'Main'
    text = bpy.data.texts.new('libload_review.py')
    text.write(COMMON % case + body)
    add_logic(scene.objects['Cube'], 'libload_review.run')
    if case == 'remove_cena':
        bpy.ops.scene.new(type='NEW')
        b = bpy.context.scene
        b.name = 'B'
        b.render.engine = 'BLENDER_GAME'
        bpy.ops.mesh.primitive_cube_add()
        add_logic(bpy.context.object, 'libload_review.run_b')
        bpy.context.screen.scene = bpy.data.scenes['Main']
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out_dir, 'libload_%s.range' % case))
