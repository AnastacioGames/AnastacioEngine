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
    "    line = 'CHECK score=%d ticks=%d alive=%s state=%d x=%.2f y=%.2f pulses=%d bullets=%d saw=%d sawmat=%d boxn=%d boxz=%.2f msgs=%d cam=%.2f,%.2f,%.2f' % (\n"
    "        p['score'], p['ticks'], p['alive'], p.state, p.worldPosition.x, p.worldPosition.y,\n"
    "        p['pulses'], bullets, p['saw'], p['sawmat'], own.scene.objects['Box']['boxn'], own.scene.objects['Box'].worldPosition.z, p['msgs'], *own.scene.objects['Cam'].worldPosition)\n"
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
    for target in (player, cam):
        scene.objects.active = target
        print("CONVERT", target.name, bpy.ops.logic.convert_to_component(mode=mode))
    print(bpy.data.texts["player_logic.py"].as_string())
    print(bpy.data.texts["cam_logic.py"].as_string())

bpy.ops.wm.save_as_mainfile(filepath=output)
