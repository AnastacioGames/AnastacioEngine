# Text Editor: Outline (classes and functions of the script, click to jump) and Insert Snippet
# (ready-made pieces of game code typed at the cursor with the current indentation).

import re

import bpy

# -- Outline --------------------------------------------------------------------------

# a regex scan and not ast: it keeps working while the code is half typed
RE_DEF = re.compile(r"^([ \t]*)(?:async[ \t]+)?(def|class)[ \t]+([A-Za-z_]\w*)")
_T3 = ('"' * 3, "'" * 3)
_cache = {"key": None, "items": []}


def _outline(text):
    """[(line number from 1, depth, kind, name)] of the text; cached by its content."""
    body = text.as_string()
    key = (text.name, hash(body))
    if _cache["key"] == key:
        return _cache["items"]
    items = []
    in_triple = None
    indents = []  # indentation of the open class/def blocks
    for n, line in enumerate(body.split("\n"), 1):
        if in_triple:
            if line.count(in_triple) % 2 == 1:
                in_triple = None
            continue
        m = RE_DEF.match(line)
        if m:
            indent = len(m.group(1).expandtabs(4))
            while indents and indents[-1] >= indent:
                indents.pop()
            items.append((n, len(indents), m.group(2), m.group(3)))
            indents.append(indent)
        code = line.split("#", 1)[0]
        for t in _T3:
            if code.count(t) % 2 == 1:
                in_triple = t
                break
    _cache["key"] = key
    _cache["items"] = items
    return items


class TEXT_PT_outline(bpy.types.Panel):
    bl_space_type = 'TEXT_EDITOR'
    bl_region_type = 'UI'
    bl_category = "Text"
    bl_label = "Outline"

    @classmethod
    def poll(cls, context):
        st = context.space_data
        return st and st.text is not None

    def draw(self, context):
        text = context.space_data.text
        box = self.layout.box()
        items = _outline(text)
        if not items:
            box.label("No classes or functions", icon='INFO')
            return
        current = text.current_line_index + 1
        # the block the cursor is in: the last definition at or before the cursor line
        here = None
        for item in items:
            if item[0] <= current:
                here = item
        col = box.column(align=True)
        col.operator_context = 'EXEC_DEFAULT'
        for item in items[:300]:
            line, depth, kind, name = item
            row = col.row(align=True)
            for _ in range(min(depth, 4)):
                row.label(text="", icon='BLANK1')  # methods under their class
            label = name + ("()" if kind == "def" else "")
            op = row.operator("text.jump", text=label, emboss=item is here,
                              icon='OBJECT_DATA' if kind == "class" else 'SCRIPT')
            op.line = line
        if len(items) > 300:
            box.label("... %d more" % (len(items) - 300))


# -- Snippets -------------------------------------------------------------------------
# $0 marks where the cursor ends. Indentation is 4 spaces; texts indented with tabs get tabs.

SNIPPETS = (
    ("SCRIPT", "Controller Script", "Script mode: runs every time the Python controller is triggered",
     "from bge import logic\n"
     "\n"
     "cont = logic.getCurrentController()\n"
     "own = cont.owner\n"
     "$0\n"),
    ("MODULE", "Controller Module Function", "Module mode (Module: script.main): receives the controller",
     "def main(cont):\n"
     "    own = cont.owner\n"
     "    $0\n"),
    ("COMPONENT", "Python Component", "Component attached to a Game Object (Add Component)",
     "from collections import OrderedDict\n"
     "\n"
     "import bge\n"
     "\n"
     "\n"
     "class Component(bge.types.KX_PythonComponent):\n"
     "    args = OrderedDict([\n"
     "        (\"Speed\", 1.0),\n"
     "    ])\n"
     "\n"
     "    def start(self, args):\n"
     "        self.speed = args[\"Speed\"]\n"
     "\n"
     "    def update(self):\n"
     "        $0\n"),
    ("INIT", "Run Once", "Code that runs only the first time (a property marks it)",
     "if \"init\" not in own:\n"
     "    own[\"init\"] = True\n"
     "    $0\n"),
    ("KEY", "Key Pressed", "Check a keyboard key (bge.events has the key codes)",
     "from bge import logic, events\n"
     "\n"
     "keyboard = logic.keyboard.inputs\n"
     "if keyboard[events.SPACEKEY].activated:\n"
     "    $0\n"),
    ("MOUSE", "Mouse Click", "Check the left mouse button",
     "from bge import logic, events\n"
     "\n"
     "if logic.mouse.inputs[events.LEFTMOUSE].activated:\n"
     "    $0\n"),
    ("MOVE", "Move With Keys", "WASD movement in the object's local axes",
     "from bge import logic, events\n"
     "\n"
     "keyboard = logic.keyboard.inputs\n"
     "speed = 0.1\n"
     "x = (keyboard[events.DKEY].active - keyboard[events.AKEY].active) * speed\n"
     "y = (keyboard[events.WKEY].active - keyboard[events.SKEY].active) * speed\n"
     "own.applyMovement((x, y, 0.0), True)\n"
     "$0\n"),
    ("RAY", "Ray Cast", "First object in front of the object (local Y axis)",
     "start = own.worldPosition\n"
     "end = start + own.getAxisVect((0.0, 1.0, 0.0)) * 10.0\n"
     "hit_object, hit_position, hit_normal = own.rayCast(end, start)\n"
     "if hit_object:\n"
     "    $0\n"),
    ("ADD", "Add Object", "Spawn a copy of an object from a hidden layer",
     "scene = logic.getCurrentScene()\n"
     "new_object = scene.addObject(\"ObjectName\", own, 0)\n"
     "$0\n"),
    ("NEAREST", "Nearest Object With Property", "Loop over the scene objects",
     "scene = logic.getCurrentScene()\n"
     "nearest = None\n"
     "for ob in scene.objects:\n"
     "    if \"enemy\" in ob and (nearest is None or own.getDistanceTo(ob) < own.getDistanceTo(nearest)):\n"
     "        nearest = ob\n"
     "$0\n"),
    ("MESSAGE", "Send Message", "Message read by Message sensors (subject) of other objects",
     "logic.sendMessage(\"subject\", \"body\")\n"
     "$0\n"),
    ("TIMER", "Timer", "Wait some seconds using the frame time",
     "own[\"timer\"] = own.get(\"timer\", 0.0) + logic.getFrameTime() - own.get(\"last\", logic.getFrameTime())\n"
     "own[\"last\"] = logic.getFrameTime()\n"
     "if own[\"timer\"] >= 2.0:\n"
     "    own[\"timer\"] = 0.0\n"
     "    $0\n"),
    ("CLASS", "Class", "A plain Python class",
     "class Name:\n"
     "    def __init__(self):\n"
     "        $0\n"),
    ("MAIN", "if __name__ == \"__main__\"", "Code that only runs when the script is run directly",
     "if __name__ == \"__main__\":\n"
     "    $0\n"),
)


