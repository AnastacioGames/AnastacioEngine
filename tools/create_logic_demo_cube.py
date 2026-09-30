"""Cube with every kind of Logic Brick, to try the "Convert to Python" button by hand.

Run with:  RangeEngine -b --python tools/create_logic_demo_cube.py -- <output.range> [convert]
In game (debug properties on screen):
  arrows move (limited to a square), V hides/shows, left click counts,
  T follows the sphere (Steering), Y goes back to manual control.
"""
import bpy
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = argv[0] if argv else "logic_demo_cube.range"
convert = len(argv) > 1 and argv[1] == "convert"

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.obstacle_simulation = 'NONE'
scene.game_settings.show_debug_properties = True


def material(name, color):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = color
    return mat


bpy.ops.mesh.primitive_cube_add(location=(0, 0, -1))
floor = bpy.context.object
floor.name = "Chao"
floor.scale = (8, 8, 1)
floor.game.physics_type = 'STATIC'
floor.data.materials.append(material("ChaoMat", (0.3, 0.3, 0.3)))

bpy.ops.mesh.primitive_uv_sphere_add(location=(4, 4, 0.5), size=0.5)
target = bpy.context.object
target.name = "Alvo"
target.game.physics_type = 'NO_COLLISION'
target.data.materials.append(material("AlvoMat", (0.1, 0.8, 1.0)))
bpy.ops.object.game_property_new(type='BOOL', name="alvo")

bpy.ops.object.lamp_add(type='SUN', location=(0, 0, 10))
bpy.ops.object.camera_add(location=(0, -14, 12), rotation=(0.85, 0, 0))
scene.camera = bpy.context.object

bpy.ops.mesh.primitive_cube_add(location=(0, 0, 1.5), radius=0.5)
cube = bpy.context.object
cube.name = "Cubo"
cube.game.physics_type = 'NO_COLLISION'
cube.data.materials.append(material("CuboMat", (1.0, 0.5, 0.1)))
for name, type_ in (("cliques", 'INT'), ("ticks", 'INT'), ("sorte", 'INT'), ("perto", 'BOOL'),
                    ("oculto", 'BOOL'), ("andando", 'INT'), ("seguindo", 'INT'), ("eventos", 'INT')):
    bpy.ops.object.game_property_new(type=type_, name=name)
    cube.game.properties[name].show_debug = True

count = [0]


def add(kind, type_, **kw):
    count[0] += 1
    name = "%s%d" % (type_.title()[:6], count[0])
    getattr(bpy.ops.logic, kind + "_add")(type=type_, name=name, object=cube.name)
    brick = getattr(cube.game, kind + "s")[name]
    for key, value in kw.items():
        setattr(brick, key, value)
    return brick


def wire(sensors, actuators, kind='LOGIC_AND', state=1, **kw):
    cont = add("controller", kind, **kw)
    cont.states = state
    for s in sensors if isinstance(sensors, (list, tuple)) else [sensors]:
        s.link(cont)
    for a in actuators if isinstance(actuators, (list, tuple)) else [actuators]:
        cont.link(actuator=a)
    return cont


def key(k, **kw):
    return add("sensor", 'KEYBOARD', key=k, **kw)


def prop_add(name, value="1"):
    return add("actuator", 'PROPERTY', mode='ADD', property=name, value=value)


def to_state(n):
    act = add("actuator", 'STATE', operation='SET')
    act.states[n - 1] = True
    return act


# --- State 1: manual control ---
move = None
for k, off in (('UP_ARROW', (0, 0.1, 0)), ('DOWN_ARROW', (0, -0.1, 0)),
               ('LEFT_ARROW', (-0.1, 0, 0)), ('RIGHT_ARROW', (0.1, 0, 0))):
    act = add("actuator", 'MOTION', offset_location=off)
    move = move or act
    wire(key(k), act)
# Actuator sensor: counts the frames the "up" motion is active.
wire(add("sensor", 'ACTUATOR', actuator=move.name, use_pulse_true_level=True), prop_add("andando"))

