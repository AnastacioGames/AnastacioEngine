"""Logic Bricks -> Python F6: sensores e actuators ligados entre objetos (Ray material+x-ray, Collision, Near,
Radar, Movement, Delay em segundos, Sound ping-pong/loop/3D e Track To com pai em outro objeto).

Run with:  RangeEngine -b --python tools/create_logic_convert_scene_f6.py -- <output.range> [convert[:MODULE|SCRIPT]]
O objeto "Driver" tem os controllers e as propriedades-resultado; os sensores ficam em Scanner (Ray), Bumper
(Collision), Sentry (Near), Radar e Mover (Movement); os actuators Sound em Speaker e Track To em Turret (filho
de Base). Com "convert" so o Driver e convertido. Rodar o .range sem e com "convert" no RangeRuntime deve imprimir a
mesma linha CHECK, e LEFT_AS_BRICK deve ser 0. O CHECK so le valores estaveis (propriedades que ficam em 1 e
orientacao do Turret parado), para nao depender da ordem de leitura do Checker.
"""
import bpy
import math
import os
import struct
import sys
import wave

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = argv[0] if argv else "logic_convert_f6.range"
convert = len(argv) > 1 and argv[1].startswith("convert")
mode = argv[1].split(":", 1)[1] if convert and ":" in argv[1] else "COMPONENT"

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'


def cube(name, loc, ptype='NO_COLLISION', scale=(1, 1, 1), actor=False):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    o = bpy.context.active_object
    o.name = name
    o.scale = scale
    o.game.physics_type = ptype
    o.game.use_actor = actor
    return o


def material(name):
    # Reaproveita pelo nome: dois materials.new("Red") dariam "Red" e "Red.001", e o Ray
    # por material (que compara o nome) nunca dispararia no segundo objeto.
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
    return m


driver = cube("Driver", (0, 0, 0))
scene.objects.active = driver
for pname in ("rayx", "rayplain", "col", "near", "radar", "moved", "delayed"):
    bpy.ops.object.game_property_new(type='INT', name=pname)

# --- Ray: Scanner (z=10) olha para -Z; Glass (z=6, material Clear) fica na frente da Wall (z=0, material Red).
scanner = cube("Scanner", (40, 0, 10))
glass = cube("Glass", (40, 0, 6), 'STATIC', (2, 2, 0.2))
wall = cube("RedWall", (40, 0, 0), 'STATIC', (2, 2, 0.5))
glass.data.materials.append(material("Clear"))
wall.data.materials.append(material("Red"))
scanner2 = cube("Scanner2", (50, 0, 10))
glass2 = cube("Glass2", (50, 0, 6), 'STATIC', (2, 2, 0.2))
glass2.data.materials.append(material("Red"))  # sem x-ray o primeiro objeto atingido ja tem o material

# --- Collision: Bumper cai sobre o Floor.
floor = cube("Floor", (0, 40, -2), 'STATIC', (10, 10, 1))
bumper = cube("Bumper", (0, 40, 1), 'RIGID_BODY')

# --- Near / Radar: Intruder (Actor com a propriedade "intruder") perto das sentinelas.
intruder = cube("Intruder", (60, 0, 0), 'STATIC', actor=True)
scene.objects.active = intruder
bpy.ops.object.game_property_new(type='BOOL', name="intruder")
sentry = cube("Sentry", (63, 0, 0), 'STATIC', actor=True)
radar = cube("Radar", (60, -4, 0), 'STATIC', actor=True)  # olha para +Y, onde esta o Intruder

# --- Movement: Mover anda sozinho (bricks proprios, que ficam como estao).
mover = cube("Mover", (-20, 0, 0))

# --- Track To com pai: Turret (filho de Base girada) mira o Target.
base = cube("Base", (0, -30, 0))
base.rotation_euler = (0.0, 0.0, math.radians(40))
turret = cube("Turret", (0, -30, 2))
turret.parent = base
turret.matrix_parent_inverse = base.matrix_world.inverted()
target = cube("Target", (10, -20, 6))

# --- Sound: arquivo wav gerado ao lado do .range.
wav = os.path.join(os.path.dirname(os.path.abspath(output)), "f6_tone.wav")
with wave.open(wav, "wb") as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(8000)
    w.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(i * 0.1))) for i in range(4000)))
snd = bpy.data.sounds.load(wav)
speaker = cube("Speaker", (-40, 0, 0))

scene.objects.active = driver


def sensor(owner, type_, name):
    bpy.ops.logic.sensor_add(type=type_, name=name, object=owner.name)
    return owner.game.sensors[name]


def actuator(owner, type_, name):
    bpy.ops.logic.actuator_add(type=type_, name=name, object=owner.name)
    return owner.game.actuators[name]


def wire(cname, sens, acts):
    bpy.ops.logic.controller_add(type='LOGIC_AND', name=cname, object=driver.name)
    c = driver.game.controllers[cname]
    c.states = 1
    for s in (sens if isinstance(sens, (list, tuple)) else [sens]):
        s.link(c)
    for a in acts:
        c.link(actuator=a)
    return c


def setter(prop):
    a = actuator(driver, 'PROPERTY', "Set_" + prop)
    a.mode = 'ASSIGN'
    a.property = prop
    a.value = "1"
    return a


