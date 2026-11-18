# "Open in External Editor": opens the script of the Text Editor in VS Code (or any editor whose
# path is set in the Text Editor sidebar > Editor). The path is kept in the user config folder, so
# it is the same for every .range. With Auto Reload from Disk (text_auto_reload.py) the changes come
# back by themselves.

import os
import shlex
import shutil
import subprocess

import bpy

_cache = {"path": None}


def _config_file():
    return os.path.join(bpy.utils.user_resource('CONFIG', create=True), "anastacio_external_editor.txt")


def editor_path():
    if _cache["path"] is None:
        try:
            with open(_config_file(), encoding="utf-8") as f:
                _cache["path"] = f.read().strip()
        except OSError:
            _cache["path"] = ""
    return _cache["path"]


def _get(_self):
    return editor_path()


def _set(_self, value):
    value = value.strip()
    if value.count('"') == 2 and value[0] == value[-1] == '"':
        value = value[1:-1]  # "C:\path with spaces\editor.exe" pasted with quotes
    _cache["path"] = value
    try:
        with open(_config_file(), "w", encoding="utf-8") as f:
            f.write(value)
    except OSError as ex:
        print("External editor: could not save the path:", ex)


def _find_editor():
    path = editor_path()
    if path:
        return path
    for name in ("code", "code-insiders", "codium"):  # VS Code family on PATH
        found = shutil.which(name)
        if found:
            return found
    if os.name == "nt":
        local = os.environ.get("LOCALAPPDATA", "")
        guess = os.path.join(local, "Programs", "Microsoft VS Code", "Code.exe")
        if os.path.isfile(guess):
            return guess
    return ""


def _command(editor, filepath, line):
    """{file} and {line} in the path are replaced; else VS Code family opens at the line."""
    if "{file}" in editor:
        parts = shlex.split(editor, posix=(os.name != "nt"))
        parts = [p[1:-1] if len(p) > 1 and p[0] == p[-1] == '"' else p for p in parts]
        return [p.replace("{file}", filepath).replace("{line}", str(line)) for p in parts]
    base = os.path.basename(editor).lower()
    if base.startswith(("code", "codium")):
        return [editor, "-g", "%s:%d" % (filepath, line)]
    return [editor, filepath]


def open_file(filepath, line=1):
    """Opens a file in the configured editor (or VS Code, or the system default). Error text or None."""
    editor = _find_editor()
    try:
        if editor:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # code.cmd without a console
            subprocess.Popen(_command(editor, filepath, line), creationflags=flags)
        elif os.name == "nt":
            os.startfile(filepath)
        else:
            subprocess.Popen(["xdg-open", filepath])
    except Exception as ex:
        return str(ex)
    return None


class TEXT_OT_open_external(bpy.types.Operator):
    """Open this script in the external editor (VS Code etc.); saved changes reload by themselves"""
    bl_idname = "text.open_external"
    bl_label = "Open in External Editor"

    @classmethod
    def poll(cls, context):
        return getattr(context, "edit_text", None) is not None

    def invoke(self, context, event):
        text = context.edit_text
        if text.is_in_memory or not text.filepath:
            self.report({'WARNING'}, "Save the text to a file first (Text > Save As)")
            bpy.ops.text.save_as('INVOKE_DEFAULT')
            return {'CANCELLED'}
        return self.execute(context)

    def execute(self, context):
        text = context.edit_text
        if text.is_in_memory or not text.filepath:
            self.report({'ERROR'}, "Text is not saved to a file")
            return {'CANCELLED'}
        if text.is_dirty and text.is_modified:
            self.report({'WARNING'}, "Changed here and on disk: use Resolve Conflict first")
            return {'CANCELLED'}
        if text.is_dirty:
            # The editor must see what is here now.
            if 'FINISHED' not in bpy.ops.text.save() or text.is_dirty:
                self.report({'ERROR'}, "Could not save the text")
                return {'CANCELLED'}
        filepath = os.path.normpath(bpy.path.abspath(text.filepath))
        error = open_file(filepath, text.current_line_index + 1)
        if error:
            self.report({'ERROR'}, "Could not open the editor: %s" % error)
            return {'CANCELLED'}
        return {'FINISHED'}


def register():
    bpy.types.WindowManager.range_external_editor = bpy.props.StringProperty(
        name="External Editor",
        description="Program used by Open in External Editor (empty = VS Code if found, "
                    "else the system default). {file} and {line} can be used as arguments",
        subtype='FILE_PATH', get=_get, set=_set)
    bpy.utils.register_class(TEXT_OT_open_external)


def unregister():
    bpy.utils.unregister_class(TEXT_OT_open_external)
    del bpy.types.WindowManager.range_external_editor
