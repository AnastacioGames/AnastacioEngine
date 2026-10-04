"""Logic Bricks -> Python Component test scene.

Run with:  RangeEngine -b --python tools/create_logic_convert_scene.py -- <output.range> [convert[:MODULE|SCRIPT]]
With "convert" the bricks of "Player" are converted by logic.convert_to_component
before saving. Running both files in RangeRuntime must print the same CHECK line.
"""
import bpy
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = argv[0] if argv else "logic_convert_test.range"
convert = len(argv) > 1 and argv[1].startswith("convert")
mode = argv[1].split(":", 1)[1] if convert and ":" in argv[1] else "COMPONENT"

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'

bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0))
player = bpy.context.active_object
player.name = "Player"
player.game.physics_type = 'NO_COLLISION'
for name, ptype in (("score", 'INT'), ("ticks", 'INT'), ("alive", 'BOOL'),
                    ("pulses", 'INT'), ("saw", 'INT')):
    bpy.ops.object.game_property_new(type=ptype, name=name)

# Bullet fica na camada 2 (inativa) para o Add Object; Wall em +X com a propriedade "wall".
bpy.ops.mesh.primitive_cube_add(location=(0, 5, 0), layers=[i == 1 for i in range(20)])
bullet = bpy.context.active_object
bullet.name = "Bullet"
bullet.game.physics_type = 'NO_COLLISION'
bpy.ops.mesh.primitive_cube_add(location=(20, 0, 0))
wall = bpy.context.active_object
wall.name = "Wall"
wall.game.physics_type = 'STATIC'
bpy.ops.object.game_property_new(type='BOOL', name="wall")
wall.data.materials.append(bpy.data.materials.new("WallMat"))
scene.objects.active = player


def brick(kind, type_, name, state=1):
    getattr(bpy.ops.logic, kind + "_add")(type=type_, name=name, object=player.name)
    item = getattr(player.game, kind + "s")[name]
    if kind == "controller":
        item.states = state
    return item


def link(sensors, cont, actuators):
    for s in sensors:
        s.link(cont)
    for a in actuators:
        cont.link(actuator=a)


# Estado 1: soma 10 uma vez e passa para o estado 2.
s_start = brick("sensor", 'ALWAYS', "Start")
c_start = brick("controller", 'LOGIC_AND', "Init", 1)
a_score = brick("actuator", 'PROPERTY', "Score")
a_score.mode = 'ADD'
a_score.property = "score"
a_score.value = "10"
a_to2 = brick("actuator", 'STATE', "GoState2")
a_to2.operation = 'SET'
a_to2.states[1] = True
link([s_start], c_start, [a_score, a_to2])

# Estado 2: pulso todo frame conta ticks e anda em X.
s_tick = brick("sensor", 'ALWAYS', "Tick")
s_tick.use_pulse_true_level = True
c_tick = brick("controller", 'LOGIC_AND', "Tick", 2)
a_ticks = brick("actuator", 'PROPERTY', "Ticks")
a_ticks.mode = 'ADD'
a_ticks.property = "ticks"
a_ticks.value = "1"
a_move = brick("actuator", 'MOTION', "Move")
a_move.offset_location = (0.1, 0.0, 0.0)
link([s_tick], c_tick, [a_ticks, a_move])

# ticks > 30: liga alive e volta ao estado 3 (parado).
s_ticks = brick("sensor", 'PROPERTY', "TicksDone")
# O enum de avaliacao depende do tipo da propriedade: definir a propriedade antes.
s_ticks.property = "ticks"
s_ticks.evaluation_type = 'PROPGREATERTHAN'
s_ticks.value = "30"
c_done = brick("controller", 'LOGIC_AND', "Done", 2)
a_alive = brick("actuator", 'PROPERTY', "Alive")
a_alive.mode = 'TOGGLE'
a_alive.property = "alive"
a_to3 = brick("actuator", 'STATE', "GoState3")
a_to3.operation = 'SET'
a_to3.states[2] = True
link([s_ticks], c_done, [a_alive, a_to3])

