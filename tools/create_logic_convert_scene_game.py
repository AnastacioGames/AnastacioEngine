"""Logic Bricks -> Python: mini-jogo com os sistemas interagindo (teste integrado, sem entrada do jogador).

Run with:  AnastacioEngine -b --python tools/create_logic_convert_scene_game.py -- <output.range> [convert[:MODULE|SCRIPT]|none]

O que acontece em jogo:
- Player patrulha em dois estados (State actuator), atira (Add Object de Bullet com velocidade) e perde vida
  quando um Enemy encosta; com a vida em 0 manda "gameover" e some.
- Spawner cria um Enemy a cada 45 quadros (objeto modelo numa camada inativa, com os proprios bricks).
- Enemy persegue o Player (Steering Seek), morre ao encostar numa Bullet e avisa o placar por mensagem.
- Bullet anda para a frente e some ao acertar um Enemy ou pelo tempo de vida.
- Score conta as mortes por mensagem; ao chegar em 3 manda "levelup"; o Door toca uma acao quando recebe.
- Turret mira no Player (Track To), liga "alert" quando ele chega perto (Near) e conta por Ray quando o ve.
- Blinker troca a visibilidade a cada 20 quadros e Camera segue o Player (Camera actuator).

Rodar o .range sem e com "convert" no AnastacioRuntime grava <cena>_check_game.txt ao lado do .range (uma linha
a cada 10 quadros, ate o quadro 400, lida no fim do quadro). As duas rodadas devem dar o mesmo arquivo, e
LEFT_AS_BRICK deve ser 0. Rode os bricks duas vezes antes: se os dois arquivos nao forem iguais, a cena nao e
deterministica e nao prova nada.
"""

import bpy
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = argv[0] if argv else "logic_convert_game.range"
convert = len(argv) > 1 and argv[1].startswith("convert")
mode = argv[1].split(":", 1)[1] if convert and ":" in argv[1] else "COMPONENT"

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.world = bpy.data.worlds.new("World")
scene.game_settings.physics_gravity = 0.0
scene.layers = [i == 0 for i in range(20)]
tested = []
LAYER2 = [i == 1 for i in range(20)]


def cube(name, loc, ptype='NO_COLLISION', scale=(0.5, 0.5, 0.5), ghost=False, actor=False):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    o = bpy.context.active_object
    o.name = name
    o.scale = scale
    o.game.physics_type = ptype
    o.game.use_ghost = ghost
    o.game.use_actor = actor
    return o


def prop(o, name, type_='INT', value=0):
    scene.objects.active = o
    bpy.ops.object.game_property_new(type=type_, name=name)
    o.game.properties[name].value = value


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


def wire(o, name, sensors, actuators, ctype='LOGIC_AND', state=1):
    bpy.ops.logic.controller_add(type=ctype, name=name, object=o.name)
    c = o.game.controllers[name]
    c.states = state
    for s in sensors:
        s.link(c)
    for a in actuators:
        a.link(c)
    if o not in tested:
        tested.append(o)
    return c


def always(o, name="Tick", skip=0):
    return sensor(o, 'ALWAYS', name, use_pulse_true_level=True, tick_skip=skip)


def add(o, p, value="1", name=None):
    return actuator(o, 'PROPERTY', name or "Add_" + p, mode='ADD', property=p, value=value)


def set_state(o, name, n):
    a = actuator(o, 'STATE', name, operation='SET')
    a.states = [i == n - 1 for i in range(30)]
    return a


def slide_action(name, index, value, frames=30):
    act = bpy.data.actions.new(name)
    fc = act.fcurves.new("location", index=index)
    fc.keyframe_points.insert(1, 0.0)
    fc.keyframe_points.insert(frames, value)
    return act


cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
cam.location = (0, -5, 30)
scene.objects.link(cam)
scene.camera = cam

