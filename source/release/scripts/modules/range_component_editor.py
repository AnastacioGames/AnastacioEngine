# Smart Components: the optional "Editor" side of a Python Component.
#
#     class Patrol(types.KX_PythonComponent):
#         args = OrderedDict([("Speed", Float(2.0, min=0, max=20))])
#         requires = {"physics": "DYNAMIC", "components": ["health.Health"]}
#
#         def start(self, args): ...          # game only
#
#         class Editor:                        # editor only, never runs in the game
#             def on_attach(self, obj): ...    # right after the component is added
#             def on_change(self, obj, name, value):   # each field, on any change
#                 if name == "Speed" and value > 15:
#                     return "Too fast"        # warning drawn under the field
#             buttons = [("Add waypoint", "add_waypoint", "PLUS")]
#             def add_waypoint(self, obj, context): ...
#
# Inside Editor methods: self.object (bpy Object), self.component (the bpy
# PythonComponent) and self.args (read/write the fields by name). bpy may be
# imported inside the methods; at module level it would break the exported game.
#
# The module is imported here with a fake Range, like the C loader does
# (blenkernel/intern/python_component.c), and cached until the file changes.
# Every call into user code is guarded: an error shows in the component box
# and is printed once, the editor never goes down because of a component.

import bpy
import os
import sys
import time
import traceback
from types import ModuleType
from bpy.app.handlers import persistent

__all__ = ("editor_of", "state_of", "attach", "run_button")

_RANGE_SUBMODULES = ("types", "logic", "events", "render", "constraints", "application",
                     "imgui", "network", "audio", "texture")

_cache = {}         # (blend path, "module.Class") -> _Entry
_states = {}        # component pointer -> _State
_printed = set()    # errors already printed to the console
_MTIME_CHECK = 1.0  # seconds between file change checks


class _FakeComponent:
    """Stands for KX_PythonComponent while importing in the editor."""


class _Anything:
    """Whatever the module uses from Range at import time (logic.globalDict,
    events.WKEY, ...): any attribute, call, item or iteration just works."""

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return self

    def __call__(self, *args, **kwargs):
        return self

    def __getitem__(self, key):
        return self

    def __setitem__(self, key, value):
        pass

    def __contains__(self, key):
        return False

    def __iter__(self):
        return iter(())

    def __bool__(self):
        return False


class _FakeSubmodule(ModuleType):
    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return _Anything()


class _Entry:
    __slots__ = ("file", "mtime", "checked", "cls", "editor", "requires", "error")

    def __init__(self):
        self.file = None
        self.mtime = 0.0
        self.checked = 0.0
        self.cls = None
        self.editor = None
        self.requires = None
        self.error = None


class _State:
    __slots__ = ("entry", "values", "warnings", "error")

    def __init__(self):
        self.entry = None
        self.values = None
        self.warnings = {}
        self.error = None


class _Args:
    """self.args inside Editor: args["Speed"] reads, args["Speed"] = 3 writes."""

    def __init__(self, component):
        self._props = component.properties

    def __contains__(self, name):
        return name in self._props

    def __getitem__(self, name):
        return _plain(self._props[name].value)

    def __setitem__(self, name, value):
        self._props[name].value = value

    def get(self, name, default=None):
        return self[name] if name in self._props else default

    def keys(self):
        return [p.name for p in self._props if not _is_layout(p.name)]

    def items(self):
        return [(k, self[k]) for k in self.keys()]


def _is_layout(name):
    return name.startswith(("C_Header", "C_Collapse", "C_Icons"))


def _plain(value):
    # Vectors and colors come as mathutils/bpy arrays: give tuples (also hashable).
    if isinstance(value, (bool, int, float, str)) or value is None:
        return value
    if isinstance(value, bpy.types.ID):
        return value
    try:
        return tuple(value)
    except TypeError:
        return value


