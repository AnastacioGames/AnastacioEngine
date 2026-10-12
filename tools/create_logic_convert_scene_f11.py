"""Logic Bricks -> Python F11: eventos proprios de quatro sensores. Collision com Pulse (muda a quantidade de
objetos encostados), Mouse Over Any com Pulse (o cursor passa para outro objeto), Keyboard com Log Toggle e
Target (texto digitado vai para uma propriedade) e Random com Delta Time (intervalo do sorteio).

Run with:  AnastacioEngine -b --python tools/create_logic_convert_scene_f11.py -- <output.range> [convert[:MODULE|SCRIPT]|none [post]]
Cada objeto conta os disparos numa propriedade (Property Add). O Checker poe o cursor no centro da tela, troca
de lugar as placas embaixo da camera (Mouse Over) e os cubos em cima do Pad (Collision). Rodar o .range sem e
com "convert" no AnastacioRuntime grava <cena>_check_f11.txt ao lado do .range (uma linha a cada 10 quadros,
ate o quadro 200, e uma linha final com a cadencia dos Random). As duas rodadas devem dar o mesmo arquivo, e
LEFT_AS_BRICK deve ser 0.

O que o arquivo NAO prova: texto digitado de verdade no Keyboard (o teste nao gera teclas). Ele cobre a
propriedade Log Toggle ligada/desligada/ausente, o Target que nao e texto (a engine o transforma em texto
mesmo sem tecla), o sensor sem controller e o sensor num estado inativo. Nos Random os valores sorteados sao
diferentes (geradores diferentes): a linha final compara so em que quadros o valor pode mudar.
"""

import bpy
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = argv[0] if argv else "logic_convert_f11.range"
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
    return c


cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
cam.location = (0, 0, 20)
scene.objects.link(cam)
scene.camera = cam
names = []  # (objeto, propriedades amostradas a cada 10 quadros)
random_names = []  # (objeto, periodo esperado em quadros)


def counter(name, props=("n",)):
    # Fila fora do raio do cursor (a camera olha para baixo em x=0, y=0).
    o = cube(name, (len(names) * 3 - 30, 30, 0))
    for p in props:
        prop(o, p)
    names.append((name, props))
    return o


def add(o, p="n", name=None):
    return actuator(o, 'PROPERTY', name or "Add_" + p, mode='ADD', property=p, value="1")


# --- 1. Collision com Pulse. O Pad (estatico) tem os sensores; os cubos D1..D3 (dinamicos, Actor) sao postos
# em cima dele e tirados pelo Checker. D1 e D3 tem a propriedade "hot" e o material "Hot".
PAD_PROPS = ("pulse", "plain", "hot", "mat", "inv", "tap", "skip")
pad = cube("Pad", (40, 0, 0), 'STATIC', (7, 3, 0.5))
for p in PAD_PROPS:
    prop(pad, p)
names.append(("Pad", PAD_PROPS))
cube("Park", (40, 60, 0), 'STATIC', (7, 3, 0.5))
hot = bpy.data.materials.new("Hot")
for i in (1, 2, 3):
    d = cube("D%d" % i, (32 + 4 * i, 60, 1.52), 'DYNAMIC')
    d.game.use_actor = True
    d.game.use_sleep = True  # "No Sleeping": parado em cima do Pad continua colidindo
    d.game.use_collision_bounds = True
    d.game.collision_bounds_type = 'BOX'
    if i != 2:
        prop(d, "hot", 'BOOL', True)
        d.data.materials.append(hot)
s_pulse = sensor(pad, 'COLLISION', "Pulse", use_pulse=True)
wire(pad, "CPulse", [s_pulse], [add(pad, "pulse")])
wire(pad, "CPlain", [sensor(pad, 'COLLISION', "Plain")], [add(pad, "plain")])
wire(pad, "CHot", [sensor(pad, 'COLLISION', "Hot", use_pulse=True, property="hot")], [add(pad, "hot")])
wire(pad, "CMat", [sensor(pad, 'COLLISION', "Mat", use_pulse=True, use_material=True, material="Hot")],
     [add(pad, "mat")])
