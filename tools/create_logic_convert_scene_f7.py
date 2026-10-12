"""Logic Bricks -> Python F7: Action (6 modos), Motion (escala, Damping, Servo, Character, Set Position),
Change Color, Property Level e Runtime API, Armature, Filter 2D, Mouse Over, Game Save Config e Weather Effects.

Run with:  AnastacioEngine -b --python tools/create_logic_convert_scene_f7.py -- <output.range> [convert[:MODULE|SCRIPT]|none [shift] [post]]
Cada objeto de teste tem os proprios bricks; com "convert" todos sao convertidos. Rodar o .range sem e com
"convert" no AnastacioRuntime grava <cena>_check_f7.txt ao lado do .range: uma linha por amostra (a cada 20
quadros, ate o quadro 200). As duas rodadas devem dar o mesmo arquivo, e LEFT_AS_BRICK deve ser 0.
"shift[:N]" atrasa as amostras em N quadros (so para investigar diferencas de fase).
"post" amostra no post_draw, depois da logica e da fisica do quadro. Use nos modos MODULE/SCRIPT (e na rodada
de bricks que serve de referencia): neles o controller Python age antes do Checker ler, e sem "post" a
amostra pega o quadro pela metade.
"""
import bpy
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = argv[0] if argv else "logic_convert_f7.range"
convert = len(argv) > 1 and argv[1].startswith("convert")
mode = argv[1].split(":", 1)[1] if convert and ":" in argv[1] else "COMPONENT"
# Nos modos MODULE/SCRIPT o controller Python age antes do Checker ler: "shift:-1" alinha a logica.
shift = 0
post = int("post" in argv[2:])
if len(argv) > 2 and argv[2].startswith("shift"):
    shift = int(argv[2].split(":", 1)[1]) if ":" in argv[2] else 1

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


cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
cam.location = (0, 0, 20)
scene.objects.link(cam)
scene.camera = cam
cube("Floor", (0, 60, -1), 'STATIC', (40, 10, 1))

# --- Motion simples: Loc e Rot por tic.
o = cube("Mover", (-30, 0, 0))
wire(o, "Go", [always(o)], [actuator(o, 'MOTION', "Step", offset_location=(0.05, 0, 0),
                                     offset_rotation=(0, 0, 0.02))])

# --- Motion Set Position, disparado no quadro 30.
o = cube("Setter", (-25, 0, 0))
wire(o, "Go", [window(o, "At30", 30, 5)], [actuator(o, 'MOTION', "Place", mode='OBJECT_NORMAL_SET',
                                                   offset_location=(-25, 7, 3))])

# --- Linear Velocity com Damping (rampa), em corpo dinamico sem gravidade propria (cai junto nos dois casos).
o = cube("Ramp", (-20, 60, 1), 'DYNAMIC')
wire(o, "Go", [window(o, "On", 10, 60)], [actuator(o, 'MOTION', "Push", linear_velocity=(2.0, 0, 0), damping=30)])

# --- Servo Control.
o = cube("Servo", (-10, 60, 1), 'DYNAMIC')
wire(o, "Go", [always(o)], [actuator(o, 'MOTION', "Drive", mode='OBJECT_SERVO', linear_velocity=(1.5, 0, 0),
                                     proportional_coefficient=0.5, integral_coefficient=0.02,
                                     use_servo_limit_x=True, force_max_x=20.0, force_min_x=-20.0)])

# --- Character Motion: anda 60 quadros e para; pula no meio.
o = cube("Walker", (0, 60, 1.2), 'CHARACTER')
wire(o, "Walk", [window(o, "On", 10, 60)], [actuator(o, 'MOTION', "Walk", mode='OBJECT_CHARACTER',
                                                    offset_location=(0.04, 0, 0), offset_rotation=(0, 0, 0.01))])
wire(o, "Jump", [window(o, "JumpOn", 100, 3)], [actuator(o, 'MOTION', "Jump", mode='OBJECT_CHARACTER',
                                                        use_character_jump=True)])

