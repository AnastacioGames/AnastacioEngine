# Smart Component Wizard: panel that builds a Smart Component without typing
# the args by hand. The code itself comes from modules/range_component_wizard.
#
# State lives in WindowManager.smart_wizard. Drawn inside Properties > Game >
# Component Manager (flowmenu) through draw_wizard(), and also from the Text
# Editor menu Text > New Smart Component. "Add Field" (smart_wizard.add_field)
# adds one field to the code of a component that already exists.

import os

import bpy
from bpy.app.handlers import persistent
from bpy.types import Operator, PropertyGroup, UIList
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty, FloatProperty,
                       FloatVectorProperty, IntProperty, PointerProperty, StringProperty)

import range_component_wizard as W

PREVIEW_TEXT = "wizard_preview.py"

_KIND_INFO = (
    ("FLOAT", "Float", "Number with decimals (slider with min/max)", "IPO_LINEAR"),
    ("INT", "Int", "Whole number", "LINENUMBERS_ON"),
    ("BOOL", "Bool", "Checkbox on/off", "CHECKBOX_HLT"),
    ("TEXT", "Text", "Text", "FONT_DATA"),
    ("CHOICE", "Choice", "List of options", "COLLAPSEMENU"),
    ("OBJECT", "Object", "Pick an object of the scene", "OBJECT_DATA"),
    ("OBJECTLIST", "Object List", "Several objects in order (waypoints, doors...)", "OUTLINER_OB_GROUP_INSTANCE"),
    ("POINT", "Point", "A position in the world, with a cross in the viewport", "CURSOR"),
    ("SCENE", "Scene", "Pick a scene of the file", "SCENE_DATA"),
    ("COLOR", "Color", "Color with picker", "COLOR"),
    ("HEADER", "Section", "Title that opens and closes the fields below it", "FULLSCREEN"),
)
_KIND_ITEMS = [(k, n, d, i, idx) for idx, (k, n, d, i) in enumerate(_KIND_INFO)]
_KIND_ICON = {k: i for k, n, d, i in _KIND_INFO}
_KIND_NAME = {k: n for k, n, d, i in _KIND_INFO}

_FILTER_ITEMS = [
    ("ANY", "Any Type", "Any object", 0),
    ("MESH", "Mesh", "", 1),
    ("LAMP", "Light", "", 2),
    ("CAMERA", "Camera", "", 3),
    ("EMPTY", "Empty", "", 4),
    ("ARMATURE", "Armature", "", 5),
    ("CURVE", "Curve", "", 6),
    ("FONT", "Text", "", 7),
]

_RECIPE_ITEMS = [(k, W.RECIPES[k]["label"], W.RECIPES[k]["tip"], idx)
                 for idx, k in enumerate(W.RECIPE_ORDER)]

_PHYSICS_ITEMS = [
    ("KEEP", "Keep", "Don't change the physics of the object", 0),
    ("NO_COLLISION", "No Collision", "", 1),
    ("STATIC", "Static", "", 2),
    ("DYNAMIC", "Dynamic", "", 3),
    ("RIGID_BODY", "Rigid Body", "", 4),
    ("CHARACTER", "Character", "", 5),
]