# Ray com material + x-ray: enxerga a RedWall atraves do Glass.
s = sensor(scanner, 'RAY', "RayX")
s.ray_type = 'MATERIAL'
s.material = "Red"
s.use_x_ray = True
s.axis = 'NEGZAXIS'
s.range = 20.0
s.use_pulse_true_level = True
wire("RayXC", s, [setter("rayx")])
# Ray com material sem x-ray: o Glass2 (primeiro atingido) tem o material.
s = sensor(scanner2, 'RAY', "RayPlain")
s.ray_type = 'MATERIAL'
s.material = "Red"
s.use_x_ray = False
s.axis = 'NEGZAXIS'
s.range = 20.0
s.use_pulse_true_level = True
wire("RayPlainC", s, [setter("rayplain")])

s = sensor(bumper, 'COLLISION', "Hit")
wire("HitC", s, [setter("col")])

s = sensor(sentry, 'NEAR', "Close")
s.property = "intruder"
s.distance = 5.0
s.reset_distance = 6.0
s.use_pulse_true_level = True
wire("CloseC", s, [setter("near")])

s = sensor(radar, 'RADAR', "Cone")
s.property = "intruder"
s.axis = 'YAXIS'
s.angle = 90.0
s.distance = 10.0
s.use_pulse_true_level = True
wire("ConeC", s, [setter("radar")])

# Movement do Mover (que anda com Motion nos bricks proprios dele).
bpy.ops.logic.sensor_add(type='ALWAYS', name="Go", object=mover.name)
bpy.ops.logic.controller_add(type='LOGIC_AND', name="GoC", object=mover.name)
bpy.ops.logic.actuator_add(type='MOTION', name="Walk", object=mover.name)
mover.game.actuators["Walk"].offset_location = (0.02, 0.0, 0.0)
mover.game.sensors["Go"].use_pulse_true_level = True
mover.game.sensors["Go"].link(mover.game.controllers["GoC"])
mover.game.controllers["GoC"].link(actuator=mover.game.actuators["Walk"])
s = sensor(mover, 'MOVEMENT', "Moving")
s.axis = 'XAXIS'
s.threshold = 0.001
s.use_pulse_true_level = True
wire("MovingC", s, [setter("moved")])

# Delay em segundos (no Driver): fica positivo depois de 1 s (o Checker le aos 120 frames).
s = sensor(driver, 'DELAY', "Wait")
s.use_deltatime = True
s.delay = 1
s.duration = 0
s.use_repeat = False
wire("WaitC", s, [setter("delayed")])

# Actuators em outros objetos que usavam helpers do componente.
s_tick = sensor(driver, 'ALWAYS', "Tick")
s_tick.use_pulse_true_level = True
a = actuator(turret, 'EDIT_OBJECT', "Aim")
a.mode = 'TRACKTO'
a.object = target
a.track_axis = 'TRACKAXISY'
a.up_axis = 'UPAXISZ'
a.use_3d_tracking = True
a.time = 0
wire("AimC", s_tick, [a])

for name, mode_, three_d in (("Loop", 'LOOPEND', False), ("PingPong", 'LOOPBIDIRECTIONAL', False),
                             ("Pos3D", 'LOOPSTOP', True)):
    a = actuator(speaker, 'SOUND', name)
    a.sound = snd
    a.mode = mode_
    a.use_sound_3d = three_d
    a.volume = 0.0  # mudo: o teste nao depende de dispositivo de audio
    wire("Snd" + name, s_tick, [a])

checker = bpy.data.objects.new("Checker", None)
scene.objects.link(checker)
scene.objects.active = checker
text = bpy.data.texts.new("checker.py")
text.from_string(
    "from Range import logic\n"
    "cont = logic.getCurrentController()\n"
    "own = cont.owner\n"
    "own['frames'] = own.get('frames', 0) + 1\n"
    "if own['frames'] == 120:\n"
    "    o = own.scene.objects\n"
    "    d = o['Driver']\n"
    "    ori = lambda ob: ','.join('%.2f' % x for row in ob.worldOrientation for x in row)\n"
    "    line = 'CHECK rayx=%s rayplain=%s col=%s near=%s radar=%s moved=%s delayed=%s turret=%s' % (\n"
    "        d['rayx'], d['rayplain'], d['col'], d['near'], d['radar'], d['moved'], d['delayed'],\n"
    "        ori(o['Turret']))\n"
    "    print(line, flush=True)\n"
    "    with open(logic.expandPath('//' + own.scene.name + '_check_f6.txt'), 'w') as f:\n"
    "        f.write(line + '\\n')\n"
    "    logic.endGame()\n")
bpy.ops.logic.sensor_add(type='ALWAYS', name="Frame", object=checker.name)
checker.game.sensors["Frame"].use_pulse_true_level = True
bpy.ops.logic.controller_add(type='PYTHON', name="Check", object=checker.name)
checker.game.controllers["Check"].text = text
checker.game.sensors["Frame"].link(checker.game.controllers["Check"])

if convert:
    scene.objects.active = driver
    print("CONVERT", driver.name, bpy.ops.logic.convert_to_component(mode=mode))
    print(bpy.data.texts["driver_logic.py"].as_string())
    todos = [(t.name, ln.strip()) for t in bpy.data.texts for ln in t.as_string().splitlines() if "# TODO:" in ln]
    print("LEFT_AS_BRICK", len(todos), todos)

bpy.ops.wm.save_as_mainfile(filepath=output)
