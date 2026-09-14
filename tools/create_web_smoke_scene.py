"""Run with RangeEngine -b --python tools/create_web_smoke_scene.py."""
import bpy
from mathutils import Vector
from pathlib import Path

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.resolution_x = 640
scene.game_settings.resolution_y = 480
world = bpy.data.worlds.new('Web smoke world')
world.horizon_color = (0.08, 0.15, 0.25)
scene.world = world

bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0))
cube = bpy.context.object
cube.name = 'WebKeyboardCube'
material = bpy.data.materials.new('Orange')
material.diffuse_color = (1.0, 0.25, 0.04)
material.use_shadeless = True
cube.data.materials.append(material)
cube.game.physics_type = 'NO_COLLISION'

script = bpy.data.texts.new('web_controls.py')
script.write('''import Range
cont = Range.logic.getCurrentController()
obj = cont.owner
if not obj.get("web_started", False):
    obj["web_started"] = True
    print("[web-smoke] Python controller started", flush=True)
keys = Range.logic.keyboard.events
dx = int(keys[Range.events.RIGHTARROWKEY] in (1, 2)) - int(keys[Range.events.LEFTARROWKEY] in (1, 2))

# Joystick: same movement as the arrow keys, driven by the D-pad or the
# left stick X axis (axisValues is normalized to -1.0..1.0 in this engine;
# deadzone avoids drift from analog stick noise).
joy = Range.logic.joysticks[0]
JOY_AXIS_DEADZONE = 0.25
if joy:
    buttons = joy.activeButtons
    dpad_dx = int(14 in buttons) - int(13 in buttons)  # SDL DPAD_RIGHT/LEFT
    joy_x = joy.axisValues[0]
    analog_dx = int(joy_x > JOY_AXIS_DEADZONE) - int(joy_x < -JOY_AXIS_DEADZONE)
    joy_dx = dpad_dx if dpad_dx else analog_dx
    if joy_dx and not dx:
        dx = joy_dx
        if not obj.get("web_joy_axis_seen", False):
            obj["web_joy_axis_seen"] = True
            print("[web-smoke] joystick moved cube", flush=True)

if dx:
    obj.applyMovement((dx * 0.05, 0, 0), False)
    if not obj.get("web_key_seen", False):
        obj["web_key_seen"] = True
        print("[web-smoke] keyboard moved cube", flush=True)

mouse_click = Range.logic.mouse.events[Range.events.LEFTMOUSE] == 1
spin_dir = obj.get("spin_dir", 1)
if mouse_click:
    spin_dir = -spin_dir
    obj["spin_dir"] = spin_dir
    print("[web-smoke] mouse click flipped spin direction", flush=True)

# Joystick button 0: same effect as the mouse click, edge-triggered so
# holding the button down doesn't flip the spin every frame.
if joy:
    joy_button_down = 0 in joy.activeButtons
    joy_button_prev = obj.get("joy_button_prev", False)
    if joy_button_down and not joy_button_prev:
        spin_dir = -spin_dir
        obj["spin_dir"] = spin_dir
        print("[web-smoke] joystick button flipped spin direction", flush=True)
    obj["joy_button_prev"] = joy_button_down

obj.applyRotation((0, 0, 0.01 * spin_dir), True)

# 2D filter toggles. Each simple filter has 3 linked actuators (create/on/off,
# see tools/create_web_smoke_scene.py for why) and each built-in filter has a
# single "on" actuator (the engine's actuator switch only ever calls
# SetBuiltinFilterEnabled(mode, True), so built-ins cannot be disabled again
# through logic bricks -- this is a known limitation, not a bug in this script).
SIMPLE_FILTER_KEYS = [
    (Range.events.ONEKEY, 'BLUR'), (Range.events.TWOKEY, 'SHARPEN'),
    (Range.events.THREEKEY, 'DILATION'), (Range.events.FOURKEY, 'EROSION'),
    (Range.events.FIVEKEY, 'LAPLACIAN'), (Range.events.SIXKEY, 'SOBEL'),
    (Range.events.SEVENKEY, 'PREWITT'), (Range.events.EIGHTKEY, 'GRAYSCALE'),
    (Range.events.NINEKEY, 'SEPIA'), (Range.events.ZEROKEY, 'INVERT'),
    (Range.events.QKEY, 'OUTLINE'),
]
BUILTIN_FILTER_KEYS = [
    (Range.events.WKEY, 'SSAO'), (Range.events.EKEY, 'BLOOM'),
    (Range.events.RKEY, 'LIGHTSCATTER'), (Range.events.TKEY, 'SSR'),
]
def key_edge(key):
    # Rising edge tracked by hand instead of relying on the engine's
    # JUST_ACTIVATED (value 1) sample, which a synthetic/CDP keydown+keyup
    # pair can land between logic ticks and miss entirely; this only needs
    # any single tick to observe the key as down after a tick that didn't.
    down = keys[key] in (1, 2)
    prev_prop = 'kbprev_' + str(key)
    was_down = obj.get(prev_prop, False)
    obj[prev_prop] = down
    return down and not was_down

for key, mode in SIMPLE_FILTER_KEYS:
    if key_edge(key):
        on_prop = 'flt_on_' + mode
        created_prop = 'flt_created_' + mode
        is_on = obj.get(on_prop, False)
        if not is_on:
            if obj.get(created_prop, False):
                cont.activate(mode + '_ON')
            else:
                cont.activate(mode + '_CREATE')
                obj[created_prop] = True
            obj[on_prop] = True
            print('[web-smoke] filter ON:', mode, flush=True)
        else:
            cont.activate(mode + '_OFF')
            obj[on_prop] = False
            print('[web-smoke] filter OFF:', mode, flush=True)
for key, mode in BUILTIN_FILTER_KEYS:
    if key_edge(key):
        cont.activate(mode + '_ON')
        print('[web-smoke] built-in filter ON (cannot toggle off):', mode, flush=True)
''')
bpy.ops.logic.sensor_add(type='ALWAYS', object=cube.name)
sensor = cube.game.sensors[-1]
sensor.use_pulse_true_level = True
bpy.ops.logic.controller_add(type='PYTHON', object=cube.name)
controller = cube.game.controllers[-1]
controller.text = script
sensor.link(controller)

