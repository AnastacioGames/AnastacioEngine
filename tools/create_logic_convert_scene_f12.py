"""Logic Bricks -> Python F12: Track To com o alvo vindo de uma propriedade (From Property).

Run with:  AnastacioEngine -b --python tools/create_logic_convert_scene_f12.py -- <output.range> [convert[:MODULE|SCRIPT]|none [post]]
Cada rastreador le o nome do alvo numa propriedade de texto (dele ou do World) que muda durante o jogo:
TA -> TB -> nome que nao existe -> vazio -> TA -> TB. A propriedade do objeto e trocada por actuators Property
(Copy) do proprio rastreador; a do World, pelo Checker. Os dois alvos andam o tempo todo. Ha rastreadores 2D e 3D,
com Time maior que 0, com pai girando, com a propriedade no World, com a propriedade ausente (nunca rastreia,
mesmo com objeto fixo) e com From Property ligado mas sem nome de propriedade (segue o objeto fixo).
Rodar o .range sem e com "convert" no AnastacioRuntime grava <cena>_check_f12.txt ao lado do .range (uma linha
a cada 10 quadros, ate o quadro 240) com a matriz de orientacao de cada rastreador. As duas rodadas devem dar
o mesmo arquivo, e LEFT_AS_BRICK deve ser 0.
"""

import bpy
import sys
from math import radians

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = argv[0] if argv else "logic_convert_f12.range"
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
cam.location = (0, 0, 60)
scene.objects.link(cam)
scene.camera = cam

# Quadro -> nome do alvo. "Nope" nao existe na cena; "" e a propriedade vazia.
SWITCHES = ((40, "TB"), (80, "Nope"), (110, ""), (140, "TA"), (190, "TB"))
# Ordem de criacao: pai, rastreadores, alvos. A cena guarda os objetos do mais novo para o mais antigo, com os
# filhos logo depois do pai, e a engine segue essa ordem: assim os alvos (e o pai) agem no quadro antes de todos
# os rastreadores, nos bricks e no codigo convertido. Nos bricks o objeto cujo Track To fica sem alvo sai da
# lista de actuators ativos e volta no fim dela (SCA_LogicManager::UpdateFrame); o componente roda sempre na
# ordem dos objetos. Com os alvos na frente desde o inicio essa volta nao muda quem age primeiro; em outra
# ordem, depois de perder e recuperar o alvo os bricks passam a ver o alvo um quadro mais novo que o componente.
later = []  # ligacoes com objetos que so existem depois (alvo fixo, donos dos nomes) ou que pedem scene.update()

# Pai que gira (comeca rodado: a engine guarda a orientacao local inicial dele).
parent = cube("Parent", (0, 20, 0))
parent.rotation_euler = (0, radians(20), radians(30))
wire(parent, "Go", [always(parent)], [actuator(parent, 'MOTION', "Spin", offset_rotation=(0, 0, 0.01))])

bpy.ops.world.game_property_new(type='STRING', name="wtgt")
scene.world.properties["wtgt"].value = "TA"

names = []


def tracker(name, three_d=True, time=0, world=False, child=False, axis='TRACKAXISY', up='UPAXISZ',
            property_name=None, fixed=None, switch=True, has_prop=True):
    if property_name is None:
        property_name = "wtgt" if world else "tname"
    o = cube(name, (len(names) * 4 - 18, 0, 0))
    if child:
        o.location = (len(names) * 4 - 18, 20, 2)
        o.rotation_euler = (radians(10), 0, radians(-40))

        def link_parent(o=o):
            o.parent = bpy.data.objects["Parent"]
            o.matrix_parent_inverse = o.parent.matrix_world.inverted()
        later.append(link_parent)
    if has_prop and not world:
        prop(o, "tname", 'STRING', "TA")
    a = actuator(o, 'EDIT_OBJECT', "Aim", mode='TRACKTO', track_axis=axis, up_axis=up, use_3d_tracking=three_d,
                 time=time, use_object_from_property=True, use_global_object_property=world,
                 object_property=property_name)
    if fixed is not None:
        later.append(lambda a=a: setattr(a, "object", bpy.data.objects[fixed]))
    # O Track To e o primeiro actuator do objeto: roda antes da troca de nome do mesmo quadro.
    wire(o, "Track", [always(o)], [a])
    if switch and not world:
        # (A propriedade do World e trocada pelo Checker, nos mesmos quadros.)
        for frame, value in SWITCHES:
            act = actuator(o, 'PROPERTY', "Set%d" % frame, mode='COPY', property="tname",
                           object_property="which")
            later.append(lambda act=act, value=value: setattr(act, "object", holders[value]))
            wire(o, "To%d" % frame, [window(o, "At%d" % frame, frame, 3)], [act])
    names.append(name)
    return o


