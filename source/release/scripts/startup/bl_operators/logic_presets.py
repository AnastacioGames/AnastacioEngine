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
from bpy.props import EnumProperty
from bpy.app.translations import pgettext_iface


class _Bricks:
    """Adds bricks to one object, all of them in the same group."""

    def __init__(self, ob, group):
        self.ob = ob
        self.game = ob.game
        self.group = group

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
    near = b.sensor('NEAR', "Player Near", property="player", distance=3.0)
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


class LOGIC_OT_preset_add(Operator):
    """Add a group of logic bricks already linked"""
    bl_idname = "logic.preset_add"
    bl_label = "Add Logic Preset"
    bl_options = {'REGISTER', 'UNDO'}

    type = EnumProperty(
        name="Preset",
        items=(
            ('WALK', "Walk (WASD)", "W and S move forward and back, A and D turn"),
            ('JUMP', "Jump", "Space jumps while a ray below touches the ground (needs Dynamic physics)"),
            ('CAMERA', "Follow Camera", "The scene camera follows the active object from behind"),
            ('COLLECT', "Collect Item", "The item disappears and sends the message \"collected\" "
                                         "when an object with the property \"player\" touches it"),
            ('DOOR', "Door with Key", "E near an object with the property \"player\" toggles the "
                                       "property \"open\", which plays the door Action (choose it) "
                                       "forward or back"),
            ('HEALTH', "Health and Damage", "Property \"health\" loses 10 when touching an object with "
                                             "the property \"damage\", the object ends at zero"),
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
        {
            'WALK': _walk,
            'JUMP': _jump,
            'COLLECT': _collect,
            'DOOR': _door,
            'HEALTH': _health,
        }[self.type](b)
        return {'FINISHED'}


classes = (
    LOGIC_OT_preset_add,
)
