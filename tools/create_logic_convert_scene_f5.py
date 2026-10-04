"""Logic Bricks -> Python F5: actuators Camera/Constraint/Steering/Mouse Look de OUTRO objeto.

Run with:  RangeEngine -b --python tools/create_logic_convert_scene_f5.py -- <output.range> [convert[:MODULE|SCRIPT]]
O objeto "Driver" tem os controllers; os actuators ficam em CamHolder (Camera), Slider (Constraint),
Chaser (Steering) e Looker (Mouse Look). Com "convert" so o Driver e convertido e o codigo gerado deve agir
sobre scene.objects[nome] do dono do actuator. Rodar o .range sem e com "convert" no RangeRuntime deve
imprimir a mesma linha CHECK, e LEFT_AS_BRICK deve ser 0.
"""
import bpy
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = argv[0] if argv else "logic_convert_f5.range"
convert = len(argv) > 1 and argv[1].startswith("convert")
mode = argv[1].split(":", 1)[1] if convert and ":" in argv[1] else "COMPONENT"

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'


def cube(name, loc, ptype='NO_COLLISION', scale=(1, 1, 1)):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    o = bpy.context.active_object
    o.name = name
    o.scale = scale
    o.game.physics_type = ptype
    return o


driver = cube("Driver", (0, 0, 0))
target = cube("Target", (10, 5, 2))  # alvo do Camera e do Steering
floor = cube("Floor", (30, 0, -10), 'STATIC', (10, 10, 1))

bpy.ops.object.camera_add(location=(0, -10, 5))
cam_holder = bpy.context.active_object
cam_holder.name = "CamHolder"
slider = cube("Slider", (3, 3, -4))
chaser = cube("Chaser", (-5, 0, 0))
looker = cube("Looker", (0, 20, 0))

scene.objects.active = driver
bpy.ops.logic.sensor_add(type='ALWAYS', name="Tick", object=driver.name)
driver.game.sensors["Tick"].use_pulse_true_level = True
s_tick = driver.game.sensors["Tick"]


def actuator(owner, type_, name):
    bpy.ops.logic.actuator_add(type=type_, name=name, object=owner.name)
    return owner.game.actuators[name]


def wire(cname, act, state=1):
    bpy.ops.logic.controller_add(type='LOGIC_AND', name=cname, object=driver.name)
    c = driver.game.controllers[cname]
    c.states = state
    s_tick.link(c)
    c.link(actuator=act)


# Camera: segue o Target por tras (eixo -Y), altura 2, damping.
a_cam = actuator(cam_holder, 'CAMERA', "Follow")
a_cam.object = target
a_cam.height = 2.0
a_cam.min = 3.0
a_cam.max = 6.0
a_cam.axis = 'NEG_Y'
a_cam.damping = 0.7
wire("CamC", a_cam)

# Constraint (Location): prende Z do Slider entre -2 e 1 com damping.
a_cst = actuator(slider, 'CONSTRAINT', "ClampZ")
a_cst.mode = 'LOC'
a_cst.limit = 'LOCZ'
a_cst.limit_min = -2.0
a_cst.limit_max = 1.0
a_cst.damping = 5
wire("CstC", a_cst)

# Steering (Seek): Chaser persegue o Target.
a_str = actuator(chaser, 'STEERING', "Seek")
a_str.mode = 'SEEK'
a_str.target = target
a_str.distance = 1.0
a_str.velocity = 4.0
a_str.acceleration = 3.0
a_str.turn_speed = 3.0
a_str.self_terminated = False
wire("StrC", a_str)

# Mouse Look: Looker gira com o mouse (sem mouse no teste headless: tem que ficar igual aos bricks).
a_ml = actuator(looker, 'MOUSE', "Look")
a_ml.mode = 'LOOK'
a_ml.use_axis_x = True
a_ml.use_axis_y = True
a_ml.sensitivity_x = 2.0
a_ml.sensitivity_y = 1.5
a_ml.threshold_x = 0.1
a_ml.threshold_y = 0.1
a_ml.min_y = -1.0
a_ml.max_y = 1.0
wire("MouseC", a_ml)

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
    "    o = own.scene.objects\n"
    "    fmt = lambda v: ','.join('%.2f' % x for x in v)\n"
    "    ori = lambda ob: ','.join('%.2f' % x for row in ob.worldOrientation for x in row)\n"
    "    line = 'CHECK cam=%s camori=%s slider=%s chaser=%s chaserori=%s looker=%s' % (\n"
    "        fmt(o['CamHolder'].worldPosition), ori(o['CamHolder']), fmt(o['Slider'].worldPosition),\n"
    "        fmt(o['Chaser'].worldPosition), ori(o['Chaser']), ori(o['Looker']))\n"
    "    print(line, flush=True)\n"
    "    with open(logic.expandPath('//' + own.scene.name + '_check_f5.txt'), 'w') as f:\n"
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
