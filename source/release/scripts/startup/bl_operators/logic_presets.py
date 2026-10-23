# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

# <pep8-80 compliant>

# Logic brick presets: each one adds a group of bricks already linked.

import bpy
from bpy.types import Operator
from bpy.props import BoolProperty, EnumProperty, StringProperty
from bpy.app.translations import pgettext_iface


class _Bricks:
    """Adds bricks to one object, all of them in the same group."""

    def __init__(self, ob, group):
        self.ob = ob
        self.game = ob.game
        self.group = group
        if group not in ob.game.brick_groups:
            ob.game.brick_groups.new(group)

    def _add(self, kind, typ, name):
        getattr(bpy.ops.logic, kind + "_add")(type=typ, name=name, object=self.ob.name)
        brick = getattr(self.game, kind + "s")[-1]
        brick.group = self.group
        return brick

    def sensor(self, typ, name, **props):
        s = self._add("sensor", typ, name)
        for k, v in props.items():
            setattr(s, k, v)
        return s

    def actuator(self, typ, name, **props):
        a = self._add("actuator", typ, name)
        for k, v in props.items():
            setattr(a, k, v)
        return a

    def link(self, sensors, actuators, name, typ='LOGIC_AND'):
        c = self._add("controller", typ, name)
        for s in sensors:
            c.link(sensor=s)
        for a in actuators:
            c.link(actuator=a)
        return c

    def key(self, key, name):
        return self.sensor('KEYBOARD', name, key=key)

    def property(self, name, typ, value):
        props = self.game.properties
        if name not in props:
            bpy.ops.object.game_property_new(type=typ, name=name)
            props[name].value = value

    def then(self, actuator, actuators, name, state=1):
        # what the "Then" button does: a Finished sensor for the actuator and a controller
        s = self.sensor('ACTUATOR', name, actuator=actuator.name, mode='FINISHED')
        c = self.link([s], actuators, name)
        c.states = state
        return c

    def state_name(self, state, name):
        self.game.state_names[state - 1].name = name


def _walk(b):
    for key, name, loc, rot in (
            ('W', "Forward", (0.0, 0.1, 0.0), (0.0, 0.0, 0.0)),
            ('S', "Back", (0.0, -0.1, 0.0), (0.0, 0.0, 0.0)),
            ('A', "Turn Left", (0.0, 0.0, 0.0), (0.0, 0.0, 0.05)),
            ('D', "Turn Right", (0.0, 0.0, 0.0), (0.0, 0.0, -0.05)),
    ):
        s = b.key(key, "Key " + key)
        a = b.actuator('MOTION', name, offset_location=loc, offset_rotation=rot,
                       use_local_location=True, use_local_rotation=True)
        b.link([s], [a], name)


def _jump(b):
    s = b.key('SPACE', "Key Space")
    ground = b.sensor('RAY', "On Ground", axis='NEGZAXIS', range=1.1)
    a = b.actuator('MOTION', "Jump", linear_velocity=(0.0, 0.0, 6.0))
    b.link([s, ground], [a], "Jump")


def _camera(b, target):
    s = b.sensor('ALWAYS', "Always")
    a = b.actuator('CAMERA', "Follow", object=target, height=3.0, min=5.0, max=8.0, axis='NEG_Y')
    b.link([s], [a], "Follow")


def _collect(b):
    s = b.sensor('COLLISION', "Touch Player", property="player")
    end = b.actuator('EDIT_OBJECT', "Remove", mode='ENDOBJECT')
    msg = b.actuator('MESSAGE', "Collected", subject="collected")
    b.link([s], [end, msg], "Collect")


def _door(b):
    b.property("open", 'BOOL', False)
    key = b.key('E', "Key E")
    near = b.sensor('NEAR', "Player Near", property="player", distance=3.0, reset_distance=4.0)
    toggle = b.actuator('PROPERTY', "Toggle Open", mode='TOGGLE', property="open")
    b.link([key, near], [toggle], "Use Door")
    is_open = b.sensor('PROPERTY', "Is Open", evaluation_type='PROPEQUAL', property="open", value="True")
    anim = b.actuator('ACTION', "Door Animation", play_mode='FLIPPER')
    b.link([is_open], [anim], "Animate Door")


def _health(b):
    b.property("health", 'INT', 100)
    hit = b.sensor('COLLISION', "Hit", property="damage")
    damage = b.actuator('PROPERTY', "Take Damage", mode='ADD', property="health", value="-10")
    b.link([hit], [damage], "Damage")
    dead = b.sensor('PROPERTY', "No Health", evaluation_type='PROPLESSTHAN', property="health", value="1")
    die = b.actuator('EDIT_OBJECT', "Die", mode='ENDOBJECT')
    b.link([dead], [die], "Die")