# --- Modelos na camada 2 (inativos): Bullet e Enemy, cada um com os proprios bricks.
bullet = cube("Bullet", (0, 0, 50), 'DYNAMIC', (1.5, 0.2, 0.2), ghost=True, actor=True)
prop(bullet, "bullet", 'BOOL', True)
wire(bullet, "Fly", [always(bullet)], [actuator(bullet, 'MOTION', "Step", offset_location=(0, 0.35, 0))])
wire(bullet, "Hit", [sensor(bullet, 'COLLISION', "OnEnemy", property="enemy")],
     [actuator(bullet, 'EDIT_OBJECT', "Die", mode='ENDOBJECT')])
bullet.layers = LAYER2

enemy = cube("Enemy", (0, 0, 60), 'DYNAMIC', (0.5, 0.5, 0.5), ghost=True, actor=True)
prop(enemy, "enemy", 'BOOL', True)
prop(enemy, "age")
wire(enemy, "Age", [always(enemy)], [add(enemy, "age")])
bpy.ops.logic.actuator_add(type='STEERING', name="Chase", object=enemy.name)
chase = enemy.game.actuators["Chase"]
chase.mode = 'SEEK'
chase.velocity = 3.5
chase.distance = 0.3
wire(enemy, "Chasing", [always(enemy, "Tick2")], [chase])
wire(enemy, "Shot", [sensor(enemy, 'COLLISION', "OnBullet", property="bullet")],
     [actuator(enemy, 'MESSAGE', "Tell", subject="kill"), actuator(enemy, 'EDIT_OBJECT', "Die", mode='ENDOBJECT')])

enemy.layers = LAYER2

# Tiro falso, sem Actor: atravessa os Enemies sem ser visto pelo Collision sensor deles.
dud = cube("Dud", (0, 0, 70), 'DYNAMIC', (1.5, 0.2, 0.2), ghost=True)
prop(dud, "bullet", 'BOOL', True)
wire(dud, "Fly", [always(dud)], [actuator(dud, 'MOTION', "Step", offset_location=(0, -0.35, 0))])
dud.layers = LAYER2

# --- Player: patrulha em dois estados, atira e perde vida.
player = cube("Player", (-6, 0, 0), 'DYNAMIC', ghost=True, actor=True)
prop(player, "player", 'BOOL', True)
prop(player, "hp", 'INT', 3)
prop(player, "shots")
prop(player, "dead", 'BOOL', False)
wire(player, "Right", [always(player, "T1")],
     [actuator(player, 'MOTION', "GoRight", offset_location=(0.08, 0, 0))], state=1)
wire(player, "ToLeft", [sensor(player, 'DELAY', "D1", delay=80)], [set_state(player, "S2", 2)], state=1)
wire(player, "Left", [always(player, "T2")],
     [actuator(player, 'MOTION', "GoLeft", offset_location=(-0.08, 0, 0))], state=2)
wire(player, "ToRight", [sensor(player, 'DELAY', "D2", delay=80)], [set_state(player, "S1", 1)], state=2)
# Tiro nos dois estados: o mesmo sensor e os mesmos actuators ligados a um controller por estado.
shoot_s = sensor(player, 'DELAY', "Reload", delay=12, duration=1, use_repeat=True)
shoot_a = actuator(player, 'EDIT_OBJECT', "Shoot", mode='ADDOBJECT', object=bullet, time=45)
shots_a = add(player, "shots")
dud_a = actuator(player, 'EDIT_OBJECT', "ShootBack", mode='ADDOBJECT', object=dud, time=45)
for st in (1, 2):
    wire(player, "Fire%d" % st, [shoot_s], [shoot_a, shots_a, dud_a], state=st)
    wire(player, "Hurt%d" % st, [sensor(player, 'COLLISION', "Touch%d" % st, property="enemy", use_tap=True)],
         [add(player, "hp", "-1", "Lose%d" % st)], state=st)
    wire(player, "Dying%d" % st,
         [sensor(player, 'PROPERTY', "NoHp%d" % st, evaluation_type='PROPLESSTHAN', property="hp", value="1")],
         [actuator(player, 'MESSAGE', "Over%d" % st, subject="gameover"),
          actuator(player, 'PROPERTY', "Dead%d" % st, mode='ASSIGN', property="dead", value="True"),
          actuator(player, 'VISIBILITY', "Hide%d" % st, use_visible=False)], state=st)
