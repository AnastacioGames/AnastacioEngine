"""Regressao do ciclo de vida da fisica (frente 4).

AnastacioEngine.exe -b --factory-startup --python este_script -- <pasta>
AnastacioRuntime.exe --server <pasta>/fisica_<caso>.range  -> <pasta>/result_fisica_<caso>.json

Casos:
  remove_con  usar o objeto Python da constraint depois de constraints.removeConstraint(id).
  end_obj     usar a constraint depois de endObject() num dos corpos.
  veiculo     usar o veiculo depois de endObject() no chassi (controle: ja protegido).
  vivo, suspende  controles: constraint viva ou com a fisica suspensa continua funcionando.
  junta, junta_sem  Rigid Body Joint do editor segura o corpo; sem a junta ele cai.
"""
import os
import sys

import bpy

out_dir = os.path.abspath(sys.argv[sys.argv.index('--') + 1])
os.makedirs(out_dir, exist_ok=True)

COMMON = '''import json
import Range
from Range import constraints

STATE = {'frame': 0}

def done(res):
    with open(Range.logic.expandPath('//result_fisica_%s.json'), 'w') as out:
        json.dump(res, out, indent=2)
    Range.logic.endGame()

def log(*args):
    with open(Range.logic.expandPath('//log_fisica.txt'), 'a') as out:
        out.write(' '.join(str(a) for a in args) + '\\n')

def probe(obj, names):
    """Tenta ler/escrever cada atributo e devolve o resultado ou o tipo da excecao."""
    res = {}
    for name in names:
        log('probe', name)
        try:
            if name == 'set_enabled':
                obj.enabled = True
                res[name] = 'ok'
            elif name == 'getParam':
                res[name] = obj.getParam(0)
            elif name == 'setParam':
                obj.setParam(0, -1.0, 1.0)
                res[name] = 'ok'
            else:
                v = getattr(obj, name)
                res[name] = v() if callable(v) else v
        except Exception as exc:
            res[name] = type(exc).__name__
    return res

def churn():
    # Reaproveita a memoria liberada para que leitura solta mostre lixo.
    return [bytearray(96) for _ in range(20000)]

def pair():
    sc = Range.logic.getCurrentScene()
    return sc.objects['A'], sc.objects['B']
'''

# Uma excecao no script deixaria o jogo rodando para sempre: grava e encerra.
GUARD = '''
_run = run

def run(cont):
    try:
        _run(cont)
    except Exception:
        import traceback
        done({'erro': traceback.format_exc()})
'''

CON_ATTRS = ['constraint_id', 'constraint_type', 'enabled', 'breakingThreshold', 'getParam', 'set_enabled', 'setParam']

CASES = {
    'remove_con': '''
def run(cont):
    f = STATE['frame']
    STATE['frame'] += 1
    a, b = pair()
    if f == 1:
        STATE['c'] = constraints.createConstraint(a.getPhysicsId(), b.getPhysicsId(), constraints.GENERIC_6DOF_CONSTRAINT)
        STATE['id'] = STATE['c'].constraint_id
        log('criada', STATE['id'])
        constraints.removeConstraint(STATE['id'])
        log('removida')
        STATE['junk'] = churn()
    elif f == 3:
        done({'id': STATE['id'], 'depois': probe(STATE['c'], %r), 'ok': True})
''' % CON_ATTRS,
    'end_obj': '''
def run(cont):
    f = STATE['frame']
    STATE['frame'] += 1
    if f == 1:
        a, b = pair()
        STATE['c'] = constraints.createConstraint(a.getPhysicsId(), b.getPhysicsId(), constraints.GENERIC_6DOF_CONSTRAINT)
        STATE['id'] = STATE['c'].constraint_id
        b.endObject()
    elif f == 2:
        STATE['junk'] = churn()
    elif f == 4:
        done({'id': STATE['id'], 'depois': probe(STATE['c'], %r), 'ok': True})
''' % CON_ATTRS,
    'vivo': '''
def run(cont):
    f = STATE['frame']
    STATE['frame'] += 1
    a, b = pair()
    if f == 1:
        STATE['c'] = constraints.createConstraint(a.getPhysicsId(), b.getPhysicsId(), constraints.GENERIC_6DOF_CONSTRAINT)
        STATE['junk'] = churn()
    elif f == 3:
        done({'depois': probe(STATE['c'], %r), 'ok': True})
''' % CON_ATTRS,
    'suspende': '''
def run(cont):
    f = STATE['frame']
    STATE['frame'] += 1
    a, b = pair()
    if f == 1:
        STATE['c'] = constraints.createConstraint(a.getPhysicsId(), b.getPhysicsId(), constraints.GENERIC_6DOF_CONSTRAINT)
        b.suspendPhysics()
    elif f == 3:
        STATE['suspensa'] = probe(STATE['c'], ['constraint_type', 'enabled'])
        b.restorePhysics()
    elif f == 5:
        done({'suspensa': STATE['suspensa'], 'restaurada': probe(STATE['c'], ['constraint_type', 'enabled']), 'ok': True})
''',
    'junta': '''
def run(cont):
    f = STATE['frame']
    STATE['frame'] += 1
    if f == 90:
        a, b = pair()
        done({'zA': round(a.worldPosition.z, 2), 'zB': round(b.worldPosition.z, 2), 'ok': True})
''',
    'veiculo': '''
def run(cont):
    f = STATE['frame']
    STATE['frame'] += 1
    if f == 1:
        a, b = pair()
        STATE['v'] = constraints.createVehicle(b.getPhysicsId())
        b.endObject()
    elif f == 2:
        STATE['junk'] = churn()
    elif f == 4:
        done({'depois': probe(STATE['v'], ['constraint_id', 'getNumWheels']), 'ok': True})
''',
}

# Controle da junta: mesma cena sem a constraint, B precisa cair.
CASES['junta_sem'] = CASES['junta']

for case, body in CASES.items():
    bpy.ops.wm.read_factory_settings()
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_GAME'
    scene.name = 'Main'
    for ob in list(scene.objects):
        if ob.type == 'MESH':
            scene.objects.unlink(ob)
    for name, z in (('A', 2.0), ('B', 4.0)):
        bpy.ops.mesh.primitive_cube_add(location=(0.0, 0.0, z))
        ob = bpy.context.object
        ob.name = name
        ob.game.physics_type = 'RIGID_BODY'
    if case in ('junta', 'junta_sem'):
        # A parado no alto segura B por uma junta ponto a ponto: B deve ficar pendurado.
        a = scene.objects['A']
        a.location.z = 6.0
        a.game.physics_type = 'STATIC'
        scene.objects['B'].location.z = 3.0
    if case == 'junta':
        con = a.constraints.new('RIGID_BODY_JOINT')
        con.target = scene.objects['B']
        con.pivot_type = 'BALL'
        con.pivot_z = -3.0
    bpy.ops.mesh.primitive_plane_add(radius=10.0)
    ground = bpy.context.object
    ground.name = 'Chao'
    scene.objects.active = ground
    text = bpy.data.texts.new('fisica_review.py')
    text.write(COMMON % case + body + GUARD)
    bpy.ops.logic.sensor_add(type='ALWAYS', object=ground.name)
    bpy.ops.logic.controller_add(type='PYTHON', object=ground.name)
    sens = ground.game.sensors[-1]
    sens.use_pulse_true_level = True
    cont = ground.game.controllers[-1]
    cont.mode = 'MODULE'
    cont.module = 'fisica_review.run'
    sens.link(cont)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out_dir, 'fisica_%s.range' % case))
