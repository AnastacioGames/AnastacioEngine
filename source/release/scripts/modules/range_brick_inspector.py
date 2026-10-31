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

# Smart Bricks: editor-only checks and viewport drawing for the native logic
# bricks. Nothing here runs in the game.
#
#   problems(ob)            -> [Problem]   what looks wrong in the bricks of ob
#   draw(ob, g, selected)                  viewport drawing (g is the Gizmo of
#                                          range_component_editor)
#
# Each brick type registers a check and/or a gizmo with @check / @gizmo.

import bpy

ERROR, WARNING, INFO = 'ERROR', 'WARNING', 'INFO'


class Problem:
    __slots__ = ("kind", "brick", "level", "text")

    def __init__(self, kind, brick, level, text):
        self.kind = kind        # "sensor", "controller" or "actuator"
        self.brick = brick
        self.level = level
        self.text = text

    @property
    def icon(self):
        return {ERROR: 'ERROR', WARNING: 'ERROR', INFO: 'INFO'}[self.level]


_checks = {}    # (kind, type) -> [func(ctx, brick) -> [(level, text)]]
_gizmos = {}    # (kind, type) -> [func(ob, brick, g)]


def check(kind, *types):
    def deco(func):
        for t in types:
            _checks.setdefault((kind, t), []).append(func)
        return func
    return deco


def gizmo(kind, *types):
    def deco(func):
        for t in types:
            _gizmos.setdefault((kind, t), []).append(func)
        return func
    return deco


class _Ctx:
    """What the checks need about the whole file, computed once per call."""

    def __init__(self, ob):
        self.ob = ob
        scene = bpy.context.scene
        self.scene = scene
        objs = list(scene.objects) if scene else list(bpy.data.objects)
        self.objects = objs
        self._props = None
        self._subjects = None

    def objects_with(self, prop):
        if self._props is None:
            self._props = {}
            for o in self.objects:
                for p in o.game.properties:
                    self._props.setdefault(p.name, []).append(o)
        return self._props.get(prop, [])

    def subjects(self):
        """(sent, listened) message subjects in the scene."""
        if self._subjects is None:
            sent, heard = set(), set()
            for o in self.objects:
                for a in o.game.actuators:
                    if a.type == 'MESSAGE':
                        sent.add(a.subject)
                for s in o.game.sensors:
                    if s.type == 'MESSAGE':
                        heard.add(s.subject)
            self._subjects = (sent, heard)
        return self._subjects

    def linked_actuators(self):
        names = set()
        for o in self.objects:
            for c in o.game.controllers:
                for a in c.actuators:
                    if a is not None:  # old files may keep a dead link
                        names.add(a.as_pointer())
        return names

    def linked_controllers(self):
        ptrs = set()
        for o in self.objects:
            for s in o.game.sensors:
                for c in s.controllers:
                    if c is not None:
                        ptrs.add(c.as_pointer())
        return ptrs


def _visible(ob, other):
    """True when other is on a layer the scene shows (Add Object needs it hidden)."""
    scene = bpy.context.scene
    return any(a and b for a, b in zip(scene.layers, other.layers))


_MOVING = {'DYNAMIC', 'RIGID_BODY', 'CHARACTER', 'SOFT_BODY'}


# ---------------------------------------------------------------- sensors

def _detect_property(ctx, prop, what):
    if not prop:
        return []
    found = [o for o in ctx.objects_with(prop) if o != ctx.ob]
    if not found:
        return [(WARNING, "No object in the scene has the property \"%s\" to %s" % (prop, what))]
    return []


@check("sensor", 'NEAR')
def _near(ctx, s):
    out = _detect_property(ctx, s.property, "detect")
    if s.distance <= 0:
        out.append((ERROR, "Distance is 0, it never detects"))
    elif s.reset_distance < s.distance:
        out.append((WARNING, "Reset distance is smaller than Distance"))
    if ctx.ob.game.physics_type == 'NO_COLLISION':
        out.append((ERROR, "Near needs collision: the object is \"No Collision\""))
    return out