def _search_paths():
    paths = []
    if bpy.data.filepath:
        paths.append(os.path.dirname(bpy.data.filepath))
    for lib in bpy.data.libraries:
        paths.append(os.path.dirname(bpy.path.abspath(lib.filepath)))
    return [os.path.normcase(os.path.abspath(p)) for p in paths if p]


def _import_component(module_name):
    """Import the component module with a fake Range. Returns the module."""
    paths = _search_paths()
    saved_path = list(sys.path)
    names = ["Range", "Range.args"] + ["Range." + s for s in _RANGE_SUBMODULES]
    saved_modules = {n: sys.modules[n] for n in names if n in sys.modules}
    before = set(sys.modules)

    import range_args
    rangemod = ModuleType("Range")
    sub = _FakeSubmodule("types")
    sub.KX_PythonComponent = _FakeComponent
    sub.steam = None
    for s in _RANGE_SUBMODULES:
        setattr(rangemod, s, sub)
    rangemod.args = range_args
    rangemod.__component__ = True
    for s in _RANGE_SUBMODULES:
        sys.modules["Range." + s] = sub
    sys.modules["Range"] = rangemod
    sys.modules["Range.args"] = range_args

    sys.path[:0] = paths
    try:
        __import__(module_name)
        return sys.modules[module_name]
    finally:
        sys.path[:] = saved_path
        # Drop what came from the game folder so the next import sees fresh code.
        for name in set(sys.modules) - before:
            mod = sys.modules.get(name)
            path = os.path.normcase(os.path.abspath(getattr(mod, "__file__", None) or ""))
            if (name == module_name or name.split(".")[0] in ("scripts", "anastacio_network")
                    or any(path.startswith(p) for p in paths)):
                del sys.modules[name]
        for n in names:
            sys.modules.pop(n, None)
        sys.modules.update(saved_modules)


def _load(entry, module, classname):
    entry.cls = entry.editor = entry.requires = entry.error = None
    try:
        mod = _import_component(module)
        entry.file = getattr(mod, "__file__", None)
        if not entry.file or not os.path.isfile(entry.file):
            entry.file = None   # internal text (Text Editor): watched by its content
        entry.mtime = _signature(entry.file, module)
        cls = getattr(mod, classname)
        entry.cls = cls
        entry.editor = getattr(cls, "Editor", None)
        entry.requires = getattr(cls, "requires", None)
    except Exception:
        # Console only: Add and Reload already report it, and game code that
        # can't be imported here is still a valid component.
        _report("%s.%s" % (module, classname), "editor import")


def _signature(path, module):
    """File mtime, or a hash of the internal text the module came from."""
    if path:
        try:
            return os.stat(path).st_mtime
        except OSError:
            return 0.0
    text = bpy.data.texts.get(module + ".py") or bpy.data.texts.get(module)
    return hash(text.as_string()) if text else 0.0


def _entry_of(component):
    """Cached info for the component class; reimports when the file changes."""
    module, classname = component.module, component.name
    if not module or not classname:
        return None
    key = (bpy.data.filepath, module + "." + classname)
    entry = _cache.get(key)
    now = time.monotonic()
    if entry is None:
        entry = _cache[key] = _Entry()
        _load(entry, module, classname)
        entry.checked = now
    elif now - entry.checked > _MTIME_CHECK:
        entry.checked = now
        if _signature(entry.file, module) != entry.mtime:
            _load(entry, module, classname)
    return entry


def _report(where, what):
    text = traceback.format_exc()
    last = text.strip().splitlines()[-1]
    if (where, text) not in _printed:
        _printed.add((where, text))
        print("Component %s (%s):\n%s" % (where, what, text))
    return last


def _instance(entry, obj, component):
    ed = entry.editor()
    ed.object = obj
    ed.component = component
    ed.args = _Args(component)
    return ed


def _find(obj_ptr, comp_ptr):
    for obj in bpy.data.objects:
        if obj.as_pointer() == obj_ptr:
            for comp in obj.game.components:
                if comp.as_pointer() == comp_ptr:
                    return obj, comp
            return obj, None
    return None, None


