"""Logic Bricks -> Python: Steering actuator (Seek, Flee, Path Following) no jogo, bricks x convertido.

Run with:  AnastacioEngine -b --python tools/create_logic_convert_scene_steering.py -- <output.range> [convert[:MODULE|SCRIPT]]
Cada objeto de teste tem os proprios bricks; com "convert" todos sao convertidos. Rodar o .range sem e com
"convert" no AnastacioRuntime grava <cena>_check_steering.txt ao lado do .range: uma linha por amostra (a cada 20
quadros, ate o quadro 200) com posicao, orientacao (matriz 3x3) e velocidade linear de cada objeto.
As duas rodadas devem dar o mesmo arquivo, e LEFT_AS_BRICK deve ser 0.

acceleration / turn_speed ficam fora do padrao de proposito: sem simulacao de obstaculos a engine nao os usa
(KX_SteeringActuator::Update so os passa para AdjustObstacleVelocity), entao nao podem mudar o resultado.
"""
import bpy
import sys
from math import radians

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = argv[0] if argv else "logic_convert_steering.range"
convert = len(argv) > 1 and argv[1].startswith("convert")
mode = argv[1].split(":", 1)[1] if convert and ":" in argv[1] else "COMPONENT"

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.world = bpy.data.worlds.new("World")
tested = []
sampled = []


def cube(name, loc, ptype='NO_COLLISION', scale=(1, 1, 1), sample=True):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    o = bpy.context.active_object
    o.name = name
    o.scale = scale
    o.game.physics_type = ptype
    if sample:
        sampled.append(name)
    return o


def sensor(o, type_, name, **kw):
    bpy.ops.logic.sensor_add(type=type_, name=name, object=o.name)
    s = o.game.sensors[name]
    for k, v in kw.items():
        setattr(s, k, v)
    return s


def actuator(o, type_, name, **kw):
    bpy.ops.logic.actuator_add(type=type_, name=name, object=o.name)
    a = o.game.actuators[name]
    for k, v in kw.items():
        setattr(a, k, v)
    return a


def wire(o, name, sensors, actuators):
    bpy.ops.logic.controller_add(type='LOGIC_AND', name=name, object=o.name)
    c = o.game.controllers[name]
    for s in sensors:
        s.link(c)
    for a in actuators:
        a.link(c)
    if o not in tested:
        tested.append(o)


def once(o, name="Once"):
    return sensor(o, 'ALWAYS', name)


def always(o, name="Tick"):
    return sensor(o, 'ALWAYS', name, use_pulse_true_level=True)


def window(o, name, start, length, repeat=False):
    """Delay: positivo de 'start' ate 'start + length' quadros (pulsos positivo e negativo)."""
    return sensor(o, 'DELAY', name, delay=start, duration=length, use_repeat=repeat)


def steer(o, name, target, mode_='SEEK', **kw):
    # acceleration / turn_speed fora do padrao: nao devem ter efeito sem simulacao de obstaculos.
    cfg = dict(mode=mode_, target=target, distance=1.5, velocity=3.0, acceleration=7.5, turn_speed=33.0,
               self_terminated=False, facing=False)
    cfg.update(kw)
    return actuator(o, 'STEERING', name, **cfg)


cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
cam.location = (0, 0, 60)
scene.objects.link(cam)
scene.camera = cam
cube("Floor", (0, 60, -1), 'STATIC', (60, 10, 1), sample=False)

# Alvos. Runner anda sempre e Jumper troca de lugar no quadro 90, os dois movidos pelo script do Checker
# (controller Python, nunca convertido): assim o alvo esta no mesmo lugar nas duas rodadas quando o Steering
# roda. Movidos por um Motion de outro objeto, a ordem entre objetos muda (bricks: ordem de ativacao dos
# actuators; componentes: ordem dos objetos) e o Steering ve o alvo com um quadro de diferenca.
goal = cube("Goal", (8, 0, 4), sample=False)
runner = cube("Runner", (-30, 20, 0))
jumper = cube("Jumper", (-30, 30, 0))
floor_goal = cube("FloorGoal", (20, 62, 0.5), sample=False)

# --- Seek 3D sem fisica: sobe ate o alvo, vira o eixo Y, para sozinho na distancia.
o = cube("SeekY", (0, 0, 0))
wire(o, "Go", [once(o)], [steer(o, "Seek", goal, facing=True, facing_axis='Y', self_terminated=True)])