# Every native 2D filter newly covered by the Web m_webSingleColorOutput fix
# (2026-09-14), bound to keyboard keys (see the Python controller script
# above) instead of always-on, so each one can be visually inspected on its
# own in a real browser. Linking an actuator to a controller does NOT run it
# automatically (confirmed via SCA_PythonController::Update, which only fires
# actuators the script explicitly passes to cont.activate()) -- the earlier
# always-on version of this scene never actually activated any of them.
#
# Simple filters (SCA_2DFilterActuator's "default" switch case) are added via
# RAS_2DFilterManager::AddFilter(..., use_reserved=false), which stores them
# at filter_pass + reservedPassIndex (17), so any distinct filter_pass keeps
# them from colliding with each other or with the built-in reserved passes
# (0-17). Each gets 3 actuators: CREATE (mode=<filter>, adds it enabled),
# ON (mode=ENABLE) and OFF (mode=DISABLE), so the key handler can toggle it
# after the first activation.
simple_filter_modes = [
    'BLUR', 'SHARPEN', 'DILATION', 'EROSION', 'LAPLACIAN', 'SOBEL', 'PREWITT',
    'GRAYSCALE', 'SEPIA', 'INVERT', 'OUTLINE',
]
for filter_pass, mode in enumerate(simple_filter_modes):
    for suffix, act_mode in (('_CREATE', mode), ('_ON', 'ENABLE'), ('_OFF', 'DISABLE')):
        bpy.ops.logic.actuator_add(type='FILTER_2D', object=cube.name)
        act = cube.game.actuators[-1]
        act.name = mode + suffix
        act.mode = act_mode
        act.filter_pass = filter_pass
        controller.link(actuator=act)

# Built-in multi-pass filters (Bloom, SSAO, LightScatter, SSR) go through
# RAS_2DFilterManager::SetBuiltinFilterEnabled(), which the actuator only
# ever calls with enabled=True -- there is no logic-brick path to disable
# them again, so only an "ON" actuator is created for these.
builtin_filter_modes = ['SSAO', 'BLOOM', 'LIGHTSCATTER', 'SSR']
for mode in builtin_filter_modes:
    bpy.ops.logic.actuator_add(type='FILTER_2D', object=cube.name)
    act = cube.game.actuators[-1]
    act.name = mode + '_ON'
    act.mode = mode
    controller.link(actuator=act)

camera = bpy.data.objects.new('WebCamera', bpy.data.cameras.new('WebCamera'))
scene.objects.link(camera)
camera.location = (0, -8, 5)
camera.rotation_euler = (Vector((0, 0, 0)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
scene.camera = camera
scene.update()
output = Path(__file__).resolve().parents[1] / 'build-web' / 'bin' / 'web-smoke.range'
bpy.ops.wm.save_as_mainfile(filepath=str(output))
print('[web-smoke] saved', str(output))