def _platform(b):
    # state 1 goes forth, state 2 comes back, each for 2 seconds
    b.state_name(1, "Going")
    b.state_name(2, "Returning")
    for state, name, step, other in ((1, "Forth", 0.03, 2), (2, "Back", -0.03, 1)):
        move = b.sensor('ALWAYS', "Every Frame " + name, use_pulse_true_level=True)
        motion = b.actuator('MOTION', "Move " + name, offset_location=(0.0, step, 0.0), use_local_location=True)
        b.link([move], [motion], "Move " + name).states = state
        start = b.sensor('ALWAYS', "Start " + name)
        wait = b.actuator('WAIT', "Wait " + name, duration=2.0)
        b.link([start], [wait], "Time " + name).states = state
        turn = b.actuator('STATE', "To " + ("Returning" if other == 2 else "Going"), operation='SET',
                          states=tuple(i == other - 1 for i in range(30)))
        b.then(wait, [turn], "Then " + name, state)


def _chase(b, target):
    near = b.sensor('NEAR', "Player Close", property="player", distance=10.0, reset_distance=12.0)
    seek = b.actuator('STEERING', "Chase", mode='SEEK', target=target, velocity=3.0, distance=1.0,
                      facing=True, facing_axis='Y', lock_z_velocity=True)
    b.link([near], [seek], "Chase Player")


_CHECKPOINT = """# Created by the "Checkpoint and Respawn" logic preset.
def start(cont):
    ob = cont.owner
    ob["respawn_at"] = ob.worldPosition.copy()


def save(cont):
    s = cont.sensors[0]
    if s.positive and s.hitObject is not None:
        cont.owner["respawn_at"] = s.hitObject.worldPosition.copy()


def respawn(cont):
    if not cont.sensors[0].positive:
        return
    ob = cont.owner
    ob.worldPosition = ob.get("respawn_at", ob.worldPosition)
    if ob.getPhysicsId():
        ob.worldLinearVelocity = (0.0, 0.0, 0.0)
"""


def _checkpoint(b):
    if "logic_checkpoint.py" not in bpy.data.texts:
        bpy.data.texts.new("logic_checkpoint.py").write(_CHECKPOINT)
    for name, sensor, func in (
            ("Remember Start", b.sensor('ALWAYS', "Game Start"), "start"),
            ("Save Checkpoint", b.sensor('COLLISION', "Touch Checkpoint", property="checkpoint"), "save"),
            ("Respawn", b.sensor('COLLISION', "Touch Danger", property="kill"), "respawn"),
    ):
        c = b.link([sensor], [], name, 'PYTHON')
        c.mode = 'MODULE'
        c.module = "logic_checkpoint." + func


def _button(b, scene):
    scene.game_settings.show_mouse = True
    over = b.sensor('MOUSE', "Mouse Over", mouse_event='MOUSEOVER')
    click = b.sensor('MOUSE', "Left Click", mouse_event='LEFTCLICK')
    go = b.actuator('SCENE', "Go To Scene", mode='SET')
    b.link([over, click], [go], "Click Button")


def _mouse_look(b):
    a = b.actuator('MOUSE', "Mouse Look", mode='LOOK')
    b.link([b.sensor('ALWAYS', "Always")], [a], "Mouse Look")


def _shoot(b, bullet):
    s = b.sensor('MOUSE', "Left Click", mouse_event='LEFTCLICK')
    a = b.actuator('EDIT_OBJECT', "Shoot", mode='ADDOBJECT', time=120, linear_velocity=(0.0, 20.0, 0.0),
                   use_local_linear_velocity=True)
    if bullet is not None:
        a.object = bullet
    b.link([s], [a], "Shoot")


def _spawn_timer(b, model):
    s = b.sensor('DELAY', "Every 2 Seconds", delay=120, use_repeat=True)
    a = b.actuator('EDIT_OBJECT', "Spawn", mode='ADDOBJECT')
    if model is not None:
        a.object = model
    b.link([s], [a], "Spawn")


def _turret(b):
    radar = b.sensor('RADAR', "Player in Sight", property="player", axis='YAXIS', angle=60.0,
                     distance=15.0)
    aim = b.actuator('EDIT_OBJECT', "Aim", mode='TRACKTO', track_axis='TRACKAXISY', up_axis='UPAXISZ',
                     use_3d_tracking=False)
    b.link([radar], [aim], "Aim at Player")
    return aim


def _pause(b, scene):
    key = b.key('P', "Key P")
    pause = b.actuator('SCENE', "Pause Scene", mode='SUSPEND', scene=scene)
    b.link([key], [pause], "Pause")