def _snippet_items(self, context):
    return [(key, name, desc) for key, name, desc, _ in SNIPPETS]


class TEXT_OT_insert_snippet(bpy.types.Operator):
    """Type a ready-made piece of game code at the cursor"""
    bl_idname = "text.insert_snippet"
    bl_label = "Insert Snippet"
    # no UNDO here: the text.insert inside is the undo step (one Ctrl+Z removes the snippet)

    snippet = bpy.props.EnumProperty(name="Snippet", items=_snippet_items)

    @classmethod
    def poll(cls, context):
        text = getattr(context, "edit_text", None)
        return text is not None and not text.library

    def execute(self, context):
        text = context.edit_text
        if text.current_line != text.select_end_line or text.current_character != text.select_end_character:
            # a selection is replaced: remove it first, so indent and cursor come from where it was
            bpy.ops.text.delete(type='PREVIOUS_CHARACTER')
        body = next((s[3] for s in SNIPPETS if s[0] == self.snippet), None)
        if body is None:
            return {'CANCELLED'}
        line = text.current_line.body
        indent = re.match(r"[ \t]*", line).group()
        before_cursor = line[:len(line.encode("utf-8")[:text.current_character].decode("utf-8", "ignore"))]
        if before_cursor.strip():
            # in the middle of a line: the snippet starts on the next one
            body = "\n" + body
        else:
            indent = before_cursor
        uses_tabs = not text.use_tabs_as_spaces and "\t" in indent + "".join(
            l.body[:1] for l in text.lines[:200])

        def fix(l):
            if uses_tabs:
                spaces = len(l) - len(l.lstrip(" "))
                l = "\t" * (spaces // 4) + " " * (spaces % 4) + l.lstrip(" ")
            return l
        lines = [fix(l) for l in body.split("\n")]
        # the first line goes where the cursor is (already indented); the others get the indent
        lines = [lines[0]] + [(indent + l) if l else "" for l in lines[1:]]
        if lines and lines[-1] == "":
            lines.pop()  # no trailing empty line after the snippet
        full = "\n".join(lines)
        marker = full.find("$0")
        tail = 0
        if marker >= 0:
            tail = len(full) - marker - 2
            full = full.replace("$0", "", 1)
        st = context.space_data
        overwrite = getattr(st, "use_overwrite", False)
        if overwrite:
            st.use_overwrite = False
        bpy.ops.text.insert(text=full)
        if overwrite:
            st.use_overwrite = True
        for _ in range(tail):
            bpy.ops.text.move(type='PREVIOUS_CHARACTER')
        return {'FINISHED'}


class TEXT_MT_snippets(bpy.types.Menu):
    bl_label = "Insert Snippet"

    def draw(self, context):
        layout = self.layout
        layout.operator_context = 'EXEC_DEFAULT'
        for key, name, desc, _ in SNIPPETS:
            layout.operator("text.insert_snippet", text=name).snippet = key


# TEXT_PT_outline is registered by bl_ui/space_text.py (first panel of the Text tab)
classes = (TEXT_OT_insert_snippet, TEXT_MT_snippets)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
