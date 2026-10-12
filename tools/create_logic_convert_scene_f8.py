"""Logic Bricks -> Python F8: Action com Child (6 modos), Character Motion com VR Gaze e Add Object com o
nome do objeto vindo de uma propriedade (do objeto e do World).

Run with:  AnastacioEngine -b --python tools/create_logic_convert_scene_f8.py -- <output.range> [convert[:MODULE|SCRIPT]|none [post]]
Cada objeto de teste tem os proprios bricks; com "convert" todos sao convertidos. Rodar o .range sem e com
"convert" no AnastacioRuntime grava <cena>_check_f8.txt ao lado do .range: uma linha por amostra (a cada 10
quadros, ate o quadro 200). As duas rodadas devem dar o mesmo arquivo, e LEFT_AS_BRICK deve ser 0.
"post" amostra no post_draw, depois da logica e da fisica do quadro (use nos modos MODULE/SCRIPT e na rodada
de bricks que serve de referencia para eles).
O VR Gaze usa so a orientacao da camera ativa, entao roda sem headset: a camera fica inclinada e girada.
"""
import bpy
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = argv[0] if argv else "logic_convert_f8.range"
convert = len(argv) > 1 and argv[1].startswith("convert")
mode = argv[1].split(":", 1)[1] if convert and ":" in argv[1] else "COMPONENT"
post = int("post" in argv[2:])

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.world = bpy.data.worlds.new("World")
tested = []
MODES = ('PLAY', 'PINGPONG', 'FLIPPER', 'LOOPSTOP', 'LOOPEND', 'PROPERTY')


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


def wire(o, name, sensors, actuators):
    bpy.ops.logic.controller_add(type='LOGIC_AND', name=name, object=o.name)
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


def action(name, path, index, value):
    act = bpy.data.actions.new(name)
    fc = act.fcurves.new(path, index)
    fc.keyframe_points.insert(1, 0.0)
    fc.keyframe_points.insert(40, value)
    for kp in fc.keyframe_points:
        kp.interpolation = 'LINEAR'
    return act


def hidden(o):
    """Camada 2: objeto inativo, so entra no jogo pelo Add Object."""
    o.layers = [i == 1 for i in range(20)]
    return o


# Camera inclinada e girada: o olhar tem componente no chao (X e Y), que e o que o VR Gaze usa.
cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
cam.location = (0, -30, 30)
cam.rotation_euler = (0.9, 0.0, 0.5)
scene.objects.link(cam)
scene.camera = cam
cube("Floor", (0, 0, -1), 'STATIC', (60, 60, 1))

# --- Character Motion com VR Gaze: anda 60 quadros para onde a camera olha e para.
o = cube("Gazer", (-10, 0, 1.2), 'CHARACTER')
wire(o, "Walk", [window(o, "On", 10, 60)], [actuator(o, 'MOTION', "Walk", mode='OBJECT_CHARACTER',
                                                    offset_location=(0.02, 0.05, 0), use_vr_gaze=True)])
# Com Local e Rot: o VR Gaze vale no lugar do eixo local; o corpo gira e a direcao do andar nao muda.
o = cube("GazerRot", (-20, 0, 1.2), 'CHARACTER')
o.rotation_euler = (0, 0, 1.0)
wire(o, "Walk", [window(o, "On", 20, 80)], [actuator(o, 'MOTION', "Walk", mode='OBJECT_CHARACTER',
                                                    offset_location=(0.0, 0.04, 0), offset_rotation=(0, 0, 0.02),
                                                    use_local_location=True, use_vr_gaze=True)])
# Add: soma a direcao anterior e mantem o modulo dela.
o = cube("GazerAdd", (-30, 0, 1.2), 'CHARACTER')
wire(o, "Walk", [window(o, "On", 10, 100)], [actuator(o, 'MOTION', "Walk", mode='OBJECT_CHARACTER',
                                                     offset_location=(0.03, 0.01, 0), use_vr_gaze=True),
                                            actuator(o, 'MOTION', "Side", mode='OBJECT_CHARACTER',
                                                     offset_location=(-0.02, 0.03, 0), use_vr_gaze=True,
                                                     use_add_character_location=True)])

# --- Action com Child: um pai por modo; filho e neto com acao propria, e um filho sem acao.
slide = action("Slide", "location", 0, 10.0)
bob = action("Bob", "location", 2, 4.0)
sway = action("Sway", "location", 1, 2.0)
for i, pm in enumerate(MODES):
    o = cube("P" + pm, (0, 10 + 4 * i, 0))
    kid = cube("K" + pm, (0, 0, 0))
    kid.parent = o
    kid.animation_data_create().action = bob
    grand = cube("G" + pm, (0, 0, 0))
    grand.parent = kid
    grand.animation_data_create().action = sway
    plain = cube("N" + pm, (1, 1, 1))
    plain.parent = o
    if pm == 'PROPERTY':
        prop(o, "pos", 'FLOAT', 1.0)
        wire(o, "Count", [always(o)], [actuator(o, 'PROPERTY', "Inc", mode='ADD', property="pos", value="0.25")])
        wire(o, "Go", [window(o, "On", 10, 60, True)],
             [actuator(o, 'ACTION', "Anim", action=slide, play_mode=pm, property="pos", frame_start=1,
                       frame_end=40, use_children=True)])
    else:
        # Positivo de 10 a 70, negativo, e de novo (repeat): exercita os pulsos nos dois sentidos.
        wire(o, "Go", [window(o, "On", 10, 60, True)],
             [actuator(o, 'ACTION', "Anim", action=slide, play_mode=pm, frame_start=1, frame_end=40,
                       use_children=True)])