class SmartWizardField(PropertyGroup):
    name = StringProperty(name="Name", default="Campo", description="Label of the field and key of args[...]")
    kind = EnumProperty(name="Type", items=_KIND_ITEMS, default="FLOAT")
    f_default = FloatProperty(name="Default", default=0.0)
    i_default = IntProperty(name="Default", default=0)
    b_default = BoolProperty(name="Default", default=False)
    s_default = StringProperty(name="Default", default="")
    c_default = FloatVectorProperty(name="Default", subtype='COLOR', size=4, min=0.0, max=1.0,
                                    default=(1.0, 1.0, 1.0, 1.0))
    p_default = FloatVectorProperty(name="Default", subtype='XYZ', size=3, default=(0.0, 0.0, 0.0))
    items = StringProperty(name="Options", default="A, B, C",
                           description="Options separated by comma. The default must be one of them")
    use_min = BoolProperty(name="Min", default=False)
    use_max = BoolProperty(name="Max", default=False)
    v_min = FloatProperty(name="Min", default=0.0)
    v_max = FloatProperty(name="Max", default=10.0)
    tip = StringProperty(name="Tip", default="", description="Shown when the mouse is over the field")
    icon = StringProperty(name="Icon", default="FULLSCREEN", description="Icon name (e.g. AUTO, COLOR)")
    start_open = BoolProperty(name="Starts Open", default=True)
    line = BoolProperty(name="Line in Viewport", default=False,
                        description="Object: arrow to it. Object List: path through them. Point: line to it")
    circle = BoolProperty(name="Circle in Viewport", default=False,
                          description="Circle around the object with this value as radius")
    required = BoolProperty(name="Required", default=False, description="Warning while it is empty")
    use_warn = BoolProperty(name="Warn Above", default=False, description="Warning when the value is bigger")
    warn_above = FloatProperty(name="Warn Above", default=10.0)
    filter = EnumProperty(name="Only", items=_FILTER_ITEMS, default="ANY",
                          description="Type of object accepted (another type shows a warning)")
    auto = StringProperty(name="Auto Pick", default="",
                          description="When added, pick the first object whose name starts with this "
                                      "(e.g. Jogador). Empty = off")
    create = BoolProperty(name="Create Button", default=False,
                          description="\"+\" button in the box that creates an object for this field")
    use_show_if = BoolProperty(name="Show Only If", default=False,
                               description="Hide this field unless another field has some value")
    show_if_field = StringProperty(name="Field", default="",
                                   description="Name of the other field (a Bool, or any field with a value below)")
    show_if_value = StringProperty(name="Value", default="",
                                   description="Value the other field must have. Empty: the Bool is on")

    def to_dict(self):
        k = self.kind
        default = {"FLOAT": self.f_default, "INT": self.i_default, "BOOL": self.b_default,
                   "COLOR": tuple(self.c_default), "POINT": tuple(self.p_default)}.get(k, self.s_default)
        num = k in ("FLOAT", "INT")
        objs = k in ("OBJECT", "OBJECTLIST")
        show_if = None
        if self.use_show_if and self.show_if_field.strip() and k != "HEADER":
            v = self.show_if_value.strip()
            show_if = (self.show_if_field.strip(), v) if v else self.show_if_field.strip()
        return W.field(
            self.name.strip(), k, default,
            min=self.v_min if num and self.use_min else None,
            max=self.v_max if num and self.use_max else None,
            tip=self.tip, items=[i.strip() for i in self.items.split(",")],
            icon=self.icon.strip() or "FULLSCREEN", open=self.start_open,
            line=self.line and k in ("OBJECT", "OBJECTLIST", "POINT"),
            circle=self.circle and k == "FLOAT",
            required=self.required and k in ("OBJECT", "OBJECTLIST", "SCENE", "TEXT"),
            warn_above=self.warn_above if num and self.use_warn else None,
            filter="" if not objs or self.filter == "ANY" else self.filter,
            create=self.create and objs, auto=self.auto if k == "OBJECT" else "",
            show_if=show_if)

    def from_dict(self, f):
        self.name, self.kind, self.tip = f["name"], f["kind"], f["tip"]
        d = f["default"]
        if f["kind"] == "FLOAT":
            self.f_default = d
        elif f["kind"] == "INT":
            self.i_default = d
        elif f["kind"] == "BOOL":
            self.b_default = bool(d)
        elif f["kind"] == "COLOR":
            self.c_default = (tuple(d) + (1.0,))[:4]
        elif f["kind"] == "POINT":
            self.p_default = (tuple(d) + (0.0, 0.0, 0.0))[:3]
        else:
            self.s_default = str(d)
        self.use_min, self.use_max = f["min"] is not None, f["max"] is not None
        if f["min"] is not None:
            self.v_min = f["min"]
        if f["max"] is not None:
            self.v_max = f["max"]
        if f["items"]:
            self.items = ", ".join(f["items"])
        self.icon, self.start_open = f["icon"], f["open"]
        self.line, self.circle, self.required = f["line"], f["circle"], f["required"]
        self.use_warn = f["warn_above"] is not None
        if f["warn_above"] is not None:
            self.warn_above = f["warn_above"]
        self.filter = f["filter"] or "ANY"
        self.auto, self.create = f["auto"], f["create"]
        cond = f["show_if"]
        self.use_show_if = bool(cond)
        if isinstance(cond, str):
            self.show_if_field, self.show_if_value = cond, ""
        elif cond:
            self.show_if_field, self.show_if_value = cond[0], str(cond[1])


