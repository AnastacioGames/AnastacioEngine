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
# Pure Python and no bpy: this module also runs inside exported games.

__all__ = ("Float", "Int", "Bool", "Text", "Choice", "Object", "Scene", "Color", "Header")


def _meta(value, kind, tip, **extra):
    value._range_meta = dict(kind=kind, tip=str(tip or ""), **extra)
    return value


def _num(v):
    return None if v is None else float(v)


class Float(float):
    """Float field. min and max together draw a slider; tip is the tooltip."""
    def __new__(cls, value=0.0, min=None, max=None, tip=""):
        return _meta(float.__new__(cls, value), "float", tip, min=_num(min), max=_num(max))


class Int(int):
    """Integer field. min and max together draw a slider; tip is the tooltip."""
    def __new__(cls, value=0, min=None, max=None, tip=""):
        return _meta(int.__new__(cls, value), "int", tip, min=_num(min), max=_num(max))


class Bool(int):
    """Checkbox with a tooltip (bool itself can't be subclassed)."""
    def __new__(cls, value=False, tip=""):
        return _meta(int.__new__(cls, bool(value)), "bool", tip)

    def __bool__(self):
        return int(self) != 0

    def __repr__(self):
        return "Bool(%r)" % bool(self)


class Text(str):
    """Text field with a tooltip."""
    def __new__(cls, value="", tip=""):
        return _meta(str.__new__(cls, value), "text", tip)


class Choice(str):
    """List of options in this order. Choice(default, item1, item2, ...).

    Without items the default is the only option; if the default isn't among
    the items, the first item is used."""
    def __new__(cls, default, *items, tip=""):
        items = tuple(str(i) for i in items) or (str(default),)
        return _meta(str.__new__(cls, default), "choice", tip, items=items)


class Object(str):
    """Pick another object of the scene with the mouse.

    In the game, args[name] is the KX_GameObject with that name, or None when
    nothing was picked or the object isn't in the scene."""
    def __new__(cls, tip=""):
        return _meta(str.__new__(cls, ""), "object", tip)


class Scene(str):
    """Pick a scene of the file with the mouse.

    In the game, args[name] is the scene name (str), ready for
    logic.addScene(args[name]); "" when nothing was picked."""
    def __new__(cls, tip=""):
        return _meta(str.__new__(cls, ""), "scene", tip)


class Color(tuple):
    """Color with the color picker. Color(r, g, b) or Color(r, g, b, a).

    In the game, args[name] is a mathutils.Color-like sequence of 3 or 4
    floats, ready for obj.color (use 4 values for that)."""
    def __new__(cls, *values, tip=""):
        if len(values) == 1:
            values = tuple(values[0])
        values = tuple(float(v) for v in values) or (1.0, 1.0, 1.0)
        if len(values) not in (3, 4):
            raise ValueError("Color needs 3 or 4 values (r, g, b[, a])")
        return _meta(tuple.__new__(cls, values), "color", tip)


def Header(name, icon="FULLSCREEN", open=True):
    """Collapsible section title. Use it as an item of the args list:

        args = OrderedDict([Header("Combat"), ("Damage", 10)])

    Same as the older ("C_Header/Name/ICON", True) entry."""
    return ("C_Header/%s/%s" % (name, icon), bool(open))