# --- Add Object com o nome numa propriedade. Os originais ficam na camada 2.
hidden(cube("BulA", (0, 0, 50)))
hidden(cube("BulB", (0, 0, 50), scale=(0.5, 0.5, 0.5)))
hidden(cube("BulD", (0, 0, 50), 'DYNAMIC', (0.3, 0.3, 0.3)))
# Propriedade do objeto: troca de BulA para BulB no quadro 60, para um nome que nao existe no 120
# (nada e adicionado) e volta para BulA no 160.
o = cube("SpawnProp", (20, 0, 5))
prop(o, "which", 'STRING', "BulA")
wire(o, "Fire", [window(o, "Every", 5, 2, True)],
     [actuator(o, 'EDIT_OBJECT', "Add", mode='ADDOBJECT', use_object_from_property=True, object_property="which",
               time=25)])
for frame, value in ((60, "BulB"), (120, "Nope"), (160, "BulA")):
    # Copy de outro objeto: o nome chega igual nos bricks e no codigo convertido.
    holder = cube("Name" + value, (25, 0, 5))
    prop(holder, "which", 'STRING', value)
    scene.objects.active = o
    wire(o, "To%d" % frame, [window(o, "At%d" % frame, frame, 3)],
         [actuator(o, 'PROPERTY', "Set%d" % frame, mode='COPY', property="which", object=holder,
                   object_property="which")])
# World Property.
scene.objects.active = o
bpy.ops.world.game_property_new(type='STRING', name="wbul")
scene.world.properties["wbul"].value = "BulB"
o = cube("SpawnWorld", (20, 10, 5))
wire(o, "Fire", [window(o, "Every", 20, 2, True)],
     [actuator(o, 'EDIT_OBJECT', "Add", mode='ADDOBJECT', use_object_from_property=True,
               use_global_object_property=True, object_property="wbul", time=50)])
# Propriedade que nao existe no objeto: nunca adiciona.
o = cube("SpawnNone", (20, 20, 5))
wire(o, "Fire", [window(o, "Every", 20, 2, True)],
     [actuator(o, 'EDIT_OBJECT', "Add", mode='ADDOBJECT', use_object_from_property=True, object_property="nada")])
# Corpo dinamico com velocidade linear e angular.
o = cube("SpawnDyn", (20, 30, 5))
prop(o, "which", 'STRING', "BulD")
wire(o, "Fire", [window(o, "Every", 30, 2, True)],
     [actuator(o, 'EDIT_OBJECT', "Add", mode='ADDOBJECT', use_object_from_property=True, object_property="which",
               time=45, linear_velocity=(3.0, 0, 0), angular_velocity=(0, 0, 2.0))])

checker = bpy.data.objects.new("Checker", None)
scene.objects.link(checker)
text = bpy.data.texts.new("checker.py")
text.from_string(('POST = %d\nMODES = %r' % (post, MODES)) + '''
from Range import logic
cont = logic.getCurrentController()
own = cont.owner
own['frames'] = own.get('frames', 0) + 1
o = own.scene.objects
def sample(n):
    v = lambda vec: ','.join('%.2f' % x for x in vec)
    def copies(name):
        found = sorted(v(x.worldPosition) for x in o if x.name == name)
        return '%s:%d[%s]' % (name, len(found), ';'.join(found))
    parts = ['f=%d' % n]
    parts += ['%s=%s' % (g.lower(), v(o[g].worldPosition)) for g in ('Gazer', 'GazerRot', 'GazerAdd')]
    parts.append('rot=%.2f' % o['GazerRot'].worldOrientation.to_euler().z)
    for m in MODES:
        parts.append('%s=%s' % (m, '|'.join(v(o[k + m].worldPosition) for k in 'PKGN')))
    parts += [copies('BulA'), copies('BulB')]
    dyn = sorted((v(x.worldPosition), '%.2f' % x.worldLinearVelocity.x, '%.2f' % x.worldAngularVelocity.z)
                 for x in o if x.name == 'BulD')
    parts.append('BulD:%d[%s]' % (len(dyn), ';'.join('/'.join(d) for d in dyn)))
    own['log'] = own.get('log', '') + ' '.join(parts) + '\\n'
def after_frame():
    n = own['frames']
    if n % 10 == 0 and own.get('sampled') != n:
        own['sampled'] = n
        sample(n)
if POST:
    # Amostra depois da logica e da fisica do quadro: nao depende de quem roda antes do Checker.
    if not own.get('hooked'):
        own['hooked'] = True
        own.scene.post_draw.append(after_frame)
else:
    after_frame()
if own['frames'] == 200 + POST:
    print(own['log'], flush=True)
    with open(logic.expandPath('//' + own.scene.name + '_check_f8.txt'), 'w', encoding='utf-8') as f:
        f.write(own['log'])
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