class LOGIC_OT_preset_add(Operator):
    """Add a group of logic bricks already linked"""
    bl_idname = "logic.preset_add"
    bl_label = "Add Logic Preset"
    bl_options = {'REGISTER', 'UNDO'}

    type = EnumProperty(
        name="Preset",
        items=(
            ('WALK', "Walk (WASD)", "W and S move forward and back, A and D turn", 'MAN_TRANS', 0),
            ('JUMP', "Jump", "Space jumps while a ray below touches the ground (needs Dynamic physics)", 'TRIA_UP', 1),
            ('CAMERA', "Follow Camera", "The scene camera follows the active object from behind", 'OUTLINER_OB_CAMERA', 2),
            ('COLLECT', "Collect Item", "The item disappears and sends the message \"collected\" "
                                         "when an object with the property \"player\" touches it", 'SOLO_ON', 3),
            ('DOOR', "Door with Key", "E near an object with the property \"player\" toggles the "
                                       "property \"open\", which plays the door Action (choose it) "
                                       "forward or back", 'KEY_HLT', 4),
            ('HEALTH', "Health and Damage", "Property \"health\" loses 10 when touching an object with "
                                             "the property \"damage\", the object ends at zero", 'GHOST_ENABLED', 5),
            ('CHASE', "Chase Enemy", "Follows the object with the property \"player\" when it comes "
                                     "closer than 10 units (Steering, Seek)", 'POSE_HLT', 6),
            ('CHECKPOINT', "Checkpoint and Respawn", "Touching an object with the property \"checkpoint\" "
                                                     "saves the place, touching one with \"kill\" "
                                                     "returns there (or to the start)", 'RECOVER_LAST', 7),
            ('BUTTON', "Menu Button", "Clicking the object opens a scene (choose it in Go To Scene), "
                                      "the mouse cursor is shown", 'RESTRICT_SELECT_OFF', 8),
            ('PLATFORM', "Moving Platform", "Goes forth for 2 seconds and comes back, with two states "
                                            "and the Wait actuator", 'LOOP_BACK', 9),
            ('MOUSE_LOOK', "Mouse Look", "The object turns with the mouse (Mouse actuator, Look)", 'RESTRICT_VIEW_OFF', 10),
            ('SHOOT', "Shoot", "Left click adds the object of Add Object in front, fast (choose the "
                               "bullet, it must be on a hidden layer)", 'FORCE_FORCE', 11),
            ('SPAWN_TIMER', "Spawn Every 2 Seconds", "Adds the object of Add Object every 2 seconds (choose "
                                                     "it, it must be on a hidden layer)", 'TIME', 12),
            ('TURRET', "Turret", "Turns to the object with the property \"player\" when it enters a "
                                 "60 degree radar of 15 units", 'LAMP_SPOT', 13),
            ('PAUSE', "Pause Key", "P suspends the scene (an overlay scene can resume it)", 'PAUSE', 14),
        ),
    )

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def execute(self, context):
        ob = context.active_object
        # the group takes the translated name, as the user sees it in the menu
        label = pgettext_iface(self.rna_type.properties["type"].enum_items[self.type].name)

        if self.type == 'CAMERA':
            cam = context.scene.camera
            if cam is None or cam == ob:
                self.report({'ERROR'}, pgettext_iface("Select the object the scene camera should follow"))
                return {'CANCELLED'}
            _camera(_Bricks(cam, label), ob)
            self.report({'INFO'}, pgettext_iface("Bricks added to the camera \"%s\"") % cam.name)
            return {'FINISHED'}

        b = _Bricks(ob, label)
        if self.type == 'CHASE':
            target = next((o for o in context.scene.objects if o != ob and "player" in o.game.properties),
                          None)
            if target is None:
                self.report({'ERROR'}, pgettext_iface("No object has the property \"player\" to chase"))
                return {'CANCELLED'}
            _chase(b, target)
            return {'FINISHED'}
        if self.type == 'BUTTON':
            _button(b, context.scene)
            return {'FINISHED'}
        if self.type in ('SHOOT', 'SPAWN_TIMER'):
            # the other selected mesh becomes the object to add
            other = next((o for o in context.selected_objects if o != ob and o.type == 'MESH'), None)
            (_shoot if self.type == 'SHOOT' else _spawn_timer)(b, other)
            return {'FINISHED'}
        if self.type == 'PAUSE':
            _pause(b, context.scene)
            return {'FINISHED'}
        if self.type == 'TURRET':
            aim = _turret(b)
            target = next((o for o in context.scene.objects if o != ob and "player" in o.game.properties),
                          None)
            if target is not None:
                aim.track_object = target
            return {'FINISHED'}
        {
            'WALK': _walk,
            'JUMP': _jump,
            'COLLECT': _collect,
            'DOOR': _door,
            'HEALTH': _health,
            'CHECKPOINT': _checkpoint,
            'PLATFORM': _platform,
            'MOUSE_LOOK': _mouse_look,
        }[self.type](b)
        return {'FINISHED'}