always = add("sensor", 'ALWAYS')
wire(always, [add("actuator", 'CONSTRAINT', mode='LOC', limit='LOCX', limit_min=-6, limit_max=6),
              add("actuator", 'CONSTRAINT', mode='LOC', limit='LOCY', limit_min=-6, limit_max=6),
              add("actuator", 'CONSTRAINT', mode='DIST', direction='DIRNZ', range=10, distance=1.5,
                  use_force_distance=True),
              add("actuator", 'CONSTRAINT', mode='ORI', direction_axis_pos='DIRPZ',
                  rotation_max=(0, 0, 1), angle_min=0, angle_max=0)])

# V toggles "oculto"; property sensors drive visibility (one via Expression controller).
wire(key('V'), add("actuator", 'PROPERTY', mode='TOGGLE', property="oculto"))
hidden = add("sensor", 'PROPERTY', evaluation_type='PROPEQUAL', property="oculto", value="True")
wire(hidden, add("actuator", 'VISIBILITY', use_visible=False))
wire(hidden, add("actuator", 'VISIBILITY', use_visible=True), kind='LOGIC_NAND')

wire(add("sensor", 'MOUSE', mouse_event='LEFTCLICK'), prop_add("cliques"))

# Delay -> message "tick" -> message sensor counts it.
wire(add("sensor", 'DELAY', delay=60, use_repeat=True), add("actuator", 'MESSAGE', subject="tick"))
wire(add("sensor", 'MESSAGE', subject="tick"), prop_add("ticks"))

wire(add("sensor", 'RANDOM', seed=7), prop_add("sorte"), kind='LOGIC_OR')

near = add("sensor", 'NEAR', property="alvo", distance=2.5, reset_distance=3)
wire(near, add("actuator", 'PROPERTY', mode='ASSIGN', property="perto", value="True"))
wire(near, add("actuator", 'PROPERTY', mode='ASSIGN', property="perto", value="False"), kind='LOGIC_NOR')

# Animation Event: scale pulse action with a trigger at frame 10.
cube.keyframe_insert("scale", frame=1)
cube.scale = (1.3, 1.3, 1.3)
cube.keyframe_insert("scale", frame=10)
cube.scale = (1, 1, 1)
cube.keyframe_insert("scale", frame=20)
action = cube.animation_data.action
cube.animation_data_clear()
scene.objects.active = cube
bpy.ops.object.animation_event_add()
event = cube.anim_events[len(cube.anim_events) - 1]
event.anim = action
scene.frame_current = 10
bpy.ops.object.animation_event_trigger_add(index=len(cube.anim_events) - 1)
scene.frame_current = 1
wire(always, add("actuator", 'ACTION', action=action, play_mode='LOOPEND', frame_start=1, frame_end=20))
wire(add("sensor", 'ANIMATIONEVENT', event_index=1, trigger_index=1), prop_add("eventos"))

wire(key('T'), to_state(2))

# --- State 2: follows the sphere ---
steer = add("actuator", 'STEERING', mode='SEEK', target=target, velocity=3, distance=1.5,
            facing=True, facing_axis='Y')
wire(add("sensor", 'ALWAYS'), steer, state=2)
following = add("sensor", 'ACTUATOR', actuator=steer.name, use_pulse_true_level=True)
wire(following, prop_add("seguindo"), kind='EXPRESSION', state=2, expression=following.name)
wire(key('Y'), to_state(1), state=2)

if convert:
    scene.objects.active = cube
    print("CONVERT", bpy.ops.logic.convert_to_component())
    text = bpy.data.texts["cubo_logic.py"].as_string()
    compile(text, "cubo", "exec")
    for line in text.splitlines():
        if "TODO" in line:
            print("  ", line.strip())

bpy.ops.wm.save_as_mainfile(filepath=bpy.path.abspath(output))
print("SAVED", output)