@check("sensor", 'RADAR')
def _radar(ctx, s):
    out = _detect_property(ctx, s.property, "detect")
    if s.distance <= 0:
        out.append((ERROR, "Distance is 0, it never detects"))
    if ctx.ob.game.physics_type == 'NO_COLLISION':
        out.append((ERROR, "Radar needs collision: the object is \"No Collision\""))
    return out


@check("sensor", 'RAY')
def _ray(ctx, s):
    out = []
    if s.ray_type == 'PROPERTY':
        out += _detect_property(ctx, s.property, "hit")
    if s.range <= 0:
        out.append((ERROR, "Range is 0, the ray hits nothing"))
    return out


@check("sensor", 'COLLISION')
def _collision(ctx, s):
    out = [] if s.use_material else _detect_property(ctx, s.property, "touch")
    if ctx.ob.game.physics_type == 'NO_COLLISION':
        out.append((ERROR, "The object is \"No Collision\", it never touches anything"))
    return out


@check("sensor", 'PROPERTY')
def _property_sensor(ctx, s):
    if s.use_runtime_property:
        return []
    if not s.property:
        return [(ERROR, "No property chosen")]
    if s.property not in ctx.ob.game.properties:
        return [(ERROR, "The object has no property \"%s\"" % s.property)]
    return []


@check("sensor", 'MESSAGE')
def _message_sensor(ctx, s):
    if not s.subject:
        return [(INFO, "No subject: reacts to every message")]
    sent, _ = ctx.subjects()
    if s.subject not in sent:
        return [(WARNING, "No Message actuator sends \"%s\"" % s.subject)]
    return []


@check("sensor", 'ACTUATOR')
def _actuator_sensor(ctx, s):
    if not s.actuator:
        return [(ERROR, "No actuator chosen")]
    if s.actuator not in ctx.ob.game.actuators:
        return [(ERROR, "The object has no actuator \"%s\"" % s.actuator)]
    return []


@check("sensor", 'KEYBOARD')
def _keyboard(ctx, s):
    if s.key == 'NONE' and not s.use_all_keys:
        return [(ERROR, "No key chosen")]
    return []


@check("sensor", 'MOUSE')
def _mouse(ctx, s):
    if s.mouse_event in ('MOUSEOVER', 'MOUSEOVERANY') and \
            not ctx.scene.game_settings.show_mouse:
        return [(INFO, "Mouse cursor is hidden (Render > Game > Mouse Cursor)")]
    return []


# ------------------------------------------------------------ controllers

def _module_found(module):
    name = module.rsplit(".", 1)[0]
    if name + ".py" in bpy.data.texts or name in bpy.data.texts:
        return True
    if not bpy.data.filepath:
        return True     # can't look for files next to an unsaved file
    import os
    base = os.path.dirname(bpy.path.abspath("//"))
    parts = name.split(".")
    for root in (base, os.path.join(base, "scripts")):
        p = os.path.join(root, *parts)
        if os.path.isfile(p + ".py") or os.path.isfile(os.path.join(p, "__init__.py")):
            return True
    return False


@check("controller", 'PYTHON')
def _python(ctx, c):
    if c.mode == 'SCRIPT':
        return [] if c.text else [(ERROR, "No script chosen")]
    if not c.module:
        return [(ERROR, "No module chosen (write file.function)")]
    if "." not in c.module:
        return [(ERROR, "Module needs a function: \"%s.function\"" % c.module)]
    if not _module_found(c.module):
        return [(WARNING, "Module \"%s\" not found in the texts or next to the file"
                 % c.module.rsplit(".", 1)[0])]
    return []


@check("controller", 'EXPRESSION')
def _expression(ctx, c):
    return [] if c.expression.strip() else [(ERROR, "Empty expression")]


# -------------------------------------------------------------- actuators

def _need(value, text):
    return [] if value is not None else [(ERROR, text)]


@check("actuator", 'STEERING')
def _steering(ctx, a):
    out = _need(a.target, "Steering without a target")
    if a.target == ctx.ob:
        out.append((ERROR, "Steering targets the object itself"))
    if a.mode == 'PATHFOLLOWING' and a.navmesh is None:
        out.append((ERROR, "Path following needs a Navigation Mesh"))
    if a.velocity <= 0:
        out.append((WARNING, "Velocity is 0, it doesn't move"))
    return out


