# Range.args: friendlier fields for Python Component "args".
#
#     from Range.args import Float, Int, Bool, Text, Choice, Object, Scene, Color, Header
#
#     class Patrol(types.KX_PythonComponent):
#         args = OrderedDict([
#             Header("Movement", icon="AUTO"),
#             ("Speed",  Float(2.0, min=0, max=20, tip="Meters per second")),
#             ("Target", Object(tip="Object it chases")),
#             ("Mode",   Choice("Walk", "Walk", "Run")),
#         ])
#
# Each helper is a plain int/float/str subclass, so the game code sees the same
# values as before (args["Speed"] is a float). The editor reads "_range_meta"
# (blenkernel/intern/python_component.c) to draw sliders, tooltips, ordered
# lists and object pickers. Object arrives in start(args) as KX_GameObject or None.
#
# Options any field takes (editor only, the game ignores them):
#     show_if="Jump"            show the field only while the Bool "Jump" is on
#     show_if=("Mode", "Run")   ... only while the field "Mode" is "Run"
#     required=True             warning while it is empty (Object, Scene, Text...)
#
# Pure Python and no bpy: this module also runs inside exported games.

__all__ = ("Float", "Int", "Bool", "Text", "Choice", "Object", "Scene", "Color", "Header",
           "ObjectList", "Point", "objects", "LIST_SEP")

LIST_SEP = ";"


def _meta(value, kind, tip, show_if=None, required=False, **extra):
    if isinstance(show_if, list):
        show_if = tuple(show_if)
    value._range_meta = dict(kind=kind, tip=str(tip or ""), show_if=show_if,
                             required=bool(required), **extra)
    return value


def _num(v):
    return None if v is None else float(v)


class Float(float):
    """Float field. min and max together draw a slider; tip is the tooltip."""
    def __new__(cls, value=0.0, min=None, max=None, tip="", circle=False, warn_above=None, **opts):
        """circle=True: circle with this radius around the object in the viewport.
        warn_above: warning when the value is bigger."""
        return _meta(float.__new__(cls, value), "float", tip, min=_num(min), max=_num(max),
                     circle=bool(circle), warn_above=_num(warn_above), **opts)


class Int(int):
    """Integer field. min and max together draw a slider; tip is the tooltip."""
    def __new__(cls, value=0, min=None, max=None, tip="", warn_above=None, **opts):
        return _meta(int.__new__(cls, value), "int", tip, min=_num(min), max=_num(max),
                     warn_above=_num(warn_above), **opts)


class Bool(int):
    """Checkbox with a tooltip (bool itself can't be subclassed)."""
    def __new__(cls, value=False, tip="", **opts):
        return _meta(int.__new__(cls, bool(value)), "bool", tip, **opts)

    def __bool__(self):
        return int(self) != 0

    def __repr__(self):
        return "Bool(%r)" % bool(self)


class Text(str):
    """Text field with a tooltip."""
    def __new__(cls, value="", tip="", **opts):
        return _meta(str.__new__(cls, value), "text", tip, **opts)


class Choice(str):
    """List of options in this order. Choice(default, item1, item2, ...).

    Without items the default is the only option; if the default isn't among
    the items, the first item is used."""
    def __new__(cls, default, *items, tip="", **opts):
        items = tuple(str(i) for i in items) or (str(default),)
        return _meta(str.__new__(cls, default), "choice", tip, items=items, **opts)


class Object(str):
    """Pick another object of the scene with the mouse.

    In the game, args[name] is the KX_GameObject with that name, or None when
    nothing was picked or the object isn't in the scene. Objects in a hidden
    layer also arrive as None: for spawn models use ObjectList + objects().

    filter: only this type is accepted ("MESH", "LAMP", "CAMERA", "EMPTY",
    "ARMATURE", "CURVE", "FONT"); another type shows a warning.
    line=True: arrow from the object to it in the viewport.
    create=True: "+" button that creates an Empty and puts it in the field."""
    def __new__(cls, tip="", filter=None, line=False, create=False, **opts):
        return _meta(str.__new__(cls, ""), "object", tip, filter=filter, line=bool(line),
                     create=bool(create), **opts)


class Scene(str):
    """Pick a scene of the file with the mouse.

    In the game, args[name] is the scene name (str), ready for
    logic.addScene(args[name]); "" when nothing was picked."""
    def __new__(cls, tip="", **opts):
        return _meta(str.__new__(cls, ""), "scene", tip, **opts)


class Color(tuple):
    """Color with the color picker. Color(r, g, b) or Color(r, g, b, a).

    In the game, args[name] is a mathutils.Color-like sequence of 3 or 4
    floats, ready for obj.color (use 4 values for that)."""
    def __new__(cls, *values, tip="", **opts):
        if len(values) == 1:
            values = tuple(values[0])
        values = tuple(float(v) for v in values) or (1.0, 1.0, 1.0)
        if len(values) not in (3, 4):
            raise ValueError("Color needs 3 or 4 values (r, g, b[, a])")
        return _meta(tuple.__new__(cls, values), "color", tip, **opts)


class ObjectList(str):
    """Several objects of the scene, in order (waypoints, doors, spawn spots).

    The editor shows a list with add/remove. In the game, args[name] is the
    names joined by ";": turn it into objects with

        self.points = objects(self.object.scene, args["Points"])

    filter, line (path through them) and create work like in Object.
    Up to ~120 characters of names in total."""
    def __new__(cls, tip="", filter=None, line=False, create=False, **opts):
        return _meta(str.__new__(cls, ""), "objectlist", tip, filter=filter, line=bool(line),
                     create=bool(create), **opts)


class Point(tuple):
    """A position in the world: Point(x, y, z). Drawn as a cross in the
    viewport, with buttons to take the 3D cursor or the selected object.
    In the game, args[name] is a Vector (world coordinates).
    line=True: line from the object to the point."""
    def __new__(cls, x=0.0, y=0.0, z=0.0, tip="", line=False, **opts):
        return _meta(tuple.__new__(cls, (float(x), float(y), float(z))), "point", tip,
                     line=bool(line), **opts)


def objects(scene, value):
    """ObjectList value -> [KX_GameObject] found in the scene (missing ones skipped).
    Works in the game; scene is self.object.scene. Objects in hidden layers
    come too (ready for scene.addObject)."""
    found = []
    inactive = getattr(scene, "objectsInactive", None)
    for name in str(value or "").split(LIST_SEP):
        name = name.strip()
        if not name:
            continue
        if name in scene.objects:
            found.append(scene.objects[name])
        elif inactive is not None and name in inactive:
            found.append(inactive[name])
    return found


def Header(name, icon="FULLSCREEN", open=True):
    """Collapsible section title. Use it as an item of the args list:

        args = OrderedDict([Header("Combat"), ("Damage", 10)])

    Same as the older ("C_Header/Name/ICON", True) entry."""
    return ("C_Header/%s/%s" % (name, icon), bool(open))