# Estado 3: Delay (5 off, 3 on, repete) + Expression; cada pulso soma e cria uma Bullet.
s_wait = brick("sensor", 'DELAY', "Wait")
s_wait.delay = 5
s_wait.duration = 3
s_wait.use_repeat = True
c_expr = brick("controller", 'EXPRESSION', "WaitAlive", 3)
c_expr.expression = "Wait AND alive"
a_pulses = brick("actuator", 'PROPERTY', "Pulses")
a_pulses.mode = 'ADD'
a_pulses.property = "pulses"
a_pulses.value = "1"
a_spawn = brick("actuator", 'EDIT_OBJECT', "Spawn")
a_spawn.mode = 'ADDOBJECT'
a_spawn.object = bullet
link([s_wait], c_expr, [a_pulses, a_spawn])

# Estado 2: Ray em +X enxerga a Wall (propriedade "wall").
s_ray = brick("sensor", 'RAY', "SeeWall")
s_ray.axis = 'XAXIS'
s_ray.range = 100.0
s_ray.property = "wall"
c_ray = brick("controller", 'LOGIC_AND', "Saw", 2)
a_saw = brick("actuator", 'PROPERTY', "SawWall")
a_saw.mode = 'ADD'
a_saw.property = "saw"
a_saw.value = "1"
link([s_ray], c_ray, [a_saw])

# Mesmo Ray, mas filtrando pelo material "WallMat".
bpy.ops.object.game_property_new(type='INT', name="sawmat")
s_raym = brick("sensor", 'RAY', "SeeWallMat")
s_raym.axis = 'XAXIS'
s_raym.range = 100.0
s_raym.ray_type = 'MATERIAL'
s_raym.material = "WallMat"
c_raym = brick("controller", 'LOGIC_AND', "SawMat", 2)
a_sawm = brick("actuator", 'PROPERTY', "SawWallMat")
a_sawm.mode = 'ADD'
a_sawm.property = "sawmat"
a_sawm.value = "1"
link([s_raym], c_raym, [a_sawm])

# Random (sequencia difere da engine; fica fora da linha CHECK, so precisa rodar sem erro).
bpy.ops.object.game_property_new(type='INT', name="coin")
s_rnd = brick("sensor", 'RANDOM', "Coin")
s_rnd.seed = 7
c_rnd = brick("controller", 'LOGIC_AND', "Coin", 2)
a_coin = brick("actuator", 'PROPERTY', "Coin")
a_coin.mode = 'ADD'
a_coin.property = "coin"
a_coin.value = "1"
link([s_rnd], c_rnd, [a_coin])

# Som em loop enquanto o Delay esta ligado (para no pulso negativo). Gera um wav curto.
import os, wave
wav_path = os.path.join(os.path.dirname(os.path.abspath(output)), "logic_convert_beep.wav")
with wave.open(wav_path, "wb") as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(22050)
    w.writeframes(b"\0\0" * 2205)
c_snd = brick("controller", 'LOGIC_AND', "Beep", 3)
a_snd = brick("actuator", 'SOUND', "Beep")
a_snd.sound = bpy.data.sounds.load(wav_path)
a_snd.mode = 'LOOPSTOP'
link([s_wait], c_snd, [a_snd])

# Tecla W (so validacao da traducao; nao ha teclado no teste automatico).
s_key = brick("sensor", 'KEYBOARD', "KeyW")
s_key.key = 'W'
c_key = brick("controller", 'LOGIC_OR', "Walk", 1)
a_walk = brick("actuator", 'MOTION', "Walk")
a_walk.offset_location = (0.0, 0.1, 0.0)
a_walk.use_local_location = True
link([s_key], c_key, [a_walk])

# Message: Tick manda "hit" para o proprio Player; o sensor Message soma msgs no frame seguinte.
bpy.ops.object.game_property_new(type='INT', name="msgs")
a_send = brick("actuator", 'MESSAGE', "SendHit")
a_send.subject = "hit"
a_send.to_property = "Player"
c_tick.link(actuator=a_send)
s_msg = brick("sensor", 'MESSAGE', "GotHit")
s_msg.subject = "hit"
c_msg = brick("controller", 'LOGIC_AND', "GotHit", 2)
a_msgs = brick("actuator", 'PROPERTY', "Msgs")
a_msgs.mode = 'ADD'
a_msgs.property = "msgs"
a_msgs.value = "1"
link([s_msg], c_msg, [a_msgs])