chase.target = player

# --- Spawner: um Enemy a cada 45 quadros, enquanto nao acabou o jogo.
spawner = cube("Spawner", (6, 8, 0))
prop(spawner, "made")
prop(spawner, "over", 'BOOL', False)
wire(spawner, "Spawn",
     [sensor(spawner, 'DELAY', "Every", delay=45, duration=1, use_repeat=True),
      sensor(spawner, 'PROPERTY', "Running", evaluation_type='PROPEQUAL', property="over", value="False")],
     [actuator(spawner, 'EDIT_OBJECT', "Make", mode='ADDOBJECT', object=enemy, time=0), add(spawner, "made")])
wire(spawner, "Stop", [sensor(spawner, 'MESSAGE', "GameOver", subject="gameover")],
     [actuator(spawner, 'PROPERTY', "SetOver", mode='ASSIGN', property="over", value="True")])
# Segundo ponto de criacao, atras do Player: esses Enemies chegam nele (as Bullets so vao para a frente).
back = cube("SpawnerBack", (0, -9, 0))
prop(back, "over", 'BOOL', False)
wire(back, "Spawn",
     [sensor(back, 'DELAY', "Every", delay=60, duration=1, use_repeat=True),
      sensor(back, 'PROPERTY', "Running", evaluation_type='PROPEQUAL', property="over", value="False")],
     [actuator(back, 'EDIT_OBJECT', "Make", mode='ADDOBJECT', object=enemy, time=0)])
wire(back, "Stop", [sensor(back, 'MESSAGE', "GameOver", subject="gameover")],
     [actuator(back, 'PROPERTY', "SetOver", mode='ASSIGN', property="over", value="True")])
wire(spawner, "Drift", [always(spawner)], [actuator(spawner, 'MOTION', "Side", offset_location=(-0.02, 0, 0))])

# --- Score: conta as mortes por mensagem; com 3 manda "levelup" uma vez.
score = cube("Score", (0, -10, 0))
prop(score, "kills")
prop(score, "level", 'INT', 1)
wire(score, "Count", [sensor(score, 'MESSAGE', "Kill", subject="kill")], [add(score, "kills")])
wire(score, "Level", [sensor(score, 'PROPERTY', "Three", evaluation_type='PROPEQUAL', property="kills", value="3")],
     [actuator(score, 'MESSAGE', "Up", subject="levelup"), add(score, "level")])

# --- Door: toca a acao quando chega "levelup".
door = cube("Door", (10, 0, 0), scale=(0.3, 2, 1))
prop(door, "opened")
wire(door, "Open", [sensor(door, 'MESSAGE', "LevelUp", subject="levelup")],
     [actuator(door, 'ACTION', "Rise", action=slide_action("DoorRise", 2, 4.0), frame_start=1, frame_end=30),
      add(door, "opened")])

# --- Turret: mira no Player, alerta por Near e conta por Ray.
turret = cube("Turret", (0, 6, 0), scale=(0.4, 0.8, 0.4))
prop(turret, "alert", 'BOOL', False)
prop(turret, "seen")
wire(turret, "Aim", [always(turret)],
     [actuator(turret, 'EDIT_OBJECT', "Track", mode='TRACKTO', object=player, use_3d_tracking=True, time=4)])
wire(turret, "Close", [sensor(turret, 'NEAR', "Near", property="player", distance=7.0, reset_distance=7.5)],
     [actuator(turret, 'PROPERTY', "Alert", mode='LEVEL', property="alert")])
wire(turret, "See", [sensor(turret, 'RAY', "Eye", property="player", range=12.0, axis='YAXIS',
                            use_pulse_true_level=True, tick_skip=4)], [add(turret, "seen")])

# --- Blinker e camera.
blinker = cube("Blinker", (-10, -8, 0))
prop(blinker, "on", 'BOOL', True)
wire(blinker, "Flip", [sensor(blinker, 'DELAY', "Each", delay=20, duration=1, use_repeat=True)],
     [actuator(blinker, 'PROPERTY', "Toggle", mode='TOGGLE', property="on")])