wire(pad, "CInv", [sensor(pad, 'COLLISION', "Inv", use_pulse=True, invert=True)], [add(pad, "inv")], 'LOGIC_NAND')
wire(pad, "CTap", [sensor(pad, 'COLLISION', "Tap", use_pulse=True, use_tap=True)], [add(pad, "tap")])
wire(pad, "CSkip", [sensor(pad, 'COLLISION', "Skip", use_pulse=True, use_pulse_true_level=True, tick_skip=9)],
     [add(pad, "skip")])
# O mesmo sensor do Pad ligado a um controller de outro objeto.
o = counter("Watcher")
wire(o, "Go", [s_pulse], [add(o)])

# --- 2. Mouse Over Any com Pulse. As placas MA, MB e MC entram e saem debaixo da camera; MA e MB tem "pick".
for i, name in enumerate(("MA", "MB", "MC")):
    m = cube(name, (100 + 20 * i, 100, 0), 'STATIC', (6, 6, 0.2))  # largas: o cursor nao precisa estar exato
    if name != "MC":
        prop(m, "pick", 'BOOL', True)
o = counter("OverPulse")
wire(o, "Go", [sensor(o, 'MOUSE', "Over", mouse_event='MOUSEOVERANY', use_pulse=True)], [add(o)])
o = counter("OverPlain")
wire(o, "Go", [sensor(o, 'MOUSE', "Over", mouse_event='MOUSEOVERANY')], [add(o)])
o = counter("OverProp")
wire(o, "Go", [sensor(o, 'MOUSE', "Over", mouse_event='MOUSEOVERANY', use_pulse=True, property="pick")], [add(o)])
o = counter("OverTap")
wire(o, "Go", [sensor(o, 'MOUSE', "Over", mouse_event='MOUSEOVERANY', use_pulse=True, use_tap=True)], [add(o)])
o = counter("OverInv")
wire(o, "Go", [sensor(o, 'MOUSE', "Over", mouse_event='MOUSEOVERANY', use_pulse=True, invert=True)], [add(o)],
     'LOGIC_NAND')
o = counter("OverSkip")
wire(o, "Go", [sensor(o, 'MOUSE', "Over", mouse_event='MOUSEOVERANY', use_pulse=True, use_pulse_true_level=True,
                      tick_skip=9)], [add(o)])
# Mouse Over simples com Pulse: o objeto sob o cursor e sempre o dono, o Pulse nao acrescenta eventos.
m = bpy.data.objects["MA"]
prop(m, "n")
names.append(("MA", ("n",)))
wire(m, "Go", [sensor(m, 'MOUSE', "Self", mouse_event='MOUSEOVER', use_pulse=True)], [add(m)])

# --- 3. Keyboard com Log Toggle e Target (sem teclas: so o que a engine faz sem nada digitado).
# Log ligado: o Target inteiro vira texto ("7"); o Target de texto fica como esta.
o = counter("KeyOn", ("n",))
prop(o, "log", 'BOOL', True)
prop(o, "num", 'INT', 7)
prop(o, "txt", 'STRING', "abc")
names[-1] = ("KeyOn", ("n", "num", "txt"))
wire(o, "Go", [sensor(o, 'KEYBOARD', "KA", key='A', log="log", target="num")], [add(o)])
wire(o, "Any", [sensor(o, 'KEYBOARD', "KAll", use_all_keys=True, log="log", target="txt")], [add(o)])
# Log desligado ate o quadro 95 (o Checker liga): o Target so vira texto depois.
o = counter("KeyOff", ("n",))
prop(o, "log", 'INT', 0)
prop(o, "num", 'INT', 7)
names[-1] = ("KeyOff", ("n", "num"))
wire(o, "Go", [sensor(o, 'KEYBOARD', "KA", key='A', log="log", target="num")], [add(o)])
# Log Toggle de texto conta como ligado; Target float e bool viram texto no formato da engine.
o = counter("KeyStr", ("n",))
prop(o, "log", 'STRING', "x")
prop(o, "val", 'FLOAT', 1.5)
prop(o, "flag", 'BOOL', True)
names[-1] = ("KeyStr", ("n", "val", "flag"))
wire(o, "Go", [sensor(o, 'KEYBOARD', "KA", key='A', log="log", target="val"),
               sensor(o, 'KEYBOARD', "KB", key='B', log="log", target="flag")], [add(o)], 'LOGIC_OR')
