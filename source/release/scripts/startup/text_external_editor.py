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


def _is_vscode(editor):
    return os.path.basename(editor).lower().startswith(("code", "codium"))


def _command(editor, filepath, line, folder=None):
    """{file} and {line} in the path are replaced; else VS Code family opens at the line (with the
    project folder, so the typings/ there give the game API hints)."""
    if "{file}" in editor:
        parts = shlex.split(editor, posix=(os.name != "nt"))
        parts = [p[1:-1] if len(p) > 1 and p[0] == p[-1] == '"' else p for p in parts]
        return [p.replace("{file}", filepath).replace("{line}", str(line)) for p in parts]
    if _is_vscode(editor):
        return [editor] + ([folder] if folder else []) + ["-g", "%s:%d" % (filepath, line)]
    return [editor, filepath]


# -- game API hints for VS Code --------------------------------------------------------
# The .pyi stubs of bge/mathutils/aud/bgl/blf (scripts/stubs, made by tools/autocomplete/
# gerar_stubs.py) are copied to <project>/typings, the folder Pylance reads by default.

STUBS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "stubs")
MARK = "ANASTACIO_STUBS.txt"  # our copy (other typings of the person are never touched)


def project_folder(filepath=None):
    """Folder of the .range (else of the script): where typings/ goes and VS Code opens."""
    if bpy.data.filepath:
        return os.path.dirname(os.path.abspath(bpy.data.filepath))
    if filepath:
        return os.path.dirname(filepath)
    return None


def install_stubs(folder):
    """Copies the stubs to folder/typings. (installed, message)."""
    if not folder or not os.path.isdir(STUBS):
        return False, "No project folder (save the .range first)"
    dest = os.path.join(folder, "typings")
    mark = os.path.join(dest, MARK)
    try:
        with open(os.path.join(STUBS, "VERSION.txt"), encoding="utf-8") as f:
            version = f.read()
    except OSError:
        version = ""
    ours = sorted(os.listdir(STUBS))
    if os.path.isfile(mark):
        try:
            with open(mark, encoding="utf-8") as f:
                if f.read() == version:
                    return True, "VS Code hints are up to date"
        except OSError:
            pass
    elif any(os.path.exists(os.path.join(dest, n)) for n in ours if n != "VERSION.txt"):
        return False, "typings/ already has a bge or mathutils that is not ours: left as it is"
    try:
        os.makedirs(dest, exist_ok=True)
        for name in ours:
            if name == "VERSION.txt":
                continue
            src, dst = os.path.join(STUBS, name), os.path.join(dest, name)
            if os.path.isdir(src):
                # file by file over the old copy: nothing else in the folder is removed
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copyfile(src, dst)
        with open(mark, "w", encoding="utf-8") as f:
            f.write(version)
    except OSError as ex:
        return False, "Could not write typings/: %s" % ex
    return True, "VS Code hints for the game API copied to %s" % dest


class TEXT_OT_install_vscode_stubs(bpy.types.Operator):
    """Copy the game API hints (bge, mathutils...) to typings/ in the project folder, so VS Code
    completes and checks them (done by itself by Open in External Editor with VS Code)"""
    bl_idname = "text.install_vscode_stubs"
    bl_label = "Set Up VS Code Hints"

    def execute(self, context):
        text = getattr(context, "edit_text", None)
        path = bpy.path.abspath(text.filepath) if text and text.filepath else None
        ok, message = install_stubs(project_folder(path))
        self.report({'INFO'} if ok else {'WARNING'}, message)
        return {'FINISHED'} if ok else {'CANCELLED'}


def open_file(filepath, line=1):
    """Opens a file in the configured editor (or VS Code, or the system default). Error text or None."""
    editor = _find_editor()
    try:
        if editor:
            folder = None
            if _is_vscode(editor) and "{file}" not in editor:
                folder = project_folder(filepath)
                ok, message = install_stubs(folder)
                if not ok:
                    print("External editor:", message)
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # code.cmd without a console
            subprocess.Popen(_command(editor, filepath, line, folder), creationflags=flags)
        elif os.name == "nt":
            os.startfile(filepath)
        else:
            subprocess.Popen(["xdg-open", filepath])
    except Exception as ex:
        return str(ex)
    return None


