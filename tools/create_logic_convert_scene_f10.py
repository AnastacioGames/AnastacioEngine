"""Logic Bricks -> Python F10: quando o controller dispara os actuators. Tap em qualquer sensor, pulso no
nivel falso, Skip, Delta Time, re-disparo quando outro sensor do mesmo controller muda, sensor de pulso ligado
a dois controllers e bricks desativados (sensor, controller e actuator).

Run with:  AnastacioEngine -b --python tools/create_logic_convert_scene_f10.py -- <output.range> [convert[:MODULE|SCRIPT]|none [post] [twice]]
Cada objeto conta os disparos numa propriedade "n" (Property Add). Rodar o .range sem e com "convert" no
AnastacioRuntime grava <cena>_check_f10.txt ao lado do .range (uma linha a cada 10 quadros, ate o quadro 200).
As duas rodadas devem dar o mesmo arquivo, e LEFT_AS_BRICK deve ser 0. "twice" converte cada objeto duas
vezes seguidas (a segunda conversao tem que reativar os bricks que a primeira desativou).
"""

import bpy
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = argv[0] if argv else "logic_convert_f7.range"
convert = len(argv) > 1 and argv[1].startswith("convert")
mode = argv[1].split(":", 1)[1] if convert and ":" in argv[1] else "COMPONENT"
post = int("post" in argv[2:])

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.world = bpy.data.worlds.new("World")
tested = []


def cube(name, loc, ptype='NO_COLLISION', scale=(1, 1, 1)):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    o = bpy.context.active_object
    o.name = name
    o.scale = scale
    o.game.physics_type = ptype
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


def wire(o, name, sensors, actuators, ctype='LOGIC_AND'):
    bpy.ops.logic.controller_add(type=ctype, name=name, object=o.name)
    c = o.game.controllers[name]
    for s in sensors:
        s.link(c)
    for a in actuators:
        a.link(c)
    if o not in tested:
        tested.append(o)


def always(o, name="Tick"):
    return sensor(o, 'ALWAYS', name, use_pulse_true_level=True)


def window(o, name, start, length, repeat=False):
    """Delay: positivo de 'start' ate 'start + length' quadros (pulsos positivo e negativo)."""
    return sensor(o, 'DELAY', name, delay=start, duration=length, use_repeat=repeat)


cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
cam.location = (0, 0, 20)
scene.objects.link(cam)
scene.camera = cam
names = []


def counter(name, props=("n",)):
    o = cube(name, (len(names) * 3 - 20, 0, 0))
    for p in props:
        prop(o, p)
    names.append((name, props))
    return o


def add(o, p="n", name=None):
    return actuator(o, 'PROPERTY', name or "Add_" + p, mode='ADD', property=p, value="1")


# --- Tap: um disparo por vez que o sensor liga; o Motion continuo so anda 1 quadro por vez.
o = counter("TapDelay")
wire(o, "Go", [sensor(o, 'DELAY', "W", delay=10, duration=20, use_repeat=True, use_tap=True)],
     [add(o), actuator(o, 'MOTION', "Step", offset_location=(0, 0.5, 0))])
o = counter("TapAlways")
wire(o, "Go", [sensor(o, 'ALWAYS', "T", use_pulse_true_level=True, use_tap=True)], [add(o)])
o = counter("TapInvert")
wire(o, "Go", [sensor(o, 'DELAY', "W", delay=15, duration=25, use_repeat=True, use_tap=True, invert=True)],
     [add(o)])
o = counter("TapProp", ("n", "sw"))
wire(o, "Flip", [sensor(o, 'DELAY', "W", delay=12, duration=18, use_repeat=True)],
     [actuator(o, 'PROPERTY', "On", mode='TOGGLE', property="sw")])
wire(o, "Go", [sensor(o, 'PROPERTY', "IsOn", property="sw", value="1", use_tap=True)], [add(o)])

# --- Pulso no nivel falso (com NAND o controller fica positivo enquanto o sensor esta falso).
o = counter("FalsePulse")
wire(o, "Go", [sensor(o, 'DELAY', "W", delay=20, duration=30, use_repeat=True, use_pulse_false_level=True,
                      tick_skip=3)], [add(o)], 'LOGIC_NAND')
o = counter("BothPulse")
wire(o, "Go", [sensor(o, 'DELAY', "W", delay=20, duration=30, use_repeat=True, use_pulse_false_level=True,
                      use_pulse_true_level=True, tick_skip=2)], [add(o)], 'LOGIC_OR')
o = counter("InvPulse")
wire(o, "Go", [sensor(o, 'DELAY', "W", delay=20, duration=30, use_repeat=True, invert=True,
                      use_pulse_true_level=True, tick_skip=2)], [add(o)])