# Sensor sem controller: a engine roda mesmo assim, so para gravar o texto.
o = counter("KeyFree", ("n",))
prop(o, "log", 'BOOL', True)
prop(o, "num", 'INT', 7)
names[-1] = ("KeyFree", ("n", "num"))
sensor(o, 'KEYBOARD', "Loose", key='A', log="log", target="num")
wire(o, "Go", [sensor(o, 'DELAY', "W", delay=10, duration=20, use_repeat=True)], [add(o)])
# Propriedades que nao existem: nada acontece.
o = counter("KeyMiss", ("n",))
prop(o, "log", 'BOOL', True)
prop(o, "num", 'INT', 7)
names[-1] = ("KeyMiss", ("n", "num"))
wire(o, "Go", [sensor(o, 'KEYBOARD', "KA", key='A', log="nolog", target="num"),
               sensor(o, 'KEYBOARD', "KB", key='B', log="log", target="notarget")], [add(o)], 'LOGIC_OR')
# Controller num estado inativo: o sensor nao roda e nao grava.
o = counter("KeyState", ("n",))
prop(o, "log", 'BOOL', True)
prop(o, "num", 'INT', 7)
names[-1] = ("KeyState", ("n", "num"))
wire(o, "Go", [sensor(o, 'KEYBOARD', "KA", key='A', log="log", target="num")], [add(o)]).states = 2
wire(o, "Tick", [sensor(o, 'DELAY', "W", delay=10, duration=20, use_repeat=True)], [add(o)])


# --- 4. Random: "n" sobe quando o sorteio muda para positivo e "m" quando muda para negativo.
def random_counter(name, period, **kw):
    o = cube(name, (len(random_names) * 3 - 30, 36, 0))
    prop(o, "n")
    prop(o, "m")
    s = sensor(o, 'RANDOM', "R", **kw)
    wire(o, "Up", [s], [add(o, "n")])
    wire(o, "Down", [s], [add(o, "m")], 'LOGIC_NAND')
    random_names.append((name, period))


random_counter("RndFrames", 5, seed=5, tick_skip=4)
# Delta Time: vale tick_skip_dt (2.5 -> sorteio a cada 3 quadros), nao o tick_skip.
random_counter("RndDt", 3, seed=3, use_dt=True, tick_skip_dt=2.5, tick_skip=7)
random_counter("RndDtSmall", 1, seed=9, use_dt=True, tick_skip_dt=0.4, tick_skip=6)

# Quadro -> [(objeto, posicao)]. Quadros que nao sao multiplos de 10, longe das amostras.
UNDER, ABOVE, TOP = (0.0, 0.0, 0.0), (0.0, 0.0, 3.0), (0.0, 0.0, 6.0)
park_m = {"MA": (100.0, 100.0, 0.0), "MB": (120.0, 100.0, 0.0), "MC": (140.0, 100.0, 0.0)}
on_pad = {"D1": (36.0, 0.0, 1.52), "D2": (40.0, 0.0, 1.52), "D3": (44.0, 0.0, 1.52)}
park_d = {"D1": (36.0, 60.0, 1.52), "D2": (40.0, 60.0, 1.52), "D3": (44.0, 60.0, 1.52)}
moves = {
    # Mouse Over: quem entra fica acima de quem ja esta (o raio da camera pega o mais alto), assim o
    # objeto sob o cursor troca sem nenhum quadro vazio no meio.
    13: [("MA", UNDER)],
    43: [("MB", ABOVE)],            # MA -> MB
    73: [("MB", park_m["MB"])],     # MB -> MA
    103: [("MC", TOP)],             # MA -> MC
    133: [("MA", park_m["MA"])],    # continua MC
    153: [("MC", park_m["MC"])],    # nada
    173: [("MB", ABOVE)],           # MB
    187: [("MC", TOP)],             # MB -> MC
    23: [("D1", on_pad["D1"])],
    53: [("D2", on_pad["D2"])],
    83: [("D3", on_pad["D3"])],
    113: [("D2", park_d["D2"])],
    143: [("D1", park_d["D1"])],
    165: [("D3", park_d["D3"])],
    185: [("D1", on_pad["D1"]), ("D2", on_pad["D2"])],
}