_RESERVED = {"CON", "PRN", "AUX", "NUL"} | {"COM%d" % i for i in range(1, 10)} | {"LPT%d" % i for i in range(1, 10)}


def _text_file_name(text):
    """<text name>.py with only safe characters (Windows reserved names get a '_')."""
    base = text.name[:-3] if text.name.lower().endswith(".py") else text.name
    base = bpy.path.clean_name(base, replace="_").strip(" .") or "script"
    if base.upper() in _RESERVED:
        base += "_"
    return base + ".py"


def _default_text_path(text):
    """<.range folder>/<text name>.py, or None while the .range is not saved."""
    if not bpy.data.filepath:
        return None
    return os.path.join(os.path.dirname(os.path.abspath(bpy.data.filepath)), _text_file_name(text))


def _save_text(text, path):
    """Save As to path; True only if the file is really on disk (save_as reports FINISHED even
    when writing fails)."""
    ok = 'FINISHED' in bpy.ops.text.save_as(filepath=path, check_existing=False)
    return ok and not text.is_in_memory and os.path.isfile(path)


class TEXT_OT_save_as_open_external(bpy.types.Operator):
    """Save the text to a file, then open it in the external editor"""
    bl_idname = "text.save_as_open_external"
    bl_label = "Save and Open in External Editor"
    bl_options = {'INTERNAL'}

    filepath = bpy.props.StringProperty(subtype='FILE_PATH')
    text_name = bpy.props.StringProperty(options={'HIDDEN'})
    check_existing = bpy.props.BoolProperty(default=True, options={'HIDDEN'})
    filter_text = bpy.props.BoolProperty(default=True, options={'HIDDEN'})
    filter_python = bpy.props.BoolProperty(default=True, options={'HIDDEN'})
    filter_folder = bpy.props.BoolProperty(default=True, options={'HIDDEN'})

    @classmethod
    def poll(cls, context):
        return getattr(context, "edit_text", None) is not None

    def invoke(self, context, event):
        text = context.edit_text
        self.text_name = text.name
        if not self.filepath:
            folder = os.path.dirname(os.path.abspath(bpy.data.filepath)) if bpy.data.filepath else ""
            self.filepath = os.path.join(folder, _text_file_name(text)) if folder else _text_file_name(text)
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        text = context.edit_text
        if self.text_name and text.name != self.text_name:
            self.report({'ERROR'}, "The text changed while choosing the file; nothing was saved")
            return {'CANCELLED'}
        if not _save_text(text, self.filepath):
            self.report({'ERROR'}, "Could not save the text to %s" % self.filepath)
            return {'CANCELLED'}
        return bpy.ops.text.open_external()


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
            # The editor only opens files: save the text next to the .range and go on.
            path = _default_text_path(text)
            if path and not os.path.lexists(path):
                if _save_text(text, path):
                    self.report({'INFO'}, "Saved as %s" % path)
                    return self.execute(context)
                self.report({'WARNING'}, "Could not save the text to %s, choose another place" % path)
            # No .range saved yet, name taken or save failed: ask where; it opens right after.
            else:
                self.report({'INFO'}, "Choose where to save the script; it opens in the editor next")
            bpy.ops.text.save_as_open_external('INVOKE_DEFAULT')
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
    bpy.utils.register_class(TEXT_OT_save_as_open_external)
    bpy.utils.register_class(TEXT_OT_install_vscode_stubs)


def unregister():
    bpy.utils.unregister_class(TEXT_OT_install_vscode_stubs)
    bpy.utils.unregister_class(TEXT_OT_save_as_open_external)
    bpy.utils.unregister_class(TEXT_OT_open_external)
    del bpy.types.WindowManager.range_external_editor
