"""Logic Bricks -> Python F9: o que a cena F7 nao exercita no jogo.

- Action em armature: Blendin > 0 em todos os modos, Continue, dois actuators em camadas diferentes (Layer
  Weight e Blend Mode Blend/Add) e dois na MESMA camada com prioridades diferentes (ou iguais, ou identicos).
- Action de objeto (IPO) em duas camadas e em conflito de prioridade.
- Armature sensor nos 5 testes (State Changed, Lin/Rot error below/above) sobre um rig com IK iTaSC cujo alvo
  anda e gira; IK de distancia; constraint inexistente; Invert.
- Game: Save/Load Config (nome+extensao, so nome, tudo vazio) e Screenshot.
- Filter 2D: Motion Blur (liga, troca o valor, desliga), os filtros prontos que a F7 nao usa, Enable, e os
  embutidos Bloom/Tonemap/SSAO/Light Scatter/SSR.

Run with:  AnastacioEngine -b --python tools/create_logic_convert_scene_f9.py -- <output.range> [convert[:MODULE|SCRIPT]|none [post] [extonly] [only:A,B]]
Cada objeto de teste tem os proprios bricks; com "convert" todos sao convertidos. Rodar o .range sem e com
"convert" no AnastacioRuntime grava <cena>_check_f9.txt ao lado do .range: uma linha por amostra (a cada 10
quadros, ate o quadro 240). As duas rodadas devem dar o mesmo arquivo, e LEFT_AS_BRICK deve ser 0.
"extonly" inclui o Save/Load Config so com extensao (diferenca conhecida, ver o comentario no codigo).
"post" amostra no post_draw (use nos modos MODULE/SCRIPT e na rodada de bricks de referencia deles).
"only:Nome1,Nome2" converte so esses objetos (para isolar uma diferenca).
"""
import bpy
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = argv[0] if argv else "logic_convert_f9.range"
convert = len(argv) > 1 and argv[1].startswith("convert")
mode = argv[1].split(":", 1)[1] if convert and ":" in argv[1] else "COMPONENT"
post = int("post" in argv[2:])
only = None
# "extonly": Save/Load Config so com a extensao preenchida. O Python nao tem como pedir o nome padrao junto
# de uma extensao (saveGlobalDict nao aceita None), entao esse caso difere e fica fora da cena padrao.
extonly = "extonly" in argv[2:]
for a in argv[2:]:
    if a.startswith("only:"):
        only = set(a.split(":", 1)[1].split(","))

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
    scene.objects.active = o  # os tipos oferecidos dependem do objeto ativo (Armature)
    bpy.ops.logic.sensor_add(type=type_, name=name, object=o.name)
    s = o.game.sensors[name]
    for k, v in kw.items():
        setattr(s, k, v)
    return s


def actuator(o, type_, name, **kw):
    scene.objects.active = o  # os tipos oferecidos dependem do objeto ativo (Armature)
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


def rig(name, loc, tip=False):
    """Armature de um bone ("Bone"); com tip, um segundo bone "Tip" ligado na ponta."""
    bpy.ops.object.armature_add(location=loc)
    arm = bpy.context.active_object
    arm.name = name
    if tip:
        bpy.ops.object.mode_set(mode='EDIT')
        eb = arm.data.edit_bones
        b = eb.new("Tip")
        b.head = eb["Bone"].tail
        b.tail = (0, 0, 2)
        b.parent = eb["Bone"]
        b.use_connect = True
        bpy.ops.object.mode_set(mode='OBJECT')
    # Sem malha deformada a engine nao resolve a pose: culling None (valor 1) e um cubo preso no bone
    # (o filho de bone e quem pede a pose aplicada, com as constraints/IK).
    items = arm.data.bl_rna.properties['culling_method'].enum_items
    arm.data.culling_method = [i.identifier for i in items if i.value == 1][0]
    tag = cube(name + "_tag", loc, scale=(0.1, 0.1, 0.1))
    tag.parent = arm
    tag.parent_type = 'BONE'
    tag.parent_bone = "Tip" if tip else "Bone"
    return arm


