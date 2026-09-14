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
''')
bpy.ops.logic.sensor_add(type='ALWAYS', object=cube.name)
sensor = cube.game.sensors[-1]
sensor.use_pulse_true_level = True
bpy.ops.logic.controller_add(type='PYTHON', object=cube.name)
controller = cube.game.controllers[-1]
controller.text = script
sensor.link(controller)

camera = bpy.data.objects.new('WebCamera', bpy.data.cameras.new('WebCamera'))
scene.objects.link(camera)
camera.location = (0, -8, 5)
camera.rotation_euler = (Vector((0, 0, 0)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
scene.camera = camera
scene.update()
output = Path(__file__).resolve().parents[1] / 'build-web' / 'bin' / 'web-smoke.range'
bpy.ops.wm.save_as_mainfile(filepath=str(output))
print('[web-smoke] saved', str(output))