# Links entre objetos: sensor da Box liga no controller do Player, que move a Box e soma nela.
bpy.ops.mesh.primitive_cube_add(location=(0, -5, 0))
box = bpy.context.active_object
box.name = "Box"
box.game.physics_type = 'NO_COLLISION'
bpy.ops.object.game_property_new(type='BOOL', name="ready")
box.game.properties["ready"].value = True
bpy.ops.object.game_property_new(type='INT', name="boxn")
bpy.ops.logic.sensor_add(type='PROPERTY', name="Ready", object=box.name)
s_ready = box.game.sensors["Ready"]
s_ready.property = "ready"
s_ready.evaluation_type = 'PROPEQUAL'
s_ready.value = "True"
bpy.ops.logic.actuator_add(type='PROPERTY', name="BoxN", object=box.name)
a_boxn = box.game.actuators["BoxN"]
a_boxn.mode = 'ADD'
a_boxn.property = "boxn"
a_boxn.value = "1"
bpy.ops.logic.actuator_add(type='MOTION', name="BoxUp", object=box.name)
box.game.actuators["BoxUp"].offset_location = (0.0, 0.0, 0.1)
scene.objects.active = player
c_box = brick("controller", 'LOGIC_AND', "BoxLink", 2)
link([s_ready], c_box, [a_boxn, box.game.actuators["BoxUp"]])

# Camera segue o Player por trás (Camera actuator; convertida junto).
bpy.ops.object.camera_add(location=(-6, -3, 4))
cam = bpy.context.active_object
cam.name = "Cam"
scene.camera = cam
scene.objects.active = cam
bpy.ops.logic.sensor_add(type='ALWAYS', name="Follow", object=cam.name)
bpy.ops.logic.controller_add(type='LOGIC_AND', name="Follow", object=cam.name)
bpy.ops.logic.actuator_add(type='CAMERA', name="Follow", object=cam.name)
a_cam = cam.game.actuators["Follow"]
a_cam.object = player
a_cam.height = 2.0
a_cam.min = 3.0
a_cam.max = 5.0
a_cam.damping = 0.5
a_cam.axis = 'POS_X'
link([cam.game.sensors["Follow"]], cam.game.controllers["Follow"], [a_cam])

# Movement +X (Player anda 0.1 por frame no estado 2), Random constante, Joystick sem controle.
scene.objects.active = player
for name in ("moved", "rv", "joy"):
    bpy.ops.object.game_property_new(type='INT', name=name)
s_mov = brick("sensor", 'MOVEMENT', "MovedX")
s_mov.axis = 'XAXIS'
s_mov.threshold = 0.05
c_mov = brick("controller", 'LOGIC_AND', "MovedX", 2)
a_mov = brick("actuator", 'PROPERTY', "Moved")
a_mov.mode = 'ADD'
a_mov.property = "moved"
a_mov.value = "1"
link([s_mov], c_mov, [a_mov])
c_rv = brick("controller", 'LOGIC_AND', "Rv", 1)
a_rv = brick("actuator", 'RANDOM', "Rv")
a_rv.distribution = 'INT_CONSTANT'
a_rv.property = "rv"
a_rv.int_value = 5
a_mvis = brick("actuator", 'MOUSE', "ShowMouse")
a_mvis.mode = 'VISIBILITY'
a_mvis.visible = True
link([s_start], c_rv, [a_rv, a_mvis])
s_joy = brick("sensor", 'JOYSTICK', "PadA")
s_joy.event_type = 'BUTTONS'
c_joy = brick("controller", 'LOGIC_AND', "PadA", 1)
a_joy = brick("actuator", 'PROPERTY', "Joy")
a_joy.mode = 'ADD'
a_joy.property = "joy"
a_joy.value = "1"
link([s_joy], c_joy, [a_joy])