tracker("T2D", three_d=False)
tracker("T3D")
tracker("TTime", time=5)
tracker("TTime2D", three_d=False, time=3)
tracker("TNegX", axis='TRACKAXISNEGX', up='UPAXISY')
tracker("TWorld", world=True)
tracker("TPar", child=True)
tracker("TParTime", child=True, time=4)
tracker("TPar2D", child=True, three_d=False)
# Objeto fixo preenchido (o campo some da UI, mas o valor fica): e so o alvo inicial; a propriedade manda.
tracker("TFixed", fixed="TB")
# Propriedade que nao existe no objeto: nunca rastreia, nem o objeto fixo.
tracker("TNoProp", property_name="nada", fixed="TA", switch=False)
# From Property ligado sem nome de propriedade: a engine segue o objeto fixo.
tracker("TNoName", property_name="", fixed="TB", switch=False)
# Propriedade do World que nao existe: nunca rastreia.
tracker("TWorldNone", world=True, property_name="wnada", switch=False)

# Dois alvos que andam o tempo todo (em direcoes e alturas diferentes).
ta = cube("TA", (-12, 14, 3), scale=(0.5, 0.5, 0.5))
wire(ta, "Go", [always(ta)], [actuator(ta, 'MOTION', "Move", offset_location=(0.07, -0.02, 0.03))])
tb = cube("TB", (10, -16, -4), scale=(0.5, 0.5, 0.5))
wire(tb, "Go", [always(tb)], [actuator(tb, 'MOTION', "Move", offset_location=(-0.04, 0.09, 0.02))])

holders = {}
for _frame, value in SWITCHES:
    # Copy de outro objeto: o nome chega igual nos bricks e no codigo convertido.
    h = cube("Name" + (value or "Empty"), (30, 0, 0), scale=(0.2, 0.2, 0.2))
    prop(h, "which", 'STRING', value)
    holders[value] = h

scene.update()  # matrix_world do pai, para o parent inverse dos filhos
for fn in later:
    fn()

checker = bpy.data.objects.new("Checker", None)
scene.objects.link(checker)
text = bpy.data.texts.new("checker.py")
# World: troca 5 quadros depois (fora dos quadros amostrados). Nos modos MODULE/SCRIPT o codigo convertido roda
# como controller, antes do Checker, e so ve o nome novo no quadro seguinte.
text.from_string(('POST = %d\nNAMES = %r\nSWITCHES = %r' % (post, names, {f + 5: v for f, v in SWITCHES})) + """
from Range import logic
cont = logic.getCurrentController()
own = cont.owner
own['frames'] = own.get('frames', 0) + 1
n = own['frames']
o = own.scene.objects
if n in SWITCHES:
    # Roda com os controllers, antes dos componentes e dos actuators do quadro: mesmo instante nas duas rodadas.
    own.scene.world['wtgt'] = SWITCHES[n]
def num(x):
    # -0.00 e 0.00 sao o mesmo valor (o sinal do zero muda entre os bricks e o codigo convertido).
    t = '%.2f' % x
    return '0.00' if t == '-0.00' else t
def sample(n):
    parts = ['f=%d' % n]
    for name in NAMES:
        parts.append('%s=%s' % (name, ','.join(num(x) for row in o[name].worldOrientation for x in row)))
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
            with open(logic.expandPath('//check_f12_error.txt'), 'w', encoding='utf-8') as f:
                f.write(traceback.format_exc())
            logic.endGame()
if POST:
    # Amostra depois da logica e da fisica do quadro: nao depende de quem roda antes do Checker.
    if not own.get('hooked'):
        own['hooked'] = True
        own.scene.post_draw.append(after_frame)
else:
    after_frame()
if n == 240 + POST:
    print(own['log'], flush=True)
    with open(logic.expandPath('//' + own.scene.name + '_check_f12.txt'), 'w', encoding='utf-8') as f:
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
        print("CONVERT", o.name, bpy.ops.logic.convert_to_component(mode=mode))
    for t in bpy.data.texts:
        left += [(t.name, ln.strip()) for ln in t.as_string().splitlines() if "# TODO:" in ln]
    print("LEFT_AS_BRICK", len(left), left)

bpy.ops.wm.save_as_mainfile(filepath=output)