@check("actuator", 'EDIT_OBJECT')
def _edit_object(ctx, a):
    if a.mode == 'ADDOBJECT':
        if a.use_object_from_property:
            return []
        if a.object is None:
            return [(ERROR, "Add Object without an object")]
        if _visible(ctx.ob, a.object):
            return [(ERROR, "\"%s\" is on a visible layer: Add Object needs it on a hidden one"
                     % a.object.name)]
    elif a.mode == 'TRACKTO':
        out = _need(a.track_object, "Track To without a target")
        if a.track_object == ctx.ob:
            out.append((ERROR, "Track To targets the object itself"))
        return out
    elif a.mode == 'REPLACEMESH':
        return _need(a.mesh, "Replace Mesh without a mesh")
    return []


@check("actuator", 'CAMERA')
def _camera(ctx, a):
    out = _need(a.object, "Camera actuator without an object to follow")
    if a.min > a.max:
        out.append((WARNING, "Min is bigger than Max"))
    return out


@check("actuator", 'ACTION')
def _action(ctx, a):
    return _need(a.action, "No Action chosen")


@check("actuator", 'SOUND')
def _sound(ctx, a):
    return _need(a.sound, "No sound chosen")


@check("actuator", 'SCENE')
def _scene(ctx, a):
    if a.mode == 'CAMERA':
        return _need(a.camera, "Set Camera without a camera")
    if a.mode != 'RESTART':
        return _need(a.scene, "No scene chosen")
    return []


@check("actuator", 'PARENT')
def _parent(ctx, a):
    if a.mode == 'SETPARENT':
        return _need(a.object, "Set Parent without a parent")
    return []


@check("actuator", 'PROPERTY')
def _property_actuator(ctx, a):
    if a.actuator_mode != 'NONE':
        return []
    if not a.property:
        return [(ERROR, "No property chosen")]
    if a.property not in ctx.ob.game.properties:
        return [(ERROR, "The object has no property \"%s\"" % a.property)]
    if a.mode == 'COPY' and a.object is None:
        return [(ERROR, "Copy without an object to copy from")]
    return []


@check("actuator", 'MESSAGE')
def _message_actuator(ctx, a):
    if not a.subject:
        return [(WARNING, "Message without a subject")]
    _, heard = ctx.subjects()
    if a.subject not in heard and "" not in heard:
        return [(INFO, "No Message sensor listens to \"%s\"" % a.subject)]
    return []


@check("actuator", 'MOTION')
def _motion(ctx, a):
    if a.mode != 'OBJECT_NORMAL':
        return []
    moves = any(any(v) for v in (a.offset_location, a.offset_rotation))
    physics = any(any(v) for v in (a.force, a.torque, a.linear_velocity, a.angular_velocity))
    if not moves and not physics:
        return [(INFO, "All values are 0, it does nothing")]
    if physics and ctx.ob.game.physics_type not in _MOVING:
        return [(WARNING, "Force and velocity need Dynamic or Rigid Body physics")]
    return []


@check("actuator", 'STATE')
def _state(ctx, a):
    return [] if any(a.states) else [(WARNING, "No state chosen")]


# ------------------------------------------------------------------ public

def problems(ob):
    """[Problem] for every brick of ob, in the order of the Logic Editor."""
    ctx = _Ctx(ob)
    game = ob.game
    out = []
    linked_c = ctx.linked_controllers()
    linked_a = ctx.linked_actuators()
    for kind, bricks in (("sensor", game.sensors), ("controller", game.controllers),
                         ("actuator", game.actuators)):
        for b in bricks:
            if not b.active:
                continue
            for func in _checks.get((kind, b.type), ()):
                try:
                    for level, text in func(ctx, b):
                        out.append(Problem(kind, b, level, text))
                except Exception as e:
                    out.append(Problem(kind, b, INFO, "Check failed: %s" % e))
            if kind == "sensor" and not len(b.controllers):
                out.append(Problem(kind, b, INFO, "Not linked to a controller"))
            elif kind == "controller" and b.as_pointer() not in linked_c:
                out.append(Problem(kind, b, INFO, "No sensor linked, it never runs"))
            elif kind == "controller" and b.type != 'PYTHON' and not len(b.actuators):
                out.append(Problem(kind, b, INFO, "No actuator linked"))
            elif kind == "actuator" and b.as_pointer() not in linked_a:
                out.append(Problem(kind, b, INFO, "Not linked to a controller"))
    return out


