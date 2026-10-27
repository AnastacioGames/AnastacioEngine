"""Regressao de callbacks de colisao e personagem (frente 4).

AnastacioEngine.exe -b --factory-startup --python este_script -- <pasta>
AnastacioRuntime.exe --server <pasta>/colisao_<caso>.range  -> <pasta>/result_colisao_<caso>.json

Casos (cubo A cai sobre o Chao; os dois tem collisionCallbacks):
  suspende   callback de A chama A.suspendPhysics(); o callback do Chao le os pontos de contato depois.
  end_ambos  callback de A remove A e o Chao no mesmo frame.
  add_obj    callback adiciona objetos novos com fisica a cada contato.
  char_end   personagem (Character) removido logo depois de jump() e walkDirection.
  char_susp  personagem suspenso e restaurado; continua andando.
"""
import os
import sys

import bpy

out_dir = os.path.abspath(sys.argv[sys.argv.index('--') + 1])
os.makedirs(out_dir, exist_ok=True)

COMMON = '''import json
import Range

STATE = {'frame': 0, 'hits': []}

def done(res):
    with open(Range.logic.expandPath('//result_colisao_%s.json'), 'w') as out:
        json.dump(res, out, indent=2)
    Range.logic.endGame()

def log(*args):
    with open(Range.logic.expandPath('//log_colisao.txt'), 'a') as out:
        out.write(' '.join(str(a) for a in args) + '\\n')

def objs():
    return Range.logic.getCurrentScene().objects

def contact(name, points):
    res = []
    for p in points:
        res.append([round(v, 2) for v in p.localPointA] + [round(p.appliedImpulse, 2)])
    return res
'''

GUARD = '''
_run = run

def run(cont):
    try:
        _run(cont)
    except Exception:
        import traceback
        done({'erro': traceback.format_exc()})
'''

CASES = {
    'suspende': '''
# O primeiro callback do par suspende A; o segundo ainda le os pontos de contato.
def cb(me):
    def f(other, point, normal, points):
        STATE['hits'].append((me, other.name, [round(v, 2) for v in point], [round(v, 2) for v in normal],
                              len(points), contact(me, points)))
        if not STATE.get('susp'):
            STATE['susp'] = me
            objs()['A'].suspendPhysics()
    return f

def run(cont):
    f = STATE['frame']
    STATE['frame'] += 1
    if f == 0:
        objs()['A'].collisionCallbacks.append(cb('A'))
        objs()['Chao'].collisionCallbacks.append(cb('Chao'))
    elif STATE['hits'] and f > STATE.setdefault('fim', f + 5):
        done({'suspendeu_em': STATE['susp'], 'hits': STATE['hits'][:4], 'ok': True})
    elif f > 300:
        done({'timeout': True})
''',
    'end_ambos': '''
def cb_a(other, point, normal, points):
    STATE['hits'].append(other.name)
    objs()['A'].endObject()
    other.endObject()
    other.endObject()

def run(cont):
    f = STATE['frame']
    STATE['frame'] += 1
    if f == 0:
        objs()['A'].collisionCallbacks.append(cb_a)
        objs()['Chao'].collisionCallbacks.append(lambda o, *a: STATE['hits'].append('chao:' + o.name))
    elif STATE['hits'] and f > STATE.setdefault('fim', f + 5):
        done({'hits': STATE['hits'], 'resta': sorted(o.name for o in objs()), 'ok': True})
    elif f > 300:
        done({'timeout': True})
''',
    'add_obj': '''
def cb_a(other, point, normal, points):
    STATE['hits'].append(other.name)
    if len(STATE['hits']) < 200:
        n = Range.logic.getCurrentScene().addObject('B', objs()['A'], 60)
        n.worldPosition.z += 3.0

def run(cont):
    f = STATE['frame']
    STATE['frame'] += 1
    if f == 0:
        objs()['A'].collisionCallbacks.append(cb_a)
    elif f == 240:
        done({'hits': len(STATE['hits']), 'objs': len(objs()), 'ok': True})
''',
    'char_end': '''
def run(cont):
    f = STATE['frame']
    STATE['frame'] += 1
    c = objs().get('P')
    if f == 30:
        ch = Range.constraints.getCharacter(c)
        log('char', ch)
        ch.jump()
        ch.walkDirection = [0.05, 0.0, 0.0]
        STATE['ch'] = ch
        c.endObject()
        log('endObject')
    elif f == 31:
        log('frame 31')
    elif f == 32:
        res = {}
        for name in ('onGround', 'jumpCount', 'walkDirection'):
            log('probe', name)
            try:
                res[name] = str(getattr(STATE['ch'], name))
            except Exception as exc:
                res[name] = type(exc).__name__
        done({'depois': res, 'ok': True})
''',
    'char_susp': '''
def run(cont):
    f = STATE['frame']
    STATE['frame'] += 1
    c = objs()['P']
    ch = Range.constraints.getCharacter(c)
    if f == 30:
        ch.walkDirection = [0.05, 0.0, 0.0]
        STATE['x0'] = c.worldPosition.x
        c.suspendPhysics()
    elif f == 40:
        STATE['x_susp'] = round(c.worldPosition.x - STATE['x0'], 2)
        c.restorePhysics()
        ch.walkDirection = [0.05, 0.0, 0.0]
    elif f == 70:
        done({'andou_suspenso': STATE['x_susp'], 'andou_depois': round(c.worldPosition.x - STATE['x0'], 2),
              'onGround': ch.onGround, 'ok': True})
''',
}

for case, body in CASES.items():
    bpy.ops.wm.read_factory_settings()
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_GAME'
    scene.name = 'Main'
    for ob in list(scene.objects):
        if ob.type == 'MESH':
            scene.objects.unlink(ob)
    bpy.ops.mesh.primitive_plane_add(radius=10.0)
    ground = bpy.context.object
    ground.name = 'Chao'
    if case.startswith('char'):
        bpy.ops.mesh.primitive_cube_add(location=(0.0, 0.0, 1.0))
        p = bpy.context.object
        p.name = 'P'
        p.game.physics_type = 'CHARACTER'
    else:
        for name, z, layer in (('A', 3.0, 0), ('B', 3.0, 1)):
            bpy.ops.mesh.primitive_cube_add(location=(0.0, 0.0, z))
            ob = bpy.context.object
            ob.name = name
            ob.game.physics_type = 'RIGID_BODY'
            if layer:
                ob.layers = [i == layer for i in range(20)]
    # A logica fica num Empty: o caso end_ambos remove o Chao.
    bpy.ops.object.empty_add(location=(0.0, 0.0, -5.0))
    logic = bpy.context.object
    logic.name = 'Logica'
    scene.objects.active = logic
    text = bpy.data.texts.new('colisao_review.py')
    text.write(COMMON % case + body + GUARD)
    bpy.ops.logic.sensor_add(type='ALWAYS', object=logic.name)
    bpy.ops.logic.controller_add(type='PYTHON', object=logic.name)
    sens = logic.game.sensors[-1]
    sens.use_pulse_true_level = True
    cont = logic.game.controllers[-1]
    cont.mode = 'MODULE'
    cont.module = 'colisao_review.run'
    sens.link(cont)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out_dir, 'colisao_%s.range' % case))