# Kid: vira filho da Wall (Parent) e roda um Mouse Look com sensibilidade 0 (nao gira).
kid = bpy.data.objects.new("Kid", None)
scene.objects.link(kid)
scene.objects.active = kid
bpy.ops.logic.sensor_add(type='ALWAYS', name="KidGo", object=kid.name)
bpy.ops.logic.controller_add(type='LOGIC_AND', name="KidGo", object=kid.name)
bpy.ops.logic.actuator_add(type='PARENT', name="ToWall", object=kid.name)
kid.game.actuators["ToWall"].object = wall
bpy.ops.logic.actuator_add(type='MOUSE', name="Look", object=kid.name)
a_look = kid.game.actuators["Look"]
a_look.mode = 'LOOK'
a_look.sensitivity_x = 0.0
a_look.sensitivity_y = 0.0
link([kid.game.sensors["KidGo"]], kid.game.controllers["KidGo"], [kid.game.actuators["ToWall"], a_look])
scene.objects.active = player

# F4: Ray por material com x-ray (Veil bloqueia sem x-ray; com x-ray o Ray enxerga o Target atras dele).
for name in ("sawx", "sawn"):
    bpy.ops.object.game_property_new(type='INT', name=name)
for name, z, mat in (("Veil", 10, "VeilMat"), ("Target", 20, "TargetMat")):
    bpy.ops.mesh.primitive_cube_add(location=(0, 0, z))
    o = bpy.context.active_object
    o.name = name
    o.scale = (10, 10, 1)
    o.game.physics_type = 'STATIC'
    o.data.materials.append(bpy.data.materials.new(mat))
scene.objects.active = player
for sname, xray, prop in (("SeeTargetXray", True, "sawx"), ("SeeTargetNoXray", False, "sawn")):
    s_x = brick("sensor", 'RAY', sname)
    s_x.axis = 'ZAXIS'
    s_x.range = 100.0
    s_x.ray_type = 'MATERIAL'
    s_x.material = "TargetMat"
    s_x.use_x_ray = xray
    c_x = brick("controller", 'LOGIC_AND', sname, 2)
    a_x = brick("actuator", 'PROPERTY', sname)
    a_x.mode = 'ADD'
    a_x.property = prop
    a_x.value = "1"
    link([s_x], c_x, [a_x])

# F4: Collision/Near/Radar de outro objeto (Faller, dinamico, cai no Floor) ligados a controllers do Player.
for name in ("landed", "nearw", "radw"):
    bpy.ops.object.game_property_new(type='INT', name=name)
bpy.ops.mesh.primitive_cube_add(location=(0, 0, -5))
floor = bpy.context.active_object
floor.name = "Floor"
floor.scale = (30, 30, 1)
floor.game.physics_type = 'STATIC'
bpy.ops.object.game_property_new(type='BOOL', name="floor")
bpy.ops.mesh.primitive_cube_add(location=(0, 0, -3.5))
faller = bpy.context.active_object
faller.name = "Faller"
faller.scale = (0.5, 0.5, 0.5)
faller.game.physics_type = 'RIGID_BODY'
scene.objects.active = faller
bpy.ops.logic.sensor_add(type='COLLISION', name="Landed", object=faller.name)
s_land = faller.game.sensors["Landed"]
s_land.property = "floor"
bpy.ops.logic.sensor_add(type='NEAR', name="NearWall", object=faller.name)
s_near = faller.game.sensors["NearWall"]
s_near.property = "wall"
s_near.distance = 25.0
s_near.reset_distance = 30.0
bpy.ops.logic.sensor_add(type='RADAR', name="RadarWall", object=faller.name)
s_rad = faller.game.sensors["RadarWall"]
s_rad.property = "wall"
s_rad.axis = 'XAXIS'
s_rad.angle = 90.0
s_rad.distance = 100.0
scene.objects.active = player
for sens, cname, prop in ((s_land, "Landed", "landed"), (s_near, "NearWall", "nearw"), (s_rad, "RadarWall", "radw")):
    c_f = brick("controller", 'LOGIC_AND', cname, 2)
    a_f = brick("actuator", 'PROPERTY', cname)
    a_f.mode = 'ADD'
    a_f.property = prop
    a_f.value = "1"
    link([sens], c_f, [a_f])

# F4: Sound em ping-pong (loop bidirecional, para no pulso negativo).
c_pp = brick("controller", 'LOGIC_AND', "BeepPP", 3)
a_pp = brick("actuator", 'SOUND', "BeepPP")
a_pp.sound = a_snd.sound
a_pp.mode = 'LOOPBIDIRECTIONALSTOP'
link([s_wait], c_pp, [a_pp])