def action(name, path, keys, group=""):
    """keys: {indice: [(quadro, valor), ...]}, interpolacao linear."""
    act = bpy.data.actions.new(name)
    for index, points in keys.items():
        fc = act.fcurves.new(path, index, group)
        for frame, value in points:
            fc.keyframe_points.insert(frame, value)
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'
    return act


cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
cam.location = (0, 0, 30)
scene.objects.link(cam)
scene.camera = cam

# ---------------------------------------------------------------------------------------------------------
# Action em armature. As acoes comecam fora do repouso, para o Blendin aparecer na pose.
BONE = 'pose.bones["Bone"].location'
slide = action("Slide", BONE, {0: [(1, 4.0), (20, 10.0)]}, "Bone")
lift = action("Lift", BONE, {0: [(1, -2.0), (10, -2.0)], 2: [(1, 3.0), (10, 6.0)]}, "Bone")
anim_rigs = []  # (nome, camadas usadas)


def anim(name, specs):
    """specs: lista de (sensor, kwargs do actuator Action). Props 'fa', 'fb'... recebem o quadro."""
    o = rig(name, (len(anim_rigs) % 6 - 3, 3 + len(anim_rigs) // 6, 0))
    layers = []
    for i, (sens, kw) in enumerate(specs):
        fp = "f" + "abc"[i]
        prop(o, fp, 'FLOAT', 0.0)
        s = window(o, "On" + "ABC"[i], *sens) if sens else always(o, "On" + "ABC"[i])
        wire(o, "Go" + "ABC"[i], [s], [actuator(o, 'ACTION', "Anim" + "ABC"[i], frame_property=fp, **kw)])
        if kw.get("layer", 0) not in layers:
            layers.append(kw.get("layer", 0))
    anim_rigs.append((name, layers, len(specs)))
    return o


# Blendin em cada modo. Janela positiva de 10 a 70 (repete): pulsos nos dois sentidos.
for pm, win, blend in (('PLAY', (10, 60, True), 6), ('PINGPONG', (10, 60, True), 6), ('FLIPPER', (10, 30, True), 6),
                       ('LOOPSTOP', (10, 60, True), 6), ('LOOPEND', (10, 6, True), 12)):
    anim("B_" + pm, [(win, dict(action=slide, play_mode=pm, frame_start=1, frame_end=20, frame_blend_in=blend))])
# Property com Blendin: o quadro vem de uma propriedade que anda 0.25 por tic.
o = anim("B_PROPERTY", [(None, dict(action=slide, play_mode='PROPERTY', property="pos", frame_start=1, frame_end=20,
                                    frame_blend_in=5))])
prop(o, "pos", 'FLOAT', 1.0)
wire(o, "Count", [always(o)], [actuator(o, 'PROPERTY', "Inc", mode='ADD', property="pos", value="0.25")])
# Continue: retoma do ultimo quadro.
anim("C_FLIPPER", [((10, 20, True), dict(action=slide, play_mode='FLIPPER', frame_start=1, frame_end=20,
                                         frame_blend_in=4, use_continue_last_frame=True))])
anim("C_LOOPSTOP", [((10, 20, True), dict(action=slide, play_mode='LOOPSTOP', frame_start=1, frame_end=20,
                                          frame_blend_in=4, use_continue_last_frame=True))])
anim("C_LOOPEND", [((10, 35, True), dict(action=slide, play_mode='LOOPEND', frame_start=1, frame_end=12,
                                         frame_blend_in=3, use_continue_last_frame=True))])

# Duas camadas no mesmo objeto, com Layer Weight e Blend Mode.
anim("L_BLEND", [((5, 200), dict(action=slide, play_mode='LOOPSTOP', frame_start=1, frame_end=20)),
                 ((20, 30, True), dict(action=lift, play_mode='PINGPONG', frame_start=1, frame_end=10, layer=1,
                                       layer_weight=0.4, blend_mode='BLEND', frame_blend_in=4))])
anim("L_ADD", [((5, 100), dict(action=slide, play_mode='LOOPEND', frame_start=1, frame_end=20, frame_blend_in=3)),
               ((30, 40, True), dict(action=lift, play_mode='FLIPPER', frame_start=1, frame_end=10, layer=2,
                                     layer_weight=0.7, blend_mode='ADD'))])
anim("L_THREE", [((5, 50, True), dict(action=slide, play_mode='PLAY', frame_start=1, frame_end=20, layer=3,
                                      layer_weight=0.5)),
                 ((15, 25, True), dict(action=lift, play_mode='LOOPSTOP', frame_start=1, frame_end=10, layer=1,
                                       layer_weight=0.25, blend_mode='ADD', frame_blend_in=2)),
                 ((40, 20, True), dict(action=slide, play_mode='LOOPEND', frame_start=20, frame_end=1, layer=0))])

# Mesma camada, prioridades diferentes (numero menor ganha).
anim("P_A", [((10, 150), dict(action=slide, play_mode='LOOPSTOP', frame_start=1, frame_end=20, priority=5)),
             ((40, 5), dict(action=lift, play_mode='PLAY', frame_start=1, frame_end=10, priority=1))])
anim("P_B", [((10, 40), dict(action=lift, play_mode='LOOPEND', frame_start=1, frame_end=10, priority=1)),
             ((20, 15, True), dict(action=slide, play_mode='FLIPPER', frame_start=1, frame_end=20, priority=5,
                                   frame_blend_in=3))])
# Mesma acao nos dois actuators (faixas diferentes).
anim("P_C", [((10, 40, True), dict(action=slide, play_mode='FLIPPER', frame_start=1, frame_end=10, priority=1)),
             ((25, 30, True), dict(action=slide, play_mode='LOOPEND', frame_start=10, frame_end=20, priority=3))])
# Mesma prioridade: o ultimo a tocar leva a camada.
anim("P_D", [((10, 10, True), dict(action=slide, play_mode='PLAY', frame_start=1, frame_end=20, priority=2)),
             ((25, 10, True), dict(action=lift, play_mode='PINGPONG', frame_start=1, frame_end=10, priority=2,
                                   frame_blend_in=3))])
# Actuators identicos: a engine recusa tocar de novo a mesma acao com os mesmos parametros.
anim("P_E", [((10, 5), dict(action=slide, play_mode='PLAY', frame_start=1, frame_end=20)),
             ((30, 5, True), dict(action=slide, play_mode='PLAY', frame_start=1, frame_end=20))])
anim("P_F", [((10, 100, True), dict(action=slide, play_mode='LOOPSTOP', frame_start=1, frame_end=20, priority=4)),
             ((30, 20, True), dict(action=lift, play_mode='LOOPSTOP', frame_start=1, frame_end=10, priority=2))])
anim("P_G", [((10, 30, True), dict(action=slide, play_mode='LOOPEND', frame_start=1, frame_end=20, priority=4)),
             ((22, 8, True), dict(action=slide, play_mode='PLAY', frame_start=1, frame_end=20, priority=6)),
             ((50, 10, True), dict(action=lift, play_mode='PINGPONG', frame_start=1, frame_end=10, priority=0))])
anim("P_H", [((10, 30, True), dict(action=slide, play_mode='PINGPONG', frame_start=1, frame_end=20, priority=3)),
             ((20, 12, True), dict(action=lift, play_mode='PROPERTY', property="pos", frame_start=1, frame_end=10,
                                   priority=1))])
prop(bpy.data.objects["P_H"], "pos", 'FLOAT', 4.0)

# Action de objeto (IPO): duas camadas e conflito de prioridade.
oslide = action("ObjSlide", "location", {0: [(1, 0.0), (20, 6.0)]})
olift = action("ObjLift", "location", {2: [(1, 1.0), (10, 4.0)]})
obj_anims = []
for name, specs in (
        ("O_L", [((10, 60, True), dict(action=oslide, play_mode='LOOPEND', frame_start=1, frame_end=20)),
                 ((25, 20, True), dict(action=olift, play_mode='PINGPONG', frame_start=1, frame_end=10, layer=1))]),
        ("O_P", [((10, 25, True), dict(action=oslide, play_mode='FLIPPER', frame_start=1, frame_end=20, priority=3)),
                 ((30, 5, True), dict(action=olift, play_mode='PLAY', frame_start=1, frame_end=10, priority=1))])):
    o = cube(name, (0, -4 - 2 * len(obj_anims), 0), scale=(0.3, 0.3, 0.3))
    for i, (sens, kw) in enumerate(specs):
        prop(o, "f" + "ab"[i], 'FLOAT', 0.0)
        wire(o, "Go" + "AB"[i], [window(o, "On" + "AB"[i], *sens)],
             [actuator(o, 'ACTION', "Anim" + "AB"[i], frame_property="f" + "ab"[i], **kw)])
    obj_anims.append(name)

# ---------------------------------------------------------------------------------------------------------
# Armature sensor: IK iTaSC de dois bones; o alvo sai do alcance, gira e volta.
goal = cube("IKGoal", (5, 0, 1.5), scale=(0.2, 0.2, 0.2))
wire(goal, "Out", [window(goal, "W1", 20, 60)], [actuator(goal, 'MOTION', "Away", offset_location=(0.06, 0, 0),
                                                         offset_rotation=(0, 0.02, 0))])
wire(goal, "Back", [window(goal, "W2", 100, 60)], [actuator(goal, 'MOTION', "Home", offset_location=(-0.06, 0, 0),
                                                           offset_rotation=(0, -0.02, 0))])
ik = rig("IKRig", (4, 0, 0), tip=True)
ik.pose.ik_solver = 'ITASC'
con = ik.pose.bones["Tip"].constraints.new('IK')
con.name = "IK"
con.target = goal
con.chain_count = 2
con.use_rotation = True
follow = ik.pose.bones["Bone"].constraints.new('COPY_SCALE')
follow.name = "Plain"
follow.target = goal
wire(ik, "Run", [always(ik)], [actuator(ik, 'ARMATURE', "Run", mode='RUN')])
ik_props = []


def arm_count(o, pname, bone, constraint, test, value=0.0, level=False, invert=False):
    prop(o, pname)
    s = sensor(o, 'ARMATURE', "S_" + pname, bone=bone, constraint=constraint, test_type=test, value=value,
               use_pulse_true_level=level, invert=invert)
    wire(o, "C_" + pname, [s], [actuator(o, 'PROPERTY', "A_" + pname, mode='ADD', property=pname, value="1")])


for pname, args in (("la", ("Tip", "IK", 'LINERRORABOVE', 1.5, True)),
                    ("lb", ("Tip", "IK", 'LINERRORBELOW', 2.0)),
                    ("ra", ("Tip", "IK", 'ROTERRORABOVE', 0.485)),
                    ("rb", ("Tip", "IK", 'ROTERRORBELOW', 0.3, True)),
                    ("st", ("Tip", "IK", 'STATECHG', 0.0)),
                    ("sl", ("Tip", "IK", 'STATECHG', 0.0, True)),
                    ("li", ("Tip", "IK", 'LINERRORABOVE', 2.2, False, True)),
                    ("ri", ("Tip", "IK", 'ROTERRORBELOW', 0.495, True, True)),
                    ("no", ("Tip", "Nope", 'LINERRORBELOW', 0.5, True)),
                    ("ni", ("Tip", "Nope", 'STATECHG', 0.0, False, True)),
                    ("pl", ("Bone", "Plain", 'LINERRORBELOW', 0.5)),
                    ("ps", ("Bone", "Plain", 'STATECHG', 0.0, True))):
    arm_count(ik, pname, *args)
    ik_props.append(pname)
wire(ik, "Off", [window(ik, "At140", 140, 5)],
     [actuator(ik, 'ARMATURE', "Disable", mode='DISABLE', bone="Tip", constraint="IK"),
      actuator(ik, 'ARMATURE', "PlainOff", mode='DISABLE', bone="Bone", constraint="Plain")])
wire(ik, "OnAgain", [window(ik, "At180", 180, 5)],
     [actuator(ik, 'ARMATURE', "Enable", mode='ENABLE', bone="Tip", constraint="IK"),
      actuator(ik, 'ARMATURE', "Weight", mode='SETWEIGHT', bone="Tip", constraint="IK", weight=0.5)])

# IK de distancia (erro linear = distancia - alvo), alvo afastando.
goal2 = cube("DistGoal", (-5, 0, 1.5), scale=(0.2, 0.2, 0.2))
wire(goal2, "Out", [window(goal2, "W1", 30, 80)], [actuator(goal2, 'MOTION', "Away", offset_location=(-0.04, 0, 0.02))])
dist = rig("DistRig", (-4, 0, 0), tip=True)
dist.pose.ik_solver = 'ITASC'
con = dist.pose.bones["Tip"].constraints.new('IK')
con.name = "Dist"
con.ik_type = 'DISTANCE'
con.target = goal2
con.chain_count = 2
con.distance = 0.5
wire(dist, "Run", [always(dist)], [actuator(dist, 'ARMATURE', "Run", mode='RUN')])
dist_props = []
for pname, args in (("da", ("Tip", "Dist", 'LINERRORABOVE', 0.2, True)),
                    ("db", ("Tip", "Dist", 'LINERRORBELOW', 1.0)),
                    ("dn", ("Tip", "Dist", 'LINERRORBELOW', -0.05, True))):
    arm_count(dist, pname, *args)
    dist_props.append(pname)

# ---------------------------------------------------------------------------------------------------------
# Game: Save/Load Config e Screenshot. O Checker troca logic.globalDict['f9'] entre um e outro.
o = cube("Game", (0, -1, 0), scale=(0.2, 0.2, 0.2))
for label, start, kw in (("A", 20, dict(saveloc="f9cfg", extension_name="sav")),
                         ("B", 24, dict(saveloc="f9cfgb")),
                         ("C", 28, dict())):
    wire(o, "Save" + label, [window(o, "S" + label, start, 2)], [actuator(o, 'GAME', "Save" + label, mode='SAVECFG', **kw)])
for label, start, kw in (("A", 50, dict(saveloc="f9cfg", extension_name="sav")),
                         ("B", 70, dict(saveloc="f9cfgb")),
                         ("C", 90, dict()),
                         ("None", 110, dict(saveloc="f9missing", extension_name="sav"))):
    wire(o, "Load" + label, [window(o, "L" + label, start, 2)], [actuator(o, 'GAME', "Load" + label, mode='LOADCFG', **kw)])
if extonly:
    wire(o, "SaveD", [window(o, "SD", 36, 2)], [actuator(o, 'GAME', "SaveD", mode='SAVECFG', extension_name="f9x")])
    wire(o, "LoadD", [window(o, "LD", 115, 2)], [actuator(o, 'GAME', "LoadD", mode='LOADCFG', extension_name="f9x")])
wire(o, "Shot", [window(o, "At125", 125, 2)], [actuator(o, 'GAME', "Shot", mode='SCREENSHOT', filename="//f9shot")])
wire(o, "Shot2", [window(o, "At155", 155, 2)], [actuator(o, 'GAME', "Shot2", mode='SCREENSHOT', filename="//f9shot_#")])

# ---------------------------------------------------------------------------------------------------------
# Filter 2D.
o = cube("Filters", (0, 1, 0), scale=(0.2, 0.2, 0.2))
READY = ('SHARPEN', 'DILATION', 'EROSION', 'LAPLACIAN', 'SOBEL', 'PREWITT', 'GRAYSCALE', 'SEPIA', 'INVERT', 'OUTLINE')
wire(o, "Add", [window(o, "At10", 10, 5)],
     [actuator(o, 'FILTER_2D', m.title(), mode=m, filter_pass=i + 1, use_mipmap=(i % 3 == 0))
      for i, m in enumerate(READY)])
wire(o, "Builtin", [window(o, "At20", 20, 5)],
     [actuator(o, 'FILTER_2D', m.title(), mode=m) for m in ('BLOOM', 'TONEMAP', 'SSAO', 'LIGHTSCATTER', 'SSR')])
wire(o, "Blur", [window(o, "At30", 30, 5)],
     [actuator(o, 'FILTER_2D', "MBlurOn", mode='MOTIONBLUR', use_motion_blur=True, motion_blur_factor=0.6)])
wire(o, "Off", [window(o, "At40", 40, 5)],
     [actuator(o, 'FILTER_2D', "Off3", mode='DISABLE', filter_pass=3),
      actuator(o, 'FILTER_2D', "Off7", mode='DISABLE', filter_pass=7),
      actuator(o, 'FILTER_2D', "OffNone", mode='DISABLE', filter_pass=15)])
wire(o, "Del", [window(o, "At60", 60, 5)],
     [actuator(o, 'FILTER_2D', "Del5", mode='REMOVE', filter_pass=5),
      actuator(o, 'FILTER_2D', "DelNone", mode='REMOVE', filter_pass=16)])
wire(o, "On", [window(o, "At80", 80, 5)],
     [actuator(o, 'FILTER_2D', "On3", mode='ENABLE', filter_pass=3),
      actuator(o, 'FILTER_2D', "OnNone", mode='ENABLE', filter_pass=5)])
wire(o, "Blur2", [window(o, "At90", 90, 5)],
     [actuator(o, 'FILTER_2D', "MBlurValue", mode='MOTIONBLUR', use_motion_blur=True, motion_blur_factor=0.2)])
# Passe ja ocupado: o actuator nao troca o filtro existente.
wire(o, "Again", [window(o, "At100", 100, 5)],
     [actuator(o, 'FILTER_2D', "Again1", mode='INVERT', filter_pass=1),
      actuator(o, 'FILTER_2D', "Again5", mode='SEPIA', filter_pass=5)])
wire(o, "BlurOff", [window(o, "At150", 150, 5)],
     [actuator(o, 'FILTER_2D', "MBlurOff", mode='MOTIONBLUR', use_motion_blur=False)])

checker = bpy.data.objects.new("Checker", None)
scene.objects.link(checker)
text = bpy.data.texts.new("checker.py")
text.from_string(('POST = %d\nANIMS = %r\nOBJS = %r\nIKP = %r\nDISTP = %r\nNPASS = %d' % (
    post, anim_rigs, obj_anims, ik_props, dist_props, len(READY))) + '''
from Range import logic
import os
cont = logic.getCurrentController()
own = cont.owner
own['frames'] = own.get('frames', 0) + 1
n = own['frames']
o = own.scene.objects
gd = logic.globalDict
folder = logic.expandPath('//')
MINE = ('f9cfg.sav', 'f9cfgb.save', 'f9shot')
def mine():
    stem = os.path.splitext(os.path.basename(own.get('blend', '')))[0]
    return sorted(f for f in os.listdir(folder)
                  if f.startswith(MINE) or (stem and f == stem + '.save') or f in ('.save', 'f9cfgb', '.f9x', stem + '.f9x'))
if n == 1:
    # Sobras de uma rodada anterior na mesma pasta.
    names = [f for f in os.listdir(folder) if f.endswith('.range')]
    own['blend'] = names[0] if len(names) == 1 else ''
    for f in mine():
        os.remove(os.path.join(folder, f))
# Valores do globalDict entre os Save (20, 24, 28) e os Load (50, 70, 90, 110); cada troca vem depois
# da amostra que mostra o valor carregado.
for frame, value in ((5, 111), (22, 333), (26, 444), (32, 222), (62, 555), (82, 666), (102, 777)):
    if n == frame:
        gd['f9'] = value
        if frame == 32:
            gd['extra'] = 1
def sample(n):
    v = lambda vec: ','.join('%.2f' % x for x in vec)
    fm = own.scene.filterManager
    parts = ['f=%d' % n]
    for name, layers, count in ANIMS:
        r = o[name]
        loc = r.channels['Bone'].location
        tag = o[name + '_tag'].worldPosition
        parts.append('%s=%.2f,%.2f,%.2f,%.2f/%s/%s' % (
            name, loc[0], loc[2], tag.x, tag.z, ','.join('%.1f' % r['f' + 'abc'[i]] for i in range(count)),
            ','.join('%s:%.1f:%d' % (r.getActionName(l)[:1] or '-', r.getActionFrame(l), r.isPlayingAction(l))
                     for l in layers)))
    for name in OBJS:
        r = o[name]
        parts.append('%s=%s/%.1f,%.1f/%s' % (
            name, v(r.worldPosition), r['fa'], r['fb'],
            ','.join('%s:%.1f:%d' % (r.getActionName(l)[3:4] or '-', r.getActionFrame(l), r.isPlayingAction(l))
                     for l in (0, 1))))
    r = o['IKRig']
    c = r.constraints['Tip:IK']
    parts.append('ik=%.2f/%.2f/%s/%.2f goal=%.2f tip=%s %s' % (c.lin_error, c.rot_error, c.active, c.ik_weight,
                                                      o['IKGoal'].worldPosition.x, v(o['IKRig_tag'].worldPosition),
                                                      ' '.join('%s=%d' % (p, r[p]) for p in IKP)))
    r = o['DistRig']
    parts.append('dist=%.2f tip=%s %s' % (r.constraints['Tip:Dist'].lin_error, v(o['DistRig_tag'].worldPosition),
                                   ' '.join('%s=%d' % (p, r[p]) for p in DISTP)))
    parts.append('gd=%s/%s/%d' % (gd.get('f9'), 'extra' in gd, len(gd)))
    parts.append('files=%s' % ','.join('GAME.save' if own['blend'] and f == os.path.splitext(own['blend'])[0] + '.save' else f
                                       for f in mine()) or 'files=')
    passes = []
    for i in range(1, NPASS + 1):
        f = fm.getFilter(i)
        passes.append('-' if f is None else '%s%d' % ('E' if f.enabled else 'D', f.mipmap))
    parts.append('pass=%s fxaa=%s grain=%s' % (''.join(passes), fm.fxaaEnabled, fm.grainEnabled))
    own['log'] = own.get('log', '') + ' '.join(parts) + '\\n'
def after_frame():
    n = own['frames']
    if n > 0 and n % 10 == 0 and own.get('sampled') != n:
        own['sampled'] = n
        sample(n)
if POST:
    if not own.get('hooked'):
        own['hooked'] = True
        own.scene.post_draw.append(after_frame)
else:
    after_frame()
if n == 240 + POST:
    # So confere que as capturas existem: o conteudo da imagem muda de uma rodada para outra ate entre
    # duas rodadas iguais de bricks, entao nao serve para comparar o Motion Blur.
    shots = sorted(f for f in mine() if f.startswith('f9shot'))
    own['log'] += 'end shots=%s\\n' %','.join(shots)
    print(own['log'], flush=True)
    with open(logic.expandPath('//' + own.scene.name + '_check_f9.txt'), 'w', encoding='utf-8') as f:
        f.write(own['log'])
    for f in mine():
        os.remove(os.path.join(folder, f))
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
        if only is not None and o.name not in only:
            continue
        scene.objects.active = o
        print("CONVERT", o.name, bpy.ops.logic.convert_to_component(mode=mode))
    for t in bpy.data.texts:
        left += [(t.name, ln.strip()) for ln in t.as_string().splitlines() if "# TODO:" in ln]
    print("LEFT_AS_BRICK", len(left), left)
    for t in bpy.data.texts:
        if t.name != "checker.py":
            with open(output + "." + t.name + ".txt", 'w', encoding='utf-8') as f:
                f.write(t.as_string())

bpy.ops.wm.save_as_mainfile(filepath=output)