class LOGIC_OT_brick_inspector_show(Operator):
    """Open this brick in the Logic Editor and close the others of the object"""
    bl_idname = "logic.brick_inspector_show"
    bl_label = "Show Brick"
    bl_options = {'REGISTER', 'UNDO'}

    kind = StringProperty(options={'HIDDEN'})
    name = StringProperty(options={'HIDDEN'})

    def execute(self, context):
        ob = context.active_object
        if ob is None:
            return {'CANCELLED'}
        game = ob.game
        for bricks in (game.sensors, game.controllers, game.actuators):
            for b in bricks:
                b.show_expanded = False
        target = getattr(game, self.kind + "s", {}).get(self.name)
        if target is None:
            return {'CANCELLED'}
        target.show_expanded = True
        if self.kind == "sensor":
            for c in target.controllers:
                c.show_expanded = True
        for area in context.screen.areas:
            if area.type == 'LOGIC_EDITOR':
                area.tag_redraw()
        return {'FINISHED'}


class LOGIC_OT_brick_inspector_object(Operator):
    """Make this object the active one to see its bricks"""
    bl_idname = "logic.brick_inspector_object"
    bl_label = "Show Object"
    bl_options = {'REGISTER', 'UNDO'}

    name = StringProperty(options={'HIDDEN'})

    def execute(self, context):
        ob = context.scene.objects.get(self.name)
        if ob is None:
            return {'CANCELLED'}
        for o in context.selected_objects:
            o.select = False
        ob.select = True
        context.scene.objects.active = ob
        return {'FINISHED'}


def _brick(context):
    for name in ("sensor", "controller", "actuator"):
        brick = getattr(context, name, None)
        if brick is not None:
            return brick
    return None


class LOGIC_OT_brick_group_new(Operator):
    """Put the brick in a new group (a typed name that is not in the list is added to it)"""
    bl_idname = "logic.brick_group_new"
    bl_label = "New Brick Group"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        brick = _brick(context)
        if brick is None:
            return {'CANCELLED'}
        groups = brick.id_data.game.brick_groups
        if brick.group and brick.group not in groups:
            groups.new(brick.group)
        else:
            brick.group = groups.new(pgettext_iface("Group")).name
        return {'FINISHED'}


class LOGIC_OT_brick_group_clear(Operator):
    """Take the brick out of its group"""
    bl_idname = "logic.brick_group_clear"
    bl_label = "Remove From Group"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        brick = _brick(context)
        if brick is None:
            return {'CANCELLED'}
        brick.group = ""
        return {'FINISHED'}


def _used_groups(ob):
    g = ob.game
    names = []
    for brick in list(g.sensors) + list(g.controllers) + list(g.actuators):
        if brick.group and brick.group not in names:
            names.append(brick.group)
    return names


class LOGIC_OT_brick_group_add(Operator):
    """Add a brick group to the list of the active object"""
    bl_idname = "logic.brick_group_add"
    bl_label = "Add Brick Group"
    bl_options = {'REGISTER', 'UNDO'}

    collect = bpy.props.BoolProperty(
        name="From Bricks",
        description="Add the groups that bricks already use and the list does not have",
    )

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def execute(self, context):
        game = context.active_object.game
        if self.collect:
            for name in _used_groups(context.active_object):
                if name not in game.brick_groups:
                    game.brick_groups.new(name)
        else:
            game.brick_groups.new(pgettext_iface("Group"))
            game.active_brick_group_index = len(game.brick_groups) - 1
        return {'FINISHED'}


class LOGIC_OT_brick_group_remove(Operator):
    """Remove the selected brick group; its bricks stay, without a group"""
    bl_idname = "logic.brick_group_remove"
    bl_label = "Remove Brick Group"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob is not None and 0 <= ob.game.active_brick_group_index < len(ob.game.brick_groups)

    def execute(self, context):
        game = context.active_object.game
        game.brick_groups.remove(game.brick_groups[game.active_brick_group_index])
        game.active_brick_group_index = max(0, min(game.active_brick_group_index, len(game.brick_groups) - 1))
        return {'FINISHED'}


classes = (
    LOGIC_OT_preset_add,
    LOGIC_OT_brick_group_new,
    LOGIC_OT_brick_group_clear,
    LOGIC_OT_brick_group_add,
    LOGIC_OT_brick_group_remove,
    LOGIC_OT_brick_inspector_show,
    LOGIC_OT_brick_inspector_object,
)

bpy.types.WindowManager.brick_inspector_show_info = BoolProperty(
    name="Show Tips",
    description="Also list tips, such as bricks that are not linked",
    default=True,
)