def count(ob):
    """(errors and warnings, infos) of ob."""
    bad = info = 0
    for p in problems(ob):
        if p.level == INFO:
            info += 1
        else:
            bad += 1
    return bad, info


# ---------------------------------------------------------------- drawing

_AXES = {
    'XAXIS': (1, 0, 0), 'YAXIS': (0, 1, 0), 'ZAXIS': (0, 0, 1),
    'NEGXAXIS': (-1, 0, 0), 'NEGYAXIS': (0, -1, 0), 'NEGZAXIS': (0, 0, -1),
}


def _axis(ob, name):
    from mathutils import Vector
    v = ob.matrix_world.to_3x3() * Vector(_AXES.get(name, (0, 1, 0)))
    return v.normalized()


def _pos(ob):
    return ob.matrix_world.translation


@gizmo("sensor", 'NEAR')
def _g_near(ob, s, g):
    g.sphere(_pos(ob), s.distance, "GREEN")
    if s.reset_distance > s.distance:
        g.circle(_pos(ob), s.reset_distance, (0.3, 0.8, 0.3, 0.4))
    g.text(_pos(ob) + _axis(ob, 'ZAXIS') * s.distance, s.name, "GREEN")


@gizmo("sensor", 'RADAR')
def _g_radar(ob, s, g):
    import math
    d = _axis(ob, s.axis)
    p = _pos(ob)
    half = math.radians(s.angle) * 0.5
    end = p + d * s.distance * math.cos(half)
    r = s.distance * math.sin(half)
    g.circle(end, r, "GREEN", axis=d, segments=24)
    side = d.orthogonal().normalized()
    up = d.cross(side)
    for v in (side, -side, up, -up):
        g.line(p, end + v * r, "GREEN")
    g.text(end, s.name, "GREEN")


@gizmo("sensor", 'RAY')
def _g_ray(ob, s, g):
    p = _pos(ob)
    end = p + _axis(ob, s.axis) * s.range
    g.line(p, end, "RED", width=2)
    g.text(end, s.name, "RED")


@gizmo("actuator", 'STEERING')
def _g_steering(ob, a, g):
    if a.target is not None:
        t = _pos(a.target)
        g.arrow(_pos(ob), t, "YELLOW", width=2)
        if a.distance > 0:
            g.circle(t, a.distance, "YELLOW")
        g.text(t, a.name, "YELLOW")


@gizmo("actuator", 'EDIT_OBJECT')
def _g_edit(ob, a, g):
    if a.mode == 'TRACKTO' and a.track_object is not None:
        t = _pos(a.track_object)
        g.arrow(_pos(ob), t, "MAGENTA", width=2)
        g.text(t, a.name, "MAGENTA")


@gizmo("actuator", 'CAMERA')
def _g_camera(ob, a, g):
    if a.object is not None:
        t = _pos(a.object)
        g.arrow(_pos(ob), t, "CYAN", width=2)
        g.circle(t, a.min, "CYAN")
        g.circle(t, a.max, (0.3, 0.8, 0.9, 0.4))
        g.text(t, a.name, "CYAN")


@gizmo("actuator", 'PARENT')
def _g_parent(ob, a, g):
    if a.mode == 'SETPARENT' and a.object is not None:
        g.line(_pos(ob), _pos(a.object), "ORANGE")


def has_bricks(ob):
    game = ob.game
    return bool(len(game.sensors) or len(game.actuators))


def draw(ob, g, selected):
    """Viewport drawing of the bricks of ob (only when selected)."""
    if not selected:
        return
    game = ob.game
    for kind, bricks in (("sensor", game.sensors), ("actuator", game.actuators)):
        for b in bricks:
            if not b.active:
                continue
            for func in _gizmos.get((kind, b.type), ()):
                func(ob, b, g)