# --- Change Color com Lerp.
o = cube("Painter", (-15, 0, 0))
wire(o, "Go", [always(o)], [actuator(o, 'EDIT_OBJECT', "Tint", mode='CHANGECOLOR', use_lerp_col=True,
                                     lerp_col=0.05, change_col=(1.0, 0.0, 0.0, 1.0))])

# --- Property Level.
o = cube("Level", (-10, 0, 0))
prop(o, "lv", 'BOOL', False)
wire(o, "Go", [window(o, "On", 30, 50)], [actuator(o, 'PROPERTY', "Lv", mode='LEVEL', property="lv")])

# --- Property Runtime API: atuador escreve a escala local, sensor le de volta.
o = cube("Runtime", (-5, 0, 0))
prop(o, "seen")
wire(o, "Set", [window(o, "At20", 20, 5)],
     [actuator(o, 'PROPERTY', "Scale", actuator_mode='RUNTIME_API', runtime_property='LOCAL_SCALE',
               runtime_value=(2.0, 0.5, 1.5), mode='ASSIGN'),
      actuator(o, 'PROPERTY', "Hide", actuator_mode='RUNTIME_API', runtime_property='VISIBLE',
               runtime_bool_value=False, mode='ASSIGN')])
wire(o, "Add", [window(o, "At60", 60, 5)],
     [actuator(o, 'PROPERTY', "Shift", actuator_mode='RUNTIME_API', runtime_property='LOCAL_POSITION',
               runtime_value=(0.0, 3.0, 0.0), mode='ADD')])
wire(o, "Read", [sensor(o, 'PROPERTY', "IsScaled", use_runtime_property=True, runtime_property='LOCAL_SCALE',
                        runtime_value=(2.0, 0.5, 1.5), evaluation_type='PROPEQUAL')],
     [actuator(o, 'PROPERTY', "Seen", mode='ASSIGN', property="seen", value="1")])

# --- Action: um objeto por modo, mesma acao (X de 0 a 10 nos quadros 1-40) e mesma janela de pulso.
act = bpy.data.actions.new("Slide")
fc = act.fcurves.new("location", 0)
fc.keyframe_points.insert(1, 0.0)
fc.keyframe_points.insert(40, 10.0)
for kp in fc.keyframe_points:
    kp.interpolation = 'LINEAR'
for i, pm in enumerate(('PLAY', 'PINGPONG', 'FLIPPER', 'LOOPSTOP', 'LOOPEND')):
    o = cube("Act" + pm, (0, 10 + 3 * i, 0))
    prop(o, "frame", 'FLOAT', 0.0)
    # Positivo de 10 a 70, negativo, e de novo (repeat): exercita os pulsos nos dois sentidos.
    wire(o, "Go", [window(o, "On", 10, 60, True)],
         [actuator(o, 'ACTION', "Anim", action=act, play_mode=pm, frame_start=1, frame_end=40,
                   frame_property="frame")])
o = cube("ActPROPERTY", (0, 30, 0))
prop(o, "pos", 'FLOAT', 1.0)
wire(o, "Count", [always(o)], [actuator(o, 'PROPERTY', "Inc", mode='ADD', property="pos", value="0.25")])
wire(o, "Go", [always(o, "Tick2")], [actuator(o, 'ACTION', "Anim", action=act, play_mode='PROPERTY', property="pos",
                                              frame_start=1, frame_end=40)])

# --- Armature: constraint Copy Location desligada no quadro 40 e influencia trocada no 80.
bpy.ops.object.armature_add(location=(20, 0, 0))
arm = bpy.context.active_object
arm.name = "Rig"
goal = cube("Goal", (22, 0, 3))
scene.objects.active = arm
bpy.ops.object.mode_set(mode='POSE')
con = arm.pose.bones[0].constraints.new('COPY_LOCATION')
con.name = "Follow"
con.target = goal
bpy.ops.object.mode_set(mode='OBJECT')
bone = arm.pose.bones[0].name
prop(arm, "on", 'INT', 0)
wire(arm, "Run", [always(arm)], [actuator(arm, 'ARMATURE', "Run", mode='RUN')])
wire(arm, "Off", [window(arm, "At40", 40, 5)], [actuator(arm, 'ARMATURE', "Disable", mode='DISABLE', bone=bone,
                                                         constraint="Follow")])