wire(blinker, "Show", [sensor(blinker, 'PROPERTY', "IsOn", evaluation_type='PROPEQUAL', property="on", value="True")],
     [actuator(blinker, 'VISIBILITY', "Vis", use_visible=True)])
wire(blinker, "HideIt",
     [sensor(blinker, 'PROPERTY', "IsOff", evaluation_type='PROPEQUAL', property="on", value="False")],
     [actuator(blinker, 'VISIBILITY', "Invis", use_visible=False)])
holder = cube("CamHolder", (0, -12, 6))
wire(holder, "Follow", [always(holder)],
     [actuator(holder, 'CAMERA', "Chase", object=player, height=4.0, min=6.0, max=10.0, damping=0.05)])

checker = bpy.data.objects.new("Checker", None)
scene.objects.link(checker)
text = bpy.data.texts.new("checker.py")
text.from_string('''
from Range import logic
cont = logic.getCurrentController()
own = cont.owner
own['frames'] = own.get('frames', 0) + 1
o = own.scene.objects
NL = chr(10)
def num(x):
    s = '%.2f' % x
    return '0.00' if s == '-0.00' else s
def v(vec):
    return ','.join(num(x) for x in vec)
def sample(n):
    p = o['Player']
    parts = ['f=%d' % n,
             'player=%s st=%d hp=%d shots=%d dead=%s vis=%s' % (v(p.worldPosition), p.state, p['hp'], p['shots'],
                                                                p['dead'], p.visible),
             'spawner=%s made=%d over=%s' % (num(o['Spawner'].worldPosition.x), o['Spawner']['made'],
                                             o['Spawner']['over']),
             'score=%d/%d door=%s/%d' % (o['Score']['kills'], o['Score']['level'], num(o['Door'].worldPosition.z),
                                         o['Door']['opened']),
             'turret=%s alert=%s seen=%d' % (v(o['Turret'].worldOrientation.col[1]), o['Turret']['alert'],
                                             o['Turret']['seen']),
             'blink=%s/%s cam=%s' % (o['Blinker']['on'], o['Blinker'].visible, v(o['CamHolder'].worldPosition))]
    for name in ('Enemy', 'Bullet'):
        found = sorted(v(x.worldPosition) for x in o if x.name == name)
        parts.append('%s:%d[%s]' % (name, len(found), ';'.join(found)))
    ages = sorted(x['age'] for x in o if x.name == 'Enemy')
    parts.append('ages=%s' % ages)
    own['log'] = own.get('log', '') + ' '.join(parts).replace(', ', ',') + NL
def after_frame():
    n = own['frames']
    if n % 10 == 0 and own.get('sampled') != n:
        own['sampled'] = n
        try:
            sample(n)
        except Exception:
            # O player nao mostra o console: grava o erro e encerra.
            import traceback
            with open(logic.expandPath('//check_game_error.txt'), 'w') as f:
                f.write(traceback.format_exc())
            logic.endGame()
if not own.get('hooked'):
    # Amostra no post_draw, depois da logica e da fisica do quadro.
    own['hooked'] = True
    own.scene.post_draw.append(after_frame)
if own['frames'] == 401:
    with open(logic.expandPath('//' + own.scene.name + '_check_game.txt'), 'w') as f:
        f.write(own.get('log', ''))
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
        # O operador so enxerga o objeto ativo numa camada visivel: os modelos voltam para a camada 2 depois.
        hidden = list(o.layers) == LAYER2
        if hidden:
            o.layers = [i in (0, 1) for i in range(20)]
        scene.objects.active = o
        print("CONVERT", o.name, bpy.ops.logic.convert_to_component(mode=mode))
        if hidden:
            o.layers = LAYER2
    for t in bpy.data.texts:
        left += [(t.name, ln.strip()) for ln in t.as_string().splitlines() if "# TODO:" in ln]
    print("LEFT_AS_BRICK", len(left), left)

bpy.ops.wm.save_as_mainfile(filepath=output)