# ---------------------------------------------------------------------------
# Public helpers (used by the Game Components panel)

def editor_of(component):
    """The Editor class of the component, or None."""
    entry = _entry_of(component)
    return entry.editor if entry else None


def state_of(component):
    """(error, {field: warning}) to draw in the component box."""
    _ensure_handler()
    entry = _entry_of(component)
    state = _states.get(component.as_pointer())
    error = (entry.error if entry else None) or (state.error if state else None)
    return error, (state.warnings if state else {})


def run_button(context, obj, component, method):
    entry = _entry_of(component)
    if not entry or not entry.editor:
        return "Component has no Editor"
    state = _states.setdefault(component.as_pointer(), _State())
    try:
        getattr(_instance(entry, obj, component), method)(obj, context)
        state.error = None
    except Exception:
        state.error = _report("%s.%s" % (component.module, component.name), method)
        return state.error
    return None


def attach(obj, component):
    """Apply 'requires' and call Editor.on_attach. Called once when added."""
    entry = _entry_of(component)
    if not entry or entry.error:
        return
    state = _states.setdefault(component.as_pointer(), _State())
    where = "%s.%s" % (component.module, component.name)
    req = entry.requires
    if req:
        try:
            physics = req.get("physics")
            if physics and obj.game.physics_type != physics:
                obj.game.physics_type = physics
            have = {c.module + "." + c.name for c in obj.game.components}
            for imp in req.get("components", ()):
                if imp not in have:
                    obj.game.components.new(imp)
        except Exception:
            state.error = _report(where, "requires")
    if entry.editor and hasattr(entry.editor, "on_attach"):
        try:
            _instance(entry, obj, component).on_attach(obj)
        except Exception:
            state.error = _report(where, "on_attach")


def _attached(obj_ptr, comp_ptr):
    """Entry point from C (BKE_python_component_attached)."""
    obj, comp = _find(obj_ptr, comp_ptr)
    if obj and comp:
        attach(obj, comp)


# ---------------------------------------------------------------------------
# on_change: values of the active object are compared on each scene update
# (only cheap reads; user code runs only when something changed).

def _snapshot(component):
    vals = {}
    for p in component.properties:
        if _is_layout(p.name):
            continue
        v = _plain(p.value)
        vals[p.name] = v.name if isinstance(v, bpy.types.ID) else v
    return vals


def _check_object(obj):
    for comp in obj.game.components:
        entry = _entry_of(comp)
        if not entry or not entry.editor or not hasattr(entry.editor, "on_change"):
            continue
        state = _states.setdefault(comp.as_pointer(), _State())
        values = _snapshot(comp)
        if state.entry is entry and state.values == values:
            continue
        # Something changed (or first look, or new code): validate every field,
        # so a warning that depends on another field stays right.
        changed = list(values)
        state.entry = entry
        state.values = values
        ed = _instance(entry, obj, comp)
        state.error = None
        for name in changed:
            try:
                msg = ed.on_change(obj, name, _plain(comp.properties[name].value))
            except Exception:
                state.error = _report("%s.%s" % (comp.module, comp.name), "on_change")
                break
            if msg:
                state.warnings[name] = str(msg)
            else:
                state.warnings.pop(name, None)
        for name in list(state.warnings):
            if name not in values:
                del state.warnings[name]
        # on_change may have changed values: take them as seen.
        state.values = _snapshot(comp)


@persistent
def _scene_update(scene):
    obj = bpy.context.active_object if hasattr(bpy.context, "active_object") else None
    if obj is None or not obj.game.components:
        return
    try:
        _check_object(obj)
    except Exception:
        _report("on_change", "scene update")


@persistent
def _load_post(_):
    _states.clear()


def _ensure_handler():
    handlers = bpy.app.handlers
    if _scene_update not in handlers.scene_update_post:
        handlers.scene_update_post.append(_scene_update)
    if _load_post not in handlers.load_post:
        handlers.load_post.append(_load_post)