# --- Um objeto por eixo de facing (X, Z e os tres negativos), alvo mais alto: matriz nao ortogonal nos X.
for i, axis in enumerate(('X', 'Z', 'NEG_X', 'NEG_Y', 'NEG_Z')):
    o = cube("Face" + axis, (-10, -20 + 4 * i, 0))
    wire(o, "Go", [once(o)], [steer(o, "Seek", goal, facing=True, facing_axis=axis, velocity=2.0, distance=3.0)])

# --- Seek sem facing, pulso ligado e auto termino, alvo que anda: termina e recomeca varias vezes.
o = cube("Chaser", (-34, 18, 0))
wire(o, "Go", [always(o)], [steer(o, "Seek", runner, self_terminated=True, velocity=4.0, distance=2.0)])

# --- Mesmo caso com sensor sem pulso: depois de terminar nao volta mais.
o = cube("ChaserOnce", (-34, 22, 1))
wire(o, "Go", [once(o)], [steer(o, "Seek", runner, self_terminated=True, velocity=4.0, distance=2.0,
                                facing=True, facing_axis='Y')])

# --- Seek com auto termino e pulso a cada 3 quadros (tick skip 2), alvo que muda de lugar no quadro 90.
# Depende da fase do pulso: a engine pulsa nos quadros 1, 4, 7...; se o convertido pulsar em outra fase
# (self._tick), o Hopper sai um quadro atrasado depois do quadro 90.
o = cube("Hopper", (-33, 30, 0))
wire(o, "Go", [sensor(o, 'ALWAYS', "Tick", use_pulse_true_level=True, tick_skip=2)],
     [steer(o, "Seek", jumper, self_terminated=True, velocity=5.0, distance=1.0, facing=True, facing_axis='X')])

# --- Flee sem fisica: foge enquanto estiver a menos de 6; sem auto termino.
o = cube("FleeZ", (9, 1, 0))
wire(o, "Go", [once(o)], [steer(o, "Flee", goal, 'FLEE', distance=6.0, facing=True, facing_axis='Z')])

# --- Flee com auto termino e pulso, de um alvo que chega perto (Runner): comeca fora do alcance.
o = cube("FleePulse", (-26, 21, 0))
wire(o, "Go", [always(o)], [steer(o, "Flee", runner, 'FLEE', distance=3.0, velocity=2.0, self_terminated=True,
                                  facing=True, facing_axis='NEG_Y')])

# --- Janela de pulso: liga no quadro 30, desliga no 90 e repete (quadro de parada e reativacao).
o = cube("Window", (-20, -30, 0))
wire(o, "Go", [window(o, "On", 30, 60, True)], [steer(o, "Seek", goal, velocity=2.5, facing=True, facing_axis='Y')])

# --- Dinamicos no chao: Z da velocidade livre e travado, com e sem facing.
o = cube("DynFree", (-20, 58, 3), 'DYNAMIC')
wire(o, "Go", [once(o)], [steer(o, "Seek", floor_goal, velocity=3.0, lock_z_velocity=False)])
o = cube("DynLock", (-20, 62, 3), 'DYNAMIC')
wire(o, "Go", [once(o)], [steer(o, "Seek", floor_goal, velocity=3.0, lock_z_velocity=True, self_terminated=True)])
o = cube("DynFace", (-20, 66, 0.5), 'DYNAMIC')
wire(o, "Go", [once(o)], [steer(o, "Seek", floor_goal, velocity=2.0, lock_z_velocity=False, facing=True,
                                facing_axis='NEG_X')])
o = cube("DynFlee", (18, 56, 0.5), 'RIGID_BODY')
wire(o, "Go", [once(o)], [steer(o, "Flee", floor_goal, 'FLEE', velocity=2.0, distance=9.0, lock_z_velocity=True,
                                self_terminated=True)])

# --- Dinamico com a dinamica suspensa do quadro 60 ao 120: nesse trecho a engine anda por ApplyMovement.
o = cube("DynSusp", (-20, 54, 0.5), 'DYNAMIC')
wire(o, "Go", [once(o)], [steer(o, "Seek", floor_goal, velocity=2.0, lock_z_velocity=False)])
wire(o, "Susp", [window(o, "At60", 60, 3)], [actuator(o, 'EDIT_OBJECT', "Suspend", mode='DYNAMICS',
                                                      dynamic_operation='SUSPENDDYN')])