# --- Outro sensor do mesmo controller muda enquanto o controller continua positivo: dispara de novo.
o = counter("OrRefire")
wire(o, "Go", [sensor(o, 'DELAY', "A", delay=10, duration=80), sensor(o, 'DELAY', "B", delay=30, duration=10),
               sensor(o, 'DELAY', "C", delay=50, duration=100)], [add(o)], 'LOGIC_OR')
o = counter("AndPulse")
wire(o, "Go", [sensor(o, 'ALWAYS', "T", use_pulse_true_level=True, tick_skip=4),
               sensor(o, 'DELAY', "W", delay=22, duration=41, use_repeat=True)], [add(o)])

# --- Um sensor de pulso ligado a dois controllers: a contagem do Skip e do sensor, nao de cada controller.
o = counter("Shared", ("n", "m"))
s = sensor(o, 'ALWAYS', "T", use_pulse_true_level=True, tick_skip=2)
wire(o, "One", [s], [add(o, "n")])
wire(o, "Two", [s, sensor(o, 'DELAY', "W", delay=30, duration=60)], [add(o, "m")])

# --- Skip em segundos (Delta Time).
o = counter("DtPulse")
wire(o, "Go", [sensor(o, 'ALWAYS', "T", use_pulse_true_level=True, use_dt=True, tick_skip_dt=0.25)], [add(o)])

# --- Bricks desativados nao existem em jogo.
o = counter("Inactive", ("n", "m", "k"))
off = sensor(o, 'DELAY', "Never", delay=5000, duration=10)
off.active = False
wire(o, "Go", [sensor(o, 'ALWAYS', "T", use_pulse_true_level=True, tick_skip=5), off],
     [add(o, "n"), add(o, "m", "AddOff")])
o.game.actuators["AddOff"].active = False
wire(o, "Dead", [sensor(o, 'ALWAYS', "T2", use_pulse_true_level=True)], [add(o, "k")])
o.game.controllers["Dead"].active = False

# --- Property Assign em propriedade de texto: o valor e uma expressao (aspas, inteiro, outra propriedade).
o = counter("StrAssign", ())
prop(o, "s", 'STRING', "a")
prop(o, "src", 'STRING', "zz")
names[-1] = ("StrAssign", ("s",))
for i, value in enumerate(('"hello"', '7', 'src')):
    wire(o, "Set%d" % i, [sensor(o, 'DELAY', "W%d" % i, delay=20 + 40 * i, duration=5)],
         [actuator(o, 'PROPERTY', "Assign%d" % i, mode='ASSIGN', property="s", value=value)])

checker = bpy.data.objects.new("Checker", None)
scene.objects.link(checker)
text = bpy.data.texts.new("checker.py")
text.from_string(('POST = %d\nNAMES = %r' % (post, names)) + """
from Range import logic
cont = logic.getCurrentController()
own = cont.owner
own['frames'] = own.get('frames', 0) + 1
n = own['frames']
o = own.scene.objects
def sample(n):
    parts = ['f=%d' % n]
    for name, props in NAMES:
        parts.append('%s=%s' % (name, '/'.join(str(o[name][p]) for p in props)))
    parts.append('tapy=%.2f' % o['TapDelay'].worldPosition.y)
    own['log'] = own.get('log', '') + ' '.join(parts) + '\\n'
def after_frame():
    n = own['frames']
    if n % 10 == 0 and own.get('sampled') != n:
        own['sampled'] = n
        try:
            sample(n)
        except Exception:
            # O player nao mostra o console: grava o erro e encerra.
            import traceback
            with open(logic.expandPath('//check_f10_error.txt'), 'w') as f:
                f.write(traceback.format_exc())
            logic.endGame()
if POST:
    # Amostra depois da logica e da fisica do quadro: nao depende de quem roda antes do Checker.
    if not own.get('hooked'):
        own['hooked'] = True
        own.scene.post_draw.append(after_frame)
else:
    after_frame()
if n == 200 + POST:
    print(own['log'], flush=True)
    with open(logic.expandPath('//' + own.scene.name + '_check_f10.txt'), 'w') as f:
        f.write(own['log'])
    logic.endGame()
""")
bpy.ops.logic.sensor_add(type='ALWAYS', name="Frame", object=checker.name)
checker.game.sensors["Frame"].use_pulse_true_level = True
bpy.ops.logic.controller_add(type='PYTHON', name="Check", object=checker.name)
checker.game.controllers["Check"].text = text
checker.game.sensors["Frame"].link(checker.game.controllers["Check"])

if convert:
    left = []
    for o in tested:
        scene.objects.active = o
        for _i in range(2 if "twice" in argv[2:] else 1):
            print("CONVERT", o.name, bpy.ops.logic.convert_to_component(mode=mode))
    for t in bpy.data.texts:
        left += [(t.name, ln.strip()) for ln in t.as_string().splitlines() if "# TODO:" in ln]
    print("LEFT_AS_BRICK", len(left), left)

bpy.ops.wm.save_as_mainfile(filepath=output)