def _module_changed(self, context):
    if self.module and not self.class_edited:
        self["class_name"] = W.class_name(self.module)


def _class_changed(self, context):
    self["class_edited"] = True


class SmartWizardSettings(PropertyGroup):
    module = StringProperty(name="File", default="meu_component", update=_module_changed,
                            description="Module name: becomes the file name (letters, numbers and _)")
    class_name = StringProperty(name="Class", default="MeuComponent", update=_class_changed)
    class_edited = BoolProperty(default=False)
    recipe = EnumProperty(name="Recipe", items=_RECIPE_ITEMS, default="EMPTY",
                          description="Starting point: fields and game code ready to adjust")
    loaded_recipe = StringProperty(default="EMPTY")
    fields = CollectionProperty(type=SmartWizardField)
    index = IntProperty(default=0)
    physics = EnumProperty(name="Physics", items=_PHYSICS_ITEMS, default="KEEP",
                           description="Physics the object gets when the component is added")
    save_to = EnumProperty(name="Save As", default="TEXT", items=[
        ("TEXT", "Text in the .blend", "Internal text: travels with the .blend, no saving needed", 0),
        ("FILE", "File in //scripts", "scripts/<file>.py next to the .blend (needs the .blend saved)", 1),
    ])
    attach = BoolProperty(name="Add to Active Object", default=True)
    open_code = BoolProperty(name="Open Code", default=True, description="Show the code in a Text Editor")
    show_preview = BoolProperty(name="Preview", default=True,
                                description="How the component box will look")
    # Add Field (existing component): the field being added.
    new_field = PointerProperty(type=SmartWizardField)


def _wizard(context):
    return context.window_manager.smart_wizard


def _physics(settings):
    return "" if settings.physics == "KEEP" else settings.physics


def _fields(settings):
    return [f.to_dict() for f in settings.fields]


def _code(s):
    label = W.RECIPES[s.loaded_recipe]["label"] if s.loaded_recipe != "EMPTY" else s.class_name.strip()
    return W.generate(s.module.strip() or "meu_component", s.class_name.strip() or "MeuComponent",
                      _fields(s), s.loaded_recipe, _physics(s), label=label)


# ----------------------------------------------------------------------------
# List