# F4: Track To de objeto com pai (Turret filho do Pivot) olhando o Player, com suavizacao (time=3).
bpy.ops.object.empty_add(location=(0, 8, 0), rotation=(0.0, 0.0, 0.6))
pivot = bpy.context.active_object
pivot.name = "Pivot"
bpy.ops.mesh.primitive_cube_add(location=(0, 8, 0))
turret = bpy.context.active_object
turret.name = "Turret"
turret.game.physics_type = 'NO_COLLISION'
turret.parent = pivot
turret.location = (2, 0, 1)
scene.objects.active = turret
bpy.ops.logic.sensor_add(type='ALWAYS', name="Aim", object=turret.name)
bpy.ops.logic.controller_add(type='LOGIC_AND', name="Aim", object=turret.name)
bpy.ops.logic.actuator_add(type='EDIT_OBJECT', name="Aim", object=turret.name)
a_aim = turret.game.actuators["Aim"]
a_aim.mode = 'TRACKTO'
a_aim.object = player
a_aim.time = 3
a_aim.use_3d_tracking = True
a_aim.track_axis = 'TRACKAXISY'
a_aim.up_axis = 'UPAXISZ'
link([turret.game.sensors["Aim"]], turret.game.controllers["Aim"], [a_aim])
scene.objects.active = player

# Checker: script comum (nao convertido) que imprime o resultado e sai.
checker = bpy.data.objects.new("Checker", None)
scene.objects.link(checker)
scene.objects.active = checker
text = bpy.data.texts.new("checker.py")
text.from_string(
    "from Range import logic\n"
    "cont = logic.getCurrentController()\n"
    "own = cont.owner\n"
    "own['frames'] = own.get('frames', 0) + 1\n"
    "if own['frames'] == 60:\n"
    "    p = logic.getCurrentScene().objects['Player']\n"
    "    bullets = len([o for o in own.scene.objects if o.name == 'Bullet'])\n"
    "    line = 'CHECK score=%d ticks=%d alive=%s state=%d x=%.2f y=%.2f pulses=%d bullets=%d saw=%d sawmat=%d boxn=%d boxz=%.2f msgs=%d cam=%.2f,%.2f,%.2f moved=%d rv=%d joy=%d kid=%s mvis=%s sawx=%d sawn=%d landed=%d nearw=%d radw=%d aim=%s' % (\n"
    "        p['score'], p['ticks'], p['alive'], p.state, p.worldPosition.x, p.worldPosition.y,\n"
    "        p['pulses'], bullets, p['saw'], p['sawmat'], own.scene.objects['Box']['boxn'], own.scene.objects['Box'].worldPosition.z, p['msgs'], *own.scene.objects['Cam'].worldPosition, p['moved'], p['rv'], p['joy'], own.scene.objects['Kid'].parent, logic.mouse.visible,\n"
    "        p['sawx'], p['sawn'], p['landed'], p['nearw'], p['radw'],\n"
    "        ','.join('%.2f' % v for row in own.scene.objects['Turret'].worldOrientation for v in row))\n"
    "    print(line, flush=True)\n"
    "    with open(logic.expandPath('//' + own.scene.name + '_check.txt'), 'w') as f:\n"
    "        f.write(line + '\\n')\n"
    "    logic.endGame()\n")
bpy.ops.logic.sensor_add(type='ALWAYS', name="Frame", object=checker.name)
checker.game.sensors["Frame"].use_pulse_true_level = True
bpy.ops.logic.controller_add(type='PYTHON', name="Check", object=checker.name)
checker.game.controllers["Check"].text = text
checker.game.sensors["Frame"].link(checker.game.controllers["Check"])

if convert:
    for target in (player, cam, kid, turret):
        scene.objects.active = target
        print("CONVERT", target.name, bpy.ops.logic.convert_to_component(mode=mode))
    print(bpy.data.texts["player_logic.py"].as_string())
    print(bpy.data.texts["cam_logic.py"].as_string())
    todos = [(t.name, ln.strip()) for t in bpy.data.texts for ln in t.as_string().splitlines() if "# TODO:" in ln]
    print("LEFT_AS_BRICK", len(todos), todos)

bpy.ops.wm.save_as_mainfile(filepath=output)