wire(arm, "Inf", [window(arm, "At80", 80, 5)],
     [actuator(arm, 'ARMATURE', "Enable", mode='ENABLE', bone=bone, constraint="Follow"),
      actuator(arm, 'ARMATURE', "Influence", mode='SETINFLUENCE', bone=bone, constraint="Follow", influence=0.25)])
wire(arm, "State", [sensor(arm, 'ARMATURE', "IsOn", bone=bone, constraint="Follow", test_type='STATECHG')],
     [actuator(arm, 'PROPERTY', "Mark", mode='ADD', property="on", value="1")])

# --- Filter 2D: Blur no passe 1, desligado no quadro 60; FXAA embutido; filtro custom no passe 2.
o = cube("Filters", (10, 0, 0))
glsl = bpy.data.texts.new("tint.glsl")
glsl.from_string("uniform sampler2D bgl_RenderedTexture;\nvoid main()\n{\n"
                 "    gl_FragColor = texture2D(bgl_RenderedTexture, gl_TexCoord[0].st) * vec4(1.0, 0.9, 0.9, 1.0);\n}\n")
wire(o, "Add", [window(o, "At10", 10, 5)],
     [actuator(o, 'FILTER_2D', "Blur", mode='BLUR', filter_pass=1),
      actuator(o, 'FILTER_2D', "Fxaa", mode='FXAA'),
      actuator(o, 'FILTER_2D', "Custom", mode='CUSTOMFILTER', filter_pass=2, glsl_shader=glsl)])
wire(o, "Off", [window(o, "At60", 60, 5)], [actuator(o, 'FILTER_2D', "BlurOff", mode='DISABLE', filter_pass=1)])
wire(o, "Del", [window(o, "At100", 100, 5)], [actuator(o, 'FILTER_2D', "CustomDel", mode='REMOVE', filter_pass=2)])

# --- Mouse Over (o Checker poe o cursor no centro; a camera olha para baixo, o Target fica embaixo dela).
o = cube("Target", (0, 0, 0), 'STATIC', (2, 2, 0.2))
prop(o, "pick", 'BOOL', True)
prop(o, "over", 'INT', 0)
prop(o, "overmat", 'INT', 0)
o.data.materials.append(bpy.data.materials.new("Pick"))
cover = cube("Cover", (0, 0, 5), 'STATIC', (2, 2, 0.2))
wire(o, "Over", [sensor(o, 'MOUSE', "OverX", mouse_event='MOUSEOVER', use_x_ray=True, property="pick")],
     [actuator(o, 'PROPERTY', "SetOver", mode='ASSIGN', property="over", value="1")])
wire(o, "OverMat", [sensor(o, 'MOUSE', "OverM", mouse_event='MOUSEOVERANY', use_x_ray=True, use_material='MATERIAL',
                           material="Pick")],
     [actuator(o, 'PROPERTY', "SetOverMat", mode='ASSIGN', property="overmat", value="1")])

# --- Game Save Config e Weather Effects.
o = cube("Game", (15, 0, 0))
wire(o, "Save", [window(o, "At50", 50, 5)], [actuator(o, 'GAME', "SaveCfg", mode='SAVECFG', saveloc="f7cfg",
                                                      extension_name="sav")])
wire(o, "Fog", [window(o, "At20", 20, 5)],
     [actuator(o, 'PROPERTY', "Density", actuator_mode='WEATHER_EFFECTS', weather_category='VOLUMETRIC_FOG',
               vfog_effect='WEATHER_VFOG_DENSITY', runtime_value=(0.77, 0, 0)),
      actuator(o, 'PROPERTY', "Lamps", actuator_mode='WEATHER_EFFECTS', weather_category='VOLUMETRIC_FOG',
               vfog_effect='WEATHER_VFOG_USE_LAMPS', runtime_bool_value=True),
      actuator(o, 'PROPERTY', "Coverage", actuator_mode='WEATHER_EFFECTS', weather_category='VOLUMETRIC_CLOUDS',
               vcloud_effect='WEATHER_VCLOUD_COVERAGE', runtime_value=(1.0, 0, 0)),
      actuator(o, 'PROPERTY', "Layers", actuator_mode='WEATHER_EFFECTS', weather_category='CLOUDS',
               cloud_effect='WEATHER_USE_SKY_LAYERS', runtime_bool_value=True)])