checker = bpy.data.objects.new("Checker", None)
scene.objects.link(checker)
text = bpy.data.texts.new("checker.py")
text.from_string(('POST = %d\nNAMES = %r\nRANDOM = %r\nMOVES = %r' % (post, names, random_names, moves)) + """
from Range import logic
import traceback
cont = logic.getCurrentController()
own = cont.owner
own['frames'] = own.get('frames', 0) + 1
n = own['frames']
o = own.scene.objects
G = logic.globalDict
def fail():
    # O player nao mostra o console: grava o erro e encerra.
    with open(logic.expandPath('//check_f11_error.txt'), 'w', encoding='utf-8') as f:
        f.write(traceback.format_exc())
    logic.endGame()
def sample(n):
    parts = ['f=%d' % n]
    for name, props in NAMES:
        parts.append('%s=%s' % (name, '/'.join(repr(o[name][p]) for p in props)))
    # Onde a engine acha que o cursor esta. "fora" = a janela nao recebeu o movimento do cursor (outra
    # janela na frente, ou alguem mexendo no mouse): as colunas Over* e MA dessa rodada nao valem.
    mx, my = logic.mouse.position
    parts.append('cursor=' + ('centro' if abs(mx - 0.5) < 0.2 and abs(my - 0.5) < 0.2 else 'fora'))
    G['log'] = G.get('log', '') + ' '.join(parts) + chr(10)
def watch_random(n):
    # Quadros em que o valor de cada Random mudou (n + m sobe em toda mudanca).
    for name, _period in RANDOM:
        total = o[name]['n'] + o[name]['m']
        last, frames = G.setdefault('rnd:' + name, [0, []])
        if total != last:
            G['rnd:' + name][0] = total
            frames.append(n)
def gcd(a, b):
    while b:
        a, b = b, a % b
    return a
def random_line():
    parts = ['random']
    for name, period in RANDOM:
        frames = G['rnd:' + name][1]
        step = 0
        for a, b in zip(frames, frames[1:]):
            step = gcd(step, b - a)
        # passo = maior divisor comum dos intervalos entre mudancas; resto = fase dentro do periodo.
        parts.append('%s=passo:%d/resto:%s/mudou:%s' % (
            name, step, sorted(set(f % period for f in frames)), len(frames) > 5))
    return ' '.join(parts) + chr(10)
def after_frame():
    n = own['frames']
    if own.get('sampled') == n:
        return
    own['sampled'] = n
    try:
        watch_random(n)
        if n % 10 == 0:
            sample(n)
        # Mudancas da cena: feitas aqui (com "post", depois de toda a logica do quadro) os bricks e o
        # componente convertido so enxergam a mudanca no quadro seguinte, os dois no mesmo quadro.
        for name, pos in MOVES.get(n, ()):
            ob = o[name]
            ob.worldPosition = pos
            if name.startswith('D'):
                ob.worldLinearVelocity = (0.0, 0.0, 0.0)
                ob.worldAngularVelocity = (0.0, 0.0, 0.0)
        if n == 95:
            o['KeyOff']['log'] = 1
    except Exception:
        fail()
try:
    logic.mouse.position = (0.5, 0.5)
    if POST:
        # Amostra depois da logica e da fisica do quadro: nao depende de quem roda antes do Checker.
        if not own.get('hooked'):
            own['hooked'] = True
            own.scene.post_draw.append(after_frame)
    else:
        after_frame()
    if n == 200 + POST:
        out = G['log'] + random_line()
        print(out, flush=True)
        with open(logic.expandPath('//' + own.scene.name + '_check_f11.txt'), 'w', encoding='utf-8') as f:
            f.write(out)
        logic.endGame()
except Exception:
    fail()
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
        print("CONVERT", o.name, bpy.ops.logic.convert_to_component(mode=mode))
    for t in bpy.data.texts:
        left += [(t.name, ln.strip()) for ln in t.as_string().splitlines() if "# TODO:" in ln]
    print("LEFT_AS_BRICK", len(left), left)
    # O Keyboard solto que grava texto tem que continuar ativo como brick.
    print("LOOSE_KEYBOARD_ACTIVE", bpy.data.objects["KeyFree"].game.sensors["Loose"].active)
    if "dump" in argv[2:]:
        for t in bpy.data.texts:
            if t.name.endswith("_logic.py"):
                print("=" * 20, t.name)
                print(t.as_string())

bpy.ops.wm.save_as_mainfile(filepath=output)