wire(o, "Rest", [window(o, "At120", 120, 3)], [actuator(o, 'EDIT_OBJECT', "Restore", mode='DYNAMICS',
                                                       dynamic_operation='RESTOREDYN')])

# --- Filho de um pai girado que tambem gira: a orientacao local desconta o pai.
parent = cube("Parent", (20, -20, 0))
parent.rotation_euler = (0, 0, radians(30))
wire(parent, "Go", [always(parent)], [actuator(parent, 'MOTION', "Spin", offset_rotation=(0, 0, 0.01))])
o = cube("Child", (24, -20, 0))
o.parent = parent
wire(o, "Go", [window(o, "On", 20, 100)], [steer(o, "Seek", goal, velocity=2.0, facing=True, facing_axis='Y')])

# --- Path Following num navmesh plano (um quadrado de 2 triangulos), com periodo de atualizacao de 500 ms.
bpy.ops.mesh.primitive_plane_add(radius=10, location=(40, 0, 0))
nav = bpy.context.active_object
nav.name = "Nav"
nav.game.physics_type = 'NAVMESH'
nav_goal = cube("NavGoal", (47, 6, 0.5), sample=False)
o = cube("Walker", (33, -6, 0.5))
wire(o, "Go", [once(o)], [steer(o, "Path", nav_goal, 'PATHFOLLOWING', navmesh=nav, velocity=3.0, distance=1.0,
                                update_period=500, facing=True, facing_axis='Y', self_terminated=True)])

checker = bpy.data.objects.new("Checker", None)
scene.objects.link(checker)
text = bpy.data.texts.new("checker.py")
text.from_string(('NAMES = %r' % (sampled,)) + '''
from Range import logic
from mathutils import Vector
import traceback
try:
    cont = logic.getCurrentController()
    own = cont.owner
    own['frames'] = own.get('frames', 0) + 1
    n = own['frames']
    o = own.scene.objects
    o['Runner'].worldPosition += Vector((0.03, 0.01, 0.0))
    if n == 90:
        o['Jumper'].worldPosition = (-22.0, 36.0, 2.0)
    if n % 20 == 0:
        # round + 0.0: -0.00001 e 0.00001 (ruido de float32 x double) viram o mesmo 0.000.
        v = lambda vec: ','.join('%.3f' % (round(x, 3) + 0.0) for x in vec)
        for name in NAMES:
            ob = o[name]
            m = ob.worldOrientation
            own['log'] = own.get('log', '') + 'f=%d %s pos=%s rot=%s|%s|%s vel=%s\\n' % (
                n, name, v(ob.worldPosition), v(m[0]), v(m[1]), v(m[2]),
                v(ob.worldLinearVelocity) if ob.getPhysicsId() else '-')
    if n == 200:
        with open(logic.expandPath('//' + own.scene.name + '_check_steering.txt'), 'w', encoding='utf-8') as f:
            f.write(own['log'])
        logic.endGame()
except Exception:
    # Sem console no player: o erro vai para um arquivo ao lado do .range e o jogo termina.
    with open(logic.expandPath('//check_steering_error.txt'), 'w', encoding='utf-8') as f:
        f.write(traceback.format_exc())
    logic.endGame()
''')
bpy.ops.logic.sensor_add(type='ALWAYS', name="Frame", object=checker.name)
checker.game.sensors["Frame"].use_pulse_true_level = True
bpy.ops.logic.controller_add(type='PYTHON', name="Check", object=checker.name)
checker.game.controllers["Check"].text = text
checker.game.sensors["Frame"].link(checker.game.controllers["Check"])

if convert:
    left = []
    for o in tested:
        scene.objects.active = o
        print("CONVERT", o.name, bpy.ops.logic.convert_to_component(mode=mode))
    for t in bpy.data.texts:
        left += [(t.name, ln.strip()) for ln in t.as_string().splitlines() if "# TODO:" in ln]
    print("LEFT_AS_BRICK", len(left), left)

bpy.ops.wm.save_as_mainfile(filepath=output)