checker = bpy.data.objects.new("Checker", None)
scene.objects.link(checker)
text = bpy.data.texts.new("checker.py")
text.from_string(('SHIFT = %d\nPOST = %d' % (shift, post)) + '''
from Range import logic
import os
cont = logic.getCurrentController()
own = cont.owner
own['frames'] = own.get('frames', 0) + 1
n = own['frames'] - SHIFT
logic.mouse.position = (0.5, 0.5)
o = own.scene.objects
logic.globalDict.setdefault('lv', 0)
def count_level():
    if o['Level']['lv']:
        logic.globalDict['lv'] += 1
if not POST:
    count_level()
def sample(n):
    v = lambda vec: ','.join('%.2f' % x for x in vec)
    fm = own.scene.filterManager
    f1, f2 = fm.getFilter(1), fm.getFilter(2)
    w = own.scene.world
    rig = o['Rig']
    con = rig.constraints[0]
    cfg = logic.expandPath('//f7cfg.sav')
    parts = [
        'f=%d' % n,
        'mover=%s rz=%.2f' % (v(o['Mover'].worldPosition), o['Mover'].worldOrientation.to_euler().z),
        'setter=%s' % v(o['Setter'].worldPosition),
        'ramp=%.2f/%.2f' % (o['Ramp'].worldPosition.x, o['Ramp'].worldLinearVelocity.x),
        'servo=%.2f/%.2f' % (o['Servo'].worldPosition.x, o['Servo'].worldLinearVelocity.x),
        'walker=%s' % v(o['Walker'].worldPosition),
        'color=%s' % v(o['Painter'].color),
        'lv=%d' % logic.globalDict['lv'],
        'rt=%s vis=%s y=%.2f seen=%s' % (v(o['Runtime'].localScale), o['Runtime'].visible,
                                         o['Runtime'].localPosition.y, o['Runtime']['seen']),
        'act=' + '|'.join('%.2f/%.1f' % (o['Act' + m].worldPosition.x, o['Act' + m]['frame'])
                          for m in ('PLAY', 'PINGPONG', 'FLIPPER', 'LOOPSTOP', 'LOOPEND')),
        'actprop=%.2f' % o['ActPROPERTY'].worldPosition.x,
        'rig=%s/%.2f on=%d' % (con.active, con.enforce, rig['on']),
        'filters=%s/%s/%s fxaa=%s' % (f1 is not None, f1.enabled if f1 is not None else None, f2 is not None,
                                      fm.fxaaEnabled),
        'over=%d/%d' % (o['Target']['over'], o['Target']['overmat']),
        'cfg=%s' % os.path.exists(cfg),
        'fog=%.2f/%s cov=%.2f layers=%s' % (w.getWeather('vfog_density'), w.getWeather('vfog_use_lamps'),
                                            w.getWeather('vcloud_coverage'), w.getWeather('use_sky_layers')),
    ]
    own['log'] = own.get('log', '') + ' '.join(parts) + '\\n'
def after_frame():
    n = own['frames'] - SHIFT
    if POST and own.get('counted') != n:
        own['counted'] = n
        count_level()
    if n > 0 and n % 20 == 0 and own.get('sampled') != n:
        own['sampled'] = n
        sample(n)
if POST:
    # Amostra depois da logica e da fisica do quadro: nao depende de quem roda antes do Checker.
    if not own.get('hooked'):
        own['hooked'] = True
        own.scene.post_draw.append(after_frame)
else:
    after_frame()
if n == 200 + POST:
    print(own['log'], flush=True)
    with open(logic.expandPath('//' + own.scene.name + '_check_f7.txt'), 'w') as f:
        f.write(own['log'])
    cfg = logic.expandPath('//f7cfg.sav')
    if os.path.exists(cfg):
        os.remove(cfg)
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