class SMARTWIZ_UL_fields(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        if item.kind == "HEADER":
            row.label(text=item.name or "Section", icon="FULLSCREEN")
            return
        row.prop(item, "name", text="", emboss=False, icon=_KIND_ICON.get(item.kind, "DOT"))
        extra = []
        if item.line and item.kind in ("OBJECT", "OBJECTLIST", "POINT"):
            extra.append("line")
        if item.circle and item.kind == "FLOAT":
            extra.append("circle")
        if item.required:
            extra.append("required")
        if item.use_show_if:
            extra.append("if " + item.show_if_field)
        sub = row.row()
        sub.alignment = 'RIGHT'
        sub.label(text=_KIND_NAME[item.kind] + (" · " + ", ".join(extra) if extra else ""))


# ----------------------------------------------------------------------------
# Operators

class SMARTWIZ_OT_load_recipe(Operator):
    bl_idname = "smart_wizard.load_recipe"
    bl_label = "Use Recipe"
    bl_description = "Replace the field list with the fields of the recipe"
    bl_options = {'INTERNAL'}

    def invoke(self, context, event):
        if len(_wizard(context).fields):
            return context.window_manager.invoke_confirm(self, event)
        return self.execute(context)

    def execute(self, context):
        s = _wizard(context)
        s.fields.clear()
        for f in W.recipe_fields(s.recipe):
            s.fields.add().from_dict(f)
        s.index = 0
        s.loaded_recipe = s.recipe
        if s.module in ("", "meu_component") or s.module.startswith("meu_"):
            s.module = "meu_" + W.identifier(W.RECIPES[s.recipe]["label"])
        s.physics = W.RECIPES[s.recipe].get("physics") or "KEEP"
        return {'FINISHED'}


class SMARTWIZ_OT_field_add(Operator):
    bl_idname = "smart_wizard.field_add"
    bl_label = "Add Field"
    bl_description = "Add a field after the selected one"
    bl_options = {'INTERNAL'}

    kind = EnumProperty(items=_KIND_ITEMS, default="FLOAT")

    def execute(self, context):
        s = _wizard(context)
        names = {f.name for f in s.fields}
        base = "Seção" if self.kind == "HEADER" else _KIND_NAME[self.kind]
        name, i = base, 2
        while name in names:
            name, i = "%s %d" % (base, i), i + 1
        f = s.fields.add()
        _new_field_defaults(f, self.kind, name)
        new = len(s.fields) - 1
        target = min(s.index + 1, new) if new else 0
        s.fields.move(new, target)
        s.index = target
        return {'FINISHED'}


def _new_field_defaults(f, kind, name):
    f.kind = kind
    f.name = name
    if kind == "FLOAT":
        f.f_default, f.use_min, f.use_max, f.v_min, f.v_max = 1.0, True, True, 0.0, 10.0
    elif kind == "INT":
        f.i_default, f.use_min, f.use_max, f.v_min, f.v_max = 1, True, True, 0.0, 10.0
    elif kind == "CHOICE":
        f.items, f.s_default = "A, B, C", "A"
    elif kind in ("OBJECT", "OBJECTLIST"):
        f.line = True
        f.create = kind == "OBJECTLIST"
    elif kind == "POINT":
        f.line, f.p_default = True, (0.0, 0.0, 1.0)


class SMARTWIZ_OT_field_remove(Operator):
    bl_idname = "smart_wizard.field_remove"
    bl_label = "Remove Field"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        s = _wizard(context)
        if 0 <= s.index < len(s.fields):
            s.fields.remove(s.index)
            s.index = max(0, min(s.index, len(s.fields) - 1))
        return {'FINISHED'}


class SMARTWIZ_OT_field_move(Operator):
    bl_idname = "smart_wizard.field_move"
    bl_label = "Move Field"
    bl_options = {'INTERNAL'}

    direction = IntProperty(default=-1)

    def execute(self, context):
        s = _wizard(context)
        new = s.index + self.direction
        if 0 <= s.index < len(s.fields) and 0 <= new < len(s.fields):
            s.fields.move(s.index, new)
            s.index = new
        return {'FINISHED'}


class SMARTWIZ_OT_field_duplicate(Operator):
    bl_idname = "smart_wizard.field_duplicate"
    bl_label = "Duplicate Field"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        s = _wizard(context)
        if not (0 <= s.index < len(s.fields)):
            return {'CANCELLED'}
        d = s.fields[s.index].to_dict()
        d["name"] += " 2"
        s.fields.add().from_dict(d)
        s.fields.move(len(s.fields) - 1, s.index + 1)
        s.index += 1
        return {'FINISHED'}


def _show_text(context, text):
    if context.screen is None:
        return False
    for area in context.screen.areas:
        if area.type == 'TEXT_EDITOR':
            area.spaces.active.text = text
            return True
    return False


class SMARTWIZ_OT_create(Operator):
    bl_idname = "smart_wizard.create"
    bl_label = "Create Smart Component"
    bl_description = "Write the component code and (optionally) add it to the active object"

    def execute(self, context):
        s = _wizard(context)
        module, cls = s.module.strip(), s.class_name.strip()
        errors = W.check(module, cls, _fields(s))
        if errors:
            self.report({'ERROR'}, errors[0])
            return {'CANCELLED'}

        code = _code(s)
        filename = module + ".py"

        if s.save_to == 'TEXT':
            if filename in bpy.data.texts:
                self.report({'ERROR'}, "There is already a text %s: pick another file name" % filename)
                return {'CANCELLED'}
            text = bpy.data.texts.new(filename)
            text.write(code)
        else:
            if not bpy.data.filepath:
                self.report({'ERROR'}, "Save the .blend first (or use Save As: Text in the .blend)")
                return {'CANCELLED'}
            folder = os.path.join(os.path.dirname(bpy.data.filepath), "scripts")
            path = os.path.join(folder, filename)
            if os.path.exists(path):
                self.report({'ERROR'}, "File already exists: %s" % path)
                return {'CANCELLED'}
            os.makedirs(folder, exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(code)
            text = bpy.data.texts.load(path)

        full = "%s.%s" % (module, cls)
        msg = "Created %s" % full
        ob = context.active_object
        if s.attach and ob is not None:
            try:
                result = bpy.ops.logic.python_component_register(component_name=full)
            except RuntimeError as e:
                result = {str(e)}
            if 'FINISHED' in result:
                msg += " and added to %s" % ob.name
            else:
                self.report({'WARNING'}, "Created %s, but could not add it: see the console" % full)
                msg = None

        if s.open_code and not _show_text(context, text) and msg:
            msg += " (open it in a Text Editor: %s)" % text.name
        if msg:
            self.report({'INFO'}, msg)
        try:
            bpy.ops.wm.flowmenu_component_list_refresh()
        except Exception:
            pass
        return {'FINISHED'}


class SMARTWIZ_OT_preview(Operator):
    bl_idname = "smart_wizard.preview"
    bl_label = "Preview Code"
    bl_description = ("Show the code in a Text Editor (text '%s'). It follows every change "
                      "while the text exists" % PREVIEW_TEXT)

    def execute(self, context):
        text = bpy.data.texts.get(PREVIEW_TEXT) or bpy.data.texts.new(PREVIEW_TEXT)
        text.clear()
        text.write(_code(_wizard(context)))
        _live["code"] = text.as_string()
        if not _show_text(context, text):
            self.report({'INFO'}, "Open the text %s in a Text Editor" % PREVIEW_TEXT)
        return {'FINISHED'}


# Live code preview: the text follows the wizard while it exists. Checked on
# scene updates (cheap: only regenerates when the wizard settings changed).
_live = {"sig": None, "code": None}


def _signature(s):
    return (s.module, s.class_name, s.loaded_recipe, s.physics,
            tuple(tuple(sorted(f.to_dict().items(), key=lambda kv: kv[0])) for f in s.fields))


@persistent
def _live_preview(scene):
    text = bpy.data.texts.get(PREVIEW_TEXT)
    if text is None:
        return
    wm = bpy.context.window_manager
    if wm is None:
        return
    s = wm.smart_wizard
    try:
        sig = repr(_signature(s))
    except Exception:
        return
    if sig == _live["sig"]:
        return
    _live["sig"] = sig
    code = _code(s)
    if code != _live["code"]:
        _live["code"] = code
        text.clear()
        text.write(code)


# ----------------------------------------------------------------------------
# Add Field to an existing component

def _component_source(comp):
    """(text or None, file path or None) where the component's code lives."""
    module = comp.module
    text = bpy.data.texts.get(module + ".py") or bpy.data.texts.get(module)
    path = None
    if text is not None and text.filepath and not text.is_in_memory:
        path = bpy.path.abspath(text.filepath)
    if text is None and bpy.data.filepath:
        folder = os.path.dirname(bpy.data.filepath)
        for cand in (os.path.join(folder, module + ".py"), os.path.join(folder, "scripts", module + ".py")):
            if os.path.isfile(cand):
                path = cand
                break
        if path:
            for t in bpy.data.texts:
                if t.filepath and os.path.normcase(bpy.path.abspath(t.filepath)) == os.path.normcase(path):
                    text = t
                    break
    return text, path


class SMARTWIZ_OT_add_field(Operator):
    bl_idname = "smart_wizard.add_field"
    bl_label = "Add Field"
    bl_description = "Add a field to the code of this component (only the args list changes)"
    bl_options = {'REGISTER', 'UNDO'}

    index = IntProperty(options={'HIDDEN'})

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def _comp(self, context):
        comps = context.active_object.game.components
        return comps[self.index] if self.index < len(comps) else None

    def invoke(self, context, event):
        comp = self._comp(context)
        if comp is None:
            return {'CANCELLED'}
        text, path = _component_source(comp)
        if text is None and path is None:
            self.report({'ERROR'}, "Code of %s not found (text or file %s.py)" % (comp.name, comp.module))
            return {'CANCELLED'}
        f = _wizard(context).new_field
        names = {p.name for p in comp.properties}
        name, i = "Campo", 2
        while name in names:
            name, i = "Campo %d" % i, i + 1
        _new_field_defaults(f, f.kind or "FLOAT", name)
        return context.window_manager.invoke_props_dialog(self, width=380)

    def draw(self, context):
        self.layout.label(text="New field in %s" % self._comp(context).name, icon="ZOOMIN")
        _draw_field(self.layout, _wizard(context).new_field)

    def execute(self, context):
        comp = self._comp(context)
        if comp is None:
            return {'CANCELLED'}
        f = _wizard(context).new_field.to_dict()
        if f["kind"] != "HEADER" and f["name"] in comp.properties:
            self.report({'ERROR'}, "There is already a field %s" % f["name"])
            return {'CANCELLED'}
        problems = W.check("m", "C", [f])
        if problems:
            self.report({'ERROR'}, problems[0])
            return {'CANCELLED'}
        text, path = _component_source(comp)
        if text is not None:
            source = text.as_string()
        else:
            with open(path, encoding="utf-8") as fh:
                source = fh.read()
        new, error = W.add_field(source, comp.name, f)
        if error:
            self.report({'ERROR'}, error)
            return {'CANCELLED'}
        try:
            compile(new, comp.module, "exec")
        except SyntaxError as e:
            self.report({'ERROR'}, "Could not add it safely (%s): nothing changed" % e.msg)
            return {'CANCELLED'}
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(new)
        if text is not None:
            text.clear()
            text.write(new)
        try:
            bpy.ops.logic.python_component_reload(index=self.index)
        except RuntimeError as e:
            self.report({'WARNING'}, "Field written, reload failed: %s" % e)
            return {'FINISHED'}
        self.report({'INFO'}, "Field %s added to %s" % (f["name"], comp.name))
        return {'FINISHED'}


# ----------------------------------------------------------------------------
# Drawing

def _draw_field(layout, f):
    k = f.kind
    col = layout.column()
    row = col.row(align=True)
    row.prop(f, "kind", text="")
    row.prop(f, "name", text="")
    if k == "HEADER":
        row = col.row(align=True)
        row.prop(f, "icon")
        row.prop(f, "start_open")
        return

    if k == "FLOAT":
        col.prop(f, "f_default")
    elif k == "INT":
        col.prop(f, "i_default")
    elif k == "BOOL":
        col.prop(f, "b_default")
    elif k == "TEXT":
        col.prop(f, "s_default")
    elif k == "CHOICE":
        col.prop(f, "items")
        col.prop(f, "s_default")
    elif k == "COLOR":
        col.prop(f, "c_default")
    elif k == "POINT":
        col.prop(f, "p_default")

    if k in ("FLOAT", "INT"):
        row = col.row(align=True)
        row.prop(f, "use_min", text="")
        sub = row.row(align=True)
        sub.active = f.use_min
        sub.prop(f, "v_min")
        row.prop(f, "use_max", text="")
        sub = row.row(align=True)
        sub.active = f.use_max
        sub.prop(f, "v_max")
        row = col.row(align=True)
        row.prop(f, "use_warn", text="")
        sub = row.row(align=True)
        sub.active = f.use_warn
        sub.prop(f, "warn_above")

    col.prop(f, "tip")

    if k in ("OBJECT", "OBJECTLIST"):
        col.prop(f, "filter")
        row = col.row()
        row.prop(f, "line", text="Path" if k == "OBJECTLIST" else "Arrow to it")
        row.prop(f, "required")
        row.prop(f, "create", text="\"+\" Button")
        if k == "OBJECT":
            col.prop(f, "auto")
    elif k == "POINT":
        col.prop(f, "line", text="Line to it")
    elif k == "FLOAT":
        col.prop(f, "circle", text="Circle with this radius")
    elif k in ("SCENE", "TEXT"):
        col.prop(f, "required")

    row = col.row(align=True)
    row.prop(f, "use_show_if", text="Show only if")
    sub = row.row(align=True)
    sub.active = f.use_show_if
    sub.prop(f, "show_if_field", text="")
    sub.prop(f, "show_if_value", text="")


def _preview_visible(fields_by_name, f):
    if not f.use_show_if or not f.show_if_field.strip():
        return True
    other = fields_by_name.get(f.show_if_field.strip())
    if other is None:
        return True
    want = f.show_if_value.strip()
    d = other.to_dict()["default"]
    if not want:
        return bool(d)
    return str(d) == want


def _draw_preview(layout, s):
    """The component box as it will look (defaults; show_if from the defaults)."""
    box = layout.box()
    box.label(text=s.class_name or "Component", icon="SCRIPTPLUGINS")
    col = box.column()
    by_name = {f.name: f for f in s.fields}
    open_ = True
    for f in s.fields:
        if f.kind == "HEADER":
            row = col.row()
            row.scale_y = 1.2
            row.label(text=f.name, icon=f.icon if f.icon else "FULLSCREEN")
            open_ = f.start_open
            continue
        if not open_ or not _preview_visible(by_name, f):
            continue
        row = col.row()
        row.label(text=f.name, icon="DOT")
        k = f.kind
        prop = {"FLOAT": "f_default", "INT": "i_default", "BOOL": "b_default", "TEXT": "s_default",
                "COLOR": "c_default", "POINT": "p_default"}.get(k)
        if prop:
            sub = row.row(align=True)
            sub.prop(f, prop, text="", slider=k in ("FLOAT", "INT") and f.use_min and f.use_max)
            if k == "POINT":
                sub.label(icon="CURSOR")
        elif k == "CHOICE":
            row.label(text=f.s_default or (f.items.split(",")[0].strip()), icon="COLLAPSEMENU")
        elif k == "OBJECTLIST":
            row.label(text="(list)  + Add Selected" + ("  + New" if f.create else ""),
                      icon="OUTLINER_OB_GROUP_INSTANCE")
        else:
            row.label(text="(pick %s)%s" % (_KIND_NAME[k].lower(), "  +" if f.create else ""),
                      icon=_KIND_ICON[k])
        if f.required:
            col.label(text="Empty: pick one", icon="ERROR")


def draw_wizard(layout, context):
    s = _wizard(context)

    row = layout.row(align=True)
    row.prop(s, "recipe", text="")
    row.operator("smart_wizard.load_recipe", text="Use Recipe", icon="IMPORT")

    col = layout.column(align=True)
    col.prop(s, "module")
    col.prop(s, "class_name")

    layout.label(text="Fields (args)", icon="SETTINGS")
    row = layout.row()
    row.template_list("SMARTWIZ_UL_fields", "", s, "fields", s, "index", rows=5)
    side = row.column(align=True)
    side.operator_menu_enum("smart_wizard.field_add", "kind", text="", icon="ZOOMIN")
    side.operator("smart_wizard.field_remove", text="", icon="ZOOMOUT")
    side.separator()
    side.operator("smart_wizard.field_move", text="", icon="TRIA_UP").direction = -1
    side.operator("smart_wizard.field_move", text="", icon="TRIA_DOWN").direction = 1
    side.separator()
    side.operator("smart_wizard.field_duplicate", text="", icon="GHOST")

    if 0 <= s.index < len(s.fields):
        _draw_field(layout.box(), s.fields[s.index])

    if s.loaded_recipe != "EMPTY":
        missing = W.recipe_missing(s.loaded_recipe, _fields(s))
        if missing:
            layout.label(text="Recipe code needs: %s (update() stays empty)" % ", ".join(missing),
                         icon="ERROR")

    row = layout.row()
    row.prop(s, "show_preview", icon="TRIA_DOWN" if s.show_preview else "TRIA_RIGHT", emboss=False)
    if s.show_preview and len(s.fields):
        _draw_preview(layout, s)

    col = layout.column()
    col.prop(s, "physics")
    col.prop(s, "save_to")
    row = col.row()
    row.prop(s, "attach")
    row.prop(s, "open_code")

    for err in W.check(s.module.strip(), s.class_name.strip(), _fields(s))[:2]:
        layout.label(text=err, icon="ERROR")

    row = layout.row(align=True)
    row.scale_y = 1.3
    row.operator("smart_wizard.create", icon="SCRIPTPLUGINS")
    row.operator("smart_wizard.preview", text="", icon="VIEWZOOM")


def _text_menu(self, context):
    self.layout.separator()
    self.layout.operator("smart_wizard.popup", icon="SCRIPTPLUGINS")


class SMARTWIZ_OT_popup(Operator):
    bl_idname = "smart_wizard.popup"
    bl_label = "New Smart Component..."
    bl_description = "Open the Smart Component Wizard"

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=480)

    def draw(self, context):
        self.layout.label(text="Smart Component Wizard", icon="SCRIPTPLUGINS")
        draw_wizard(self.layout, context)

    def execute(self, context):
        return {'FINISHED'}


classes = (
    SmartWizardField,
    SmartWizardSettings,
    SMARTWIZ_UL_fields,
    SMARTWIZ_OT_load_recipe,
    SMARTWIZ_OT_field_add,
    SMARTWIZ_OT_field_remove,
    SMARTWIZ_OT_field_move,
    SMARTWIZ_OT_field_duplicate,
    SMARTWIZ_OT_create,
    SMARTWIZ_OT_preview,
    SMARTWIZ_OT_add_field,
    SMARTWIZ_OT_popup,
)


def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.WindowManager.smart_wizard = PointerProperty(type=SmartWizardSettings)
    bpy.types.TEXT_MT_text.append(_text_menu)
    if _live_preview not in bpy.app.handlers.scene_update_post:
        bpy.app.handlers.scene_update_post.append(_live_preview)


def unregister():
    if _live_preview in bpy.app.handlers.scene_update_post:
        bpy.app.handlers.scene_update_post.remove(_live_preview)
    bpy.types.TEXT_MT_text.remove(_text_menu)
    del bpy.types.WindowManager.smart_wizard
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
