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

# <pep8 compliant>

import bpy
from bpy.types import Operator
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    StringProperty,
)

# ########## Datablock previews... ##########


class WM_OT_previews_batch_generate(Operator):
    """Generate selected .blend file's previews"""
    bl_idname = "wm.previews_batch_generate"
    bl_label = "Batch-Generate Previews"
    bl_options = {'REGISTER'}

    # -----------
    # File props.
    files: CollectionProperty(
        type=bpy.types.OperatorFileListElement,
        options={'HIDDEN', 'SKIP_SAVE'},
    )

    directory: StringProperty(
        maxlen=1024,
        subtype='FILE_PATH',
        options={'HIDDEN', 'SKIP_SAVE'},
    )

    # Show only images/videos, and directories!
    filter_blender: BoolProperty(
        default=True,
        options={'HIDDEN', 'SKIP_SAVE'},
    )
    filter_folder: BoolProperty(
        default=True,
        options={'HIDDEN', 'SKIP_SAVE'},
    )

    # -----------
    # Own props.
    use_scenes: BoolProperty(
        default=True,
        name="Scenes",
        description="Generate scenes' previews",
    )
    use_groups: BoolProperty(
        default=True,
        name="Groups",
        description="Generate groups' previews",
    )
    use_objects: BoolProperty(
        default=True,
        name="Objects",
        description="Generate objects' previews",
    )
    use_intern_data: BoolProperty(
        default=True,
        name="Mat/Tex/...",
        description="Generate 'internal' previews (materials, textures, images, etc.)",
    )

    use_trusted: BoolProperty(
        default=False,
        name="Trusted Blend Files",
        description="Enable python evaluation for selected files",
    )
    use_backups: BoolProperty(
        default=True,
        name="Save Backups",
        description="Keep a backup (.blend1) version of the files when saving with generated previews",
    )

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        import os
        import subprocess
        from bl_previews_utils import bl_previews_render as preview_render

        context.window_manager.progress_begin(0, len(self.files))
        context.window_manager.progress_update(0)
        for i, fn in enumerate(self.files):
            blen_path = os.path.join(self.directory, fn.name)
            cmd = [
                bpy.app.binary_path,
                "--background",
                "--factory-startup",
                "-noaudio",
            ]
            if self.use_trusted:
                cmd.append("--enable-autoexec")
            cmd.extend([
                blen_path,
                "--python",
                os.path.join(os.path.dirname(preview_render.__file__), "bl_previews_render.py"),
                "--",
            ])
            if not self.use_scenes:
                cmd.append('--no_scenes')
            if not self.use_groups:
                cmd.append('--no_groups')
            if not self.use_objects:
                cmd.append('--no_objects')
            if not self.use_intern_data:
                cmd.append('--no_data_intern')
            if not self.use_backups:
                cmd.append("--no_backups")
            if subprocess.call(cmd):
                self.report({'ERROR'}, "Previews generation process failed for file '%s'!" % blen_path)
                context.window_manager.progress_end()
                return {'CANCELLED'}
            context.window_manager.progress_update(i + 1)
        context.window_manager.progress_end()

        return {'FINISHED'}


class WM_OT_previews_batch_clear(Operator):
    """Clear selected .blend file's previews"""
    bl_idname = "wm.previews_batch_clear"
    bl_label = "Batch-Clear Previews"
    bl_options = {'REGISTER'}

    # -----------
    # File props.
    files: CollectionProperty(
        type=bpy.types.OperatorFileListElement,
        options={'HIDDEN', 'SKIP_SAVE'},
    )

    directory: StringProperty(
        maxlen=1024,
        subtype='FILE_PATH',
        options={'HIDDEN', 'SKIP_SAVE'},
    )

    # Show only images/videos, and directories!
    filter_blender: BoolProperty(
        default=True,
        options={'HIDDEN', 'SKIP_SAVE'},
    )
    filter_folder: BoolProperty(
        default=True,
        options={'HIDDEN', 'SKIP_SAVE'},
    )

    # -----------
    # Own props.
    use_scenes: BoolProperty(
        default=True,
        name="Scenes",
        description="Clear scenes' previews",
    )
    use_groups: BoolProperty(default=True,
                              name="Groups",
                              description="Clear groups' previews",
                              )
    use_objects: BoolProperty(
        default=True,
        name="Objects",
        description="Clear objects' previews",
    )
    use_intern_data: BoolProperty(
        default=True,
        name="Mat/Tex/...",
        description="Clear 'internal' previews (materials, textures, images, etc.)",
    )

    use_trusted: BoolProperty(
        default=False,
        name="Trusted Blend Files",
        description="Enable python evaluation for selected files",
    )
    use_backups: BoolProperty(
        default=True,
        name="Save Backups",
        description="Keep a backup (.blend1) version of the files when saving with cleared previews",
    )

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        import os
        import subprocess
        from bl_previews_utils import bl_previews_render as preview_render

        context.window_manager.progress_begin(0, len(self.files))
        context.window_manager.progress_update(0)
        for i, fn in enumerate(self.files):
            blen_path = os.path.join(self.directory, fn.name)
            cmd = [
                bpy.app.binary_path,
                "--background",
                "--factory-startup",
                "-noaudio",
            ]
            if self.use_trusted:
                cmd.append("--enable-autoexec")
            cmd.extend([
                blen_path,
                "--python",
                os.path.join(os.path.dirname(preview_render.__file__), "bl_previews_render.py"),
                "--",
                "--clear",
            ])
            if not self.use_scenes:
                cmd.append('--no_scenes')
            if not self.use_groups:
                cmd.append('--no_groups')
            if not self.use_objects:
                cmd.append('--no_objects')
            if not self.use_intern_data:
                cmd.append('--no_data_intern')
            if not self.use_backups:
                cmd.append("--no_backups")
            if subprocess.call(cmd):
                self.report({'ERROR'}, "Previews clear process failed for file '%s'!" % blen_path)
                context.window_manager.progress_end()
                return {'CANCELLED'}
            context.window_manager.progress_update(i + 1)
        context.window_manager.progress_end()

        return {'FINISHED'}


class WM_OT_blend_strings_utf8_validate(Operator):
    """Check and fix all strings in current .blend file to be valid UTF-8 Unicode (needed for some old, 2.4x area files)"""
    bl_idname = "wm.blend_strings_utf8_validate"
    bl_label = "Validate .blend strings"
    bl_options = {'REGISTER'}

    def validate_strings(self, item, done_items):
        if item is None:
            return False

        if item in done_items:
            return False
        done_items.add(item)

        if getattr(item, 'library', None) is not None:
            return False  # No point in checking library data, we cannot fix it anyway...

        changed = False
        for prop in item.bl_rna.properties:
            if prop.identifier in {'bl_rna', 'rna_type'}:
                continue  # Or we'd recurse 'till Hell freezes.
            if prop.is_readonly:
                continue
            if prop.type == 'STRING':
                val_bytes = item.path_resolve(prop.identifier, False).as_bytes()
                val_utf8 = val_bytes.decode('utf-8', 'replace')
                val_bytes_valid = val_utf8.encode('utf-8')
                if val_bytes_valid != val_bytes:
                    print("found bad utf8 encoded string %r, fixing to %r (%r)..."
                          "" % (val_bytes, val_bytes_valid, val_utf8))
                    setattr(item, prop.identifier, val_utf8)
                    changed = True
            elif prop.type == 'POINTER':
                it = getattr(item, prop.identifier)
                changed |= self.validate_strings(it, done_items)
            elif prop.type == 'COLLECTION':
                for it in getattr(item, prop.identifier):
                    changed |= self.validate_strings(it, done_items)
        return changed

    def execute(self, context):
        changed = False
        done_items = set()
        for prop in bpy.data.bl_rna.properties:
            if prop.type == 'COLLECTION':
                for it in getattr(bpy.data, prop.identifier):
                    changed |= self.validate_strings(it, done_items)
        if changed:
            self.report({'WARNING'},
                        "Some strings were fixed, don't forget to save the .blend file to keep those changes")
        return {'FINISHED'}


class FILE_OT_asset_previews_generate(Operator):
    """Generate previews for the assets of every .blend file of the current asset library folder"""
    bl_idname = "file.asset_previews_generate"
    bl_label = "Generate Asset Previews"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        space = context.space_data
        return (space and space.type == 'FILE_BROWSER' and
                space.browse_mode == 'ASSETS' and space.params)

    @staticmethod
    def library_folder(directory):
        import os
        # Browsing inside a .blend file: the library is the folder holding it.
        path = os.path.normpath(bpy.path.abspath(directory))
        while path and not os.path.isdir(path):
            parent = os.path.dirname(path)
            if parent == path:
                return ""
            path = parent
        return path

    def execute(self, context):
        import os
        space = context.space_data
        folder = self.library_folder(space.params.directory)
        if not folder:
            self.report({'ERROR'}, "Asset library folder not found")
            return {'CANCELLED'}

        current = os.path.normcase(os.path.normpath(bpy.data.filepath)) if bpy.data.filepath else ""
        files = [{"name": fn} for fn in sorted(os.listdir(folder))
                 if fn.lower().endswith(".blend") and
                 os.path.normcase(os.path.join(folder, fn)) != current]
        if not files:
            self.report({'WARNING'}, "No .blend file in '%s'" % folder)
            return {'CANCELLED'}

        ret = bpy.ops.wm.previews_batch_generate(
            'EXEC_DEFAULT', files=files, directory=folder + os.sep,
            use_scenes=False, use_backups=False,
        )
        if 'FINISHED' not in ret:
            return {'CANCELLED'}
        for f in files:
            _AssetPreviewsAuto.mark_done(os.path.join(folder, f["name"]))

        if bpy.ops.file.refresh.poll():
            bpy.ops.file.refresh()
        self.report({'INFO'}, "Previews generated for %d file(s)" % len(files))
        return {'FINISHED'}


class _AssetPreviewsAuto:
    """Generates the previews of the asset libraries in the background.

    Every open Asset Browser is checked a few times per second of UI activity.
    A .blend never generated, or changed after the last generation, gets a
    background process (the same script as wm.previews_batch_generate), one
    file at a time. The modification time after the generation (the script
    saves the file) is kept in asset_previews.json in the user config folder,
    together with the on/off toggle, so it survives restarts.
    """

    INTERVAL = 2.0
    _data = None
    _proc = None
    _proc_file = ""
    _queue = []
    _last = 0.0

    @classmethod
    def _json_path(cls):
        import os
        folder = bpy.utils.user_resource('CONFIG', create=True)
        return os.path.join(folder, "asset_previews.json")

    @classmethod
    def data(cls):
        if cls._data is None:
            import json
            try:
                with open(cls._json_path(), encoding="utf-8") as fh:
                    cls._data = json.load(fh)
            except (OSError, ValueError):
                cls._data = {}
            cls._data.setdefault("auto", True)
            cls._data.setdefault("files", {})
        return cls._data

    @classmethod
    def save(cls):
        import json
        try:
            with open(cls._json_path(), "w", encoding="utf-8") as fh:
                json.dump(cls.data(), fh, indent=1)
        except OSError:
            pass

    @classmethod
    def enabled(cls):
        return bool(cls.data()["auto"])

    @classmethod
    def set_enabled(cls, value):
        cls.data()["auto"] = bool(value)
        cls.save()

    @staticmethod
    def _key(path):
        import os
        return os.path.normcase(os.path.abspath(path))

    @classmethod
    def mark_done(cls, path):
        import os
        try:
            cls.data()["files"][cls._key(path)] = os.path.getmtime(path)
        except OSError:
            return
        cls.save()

    @classmethod
    def _stale(cls, folder):
        import os
        current = cls._key(bpy.data.filepath) if bpy.data.filepath else ""
        done = cls.data()["files"]
        try:
            names = sorted(os.listdir(folder))
        except OSError:
            return []
        stale = []
        for fn in names:
            if not fn.lower().endswith(".blend"):
                continue
            path = os.path.join(folder, fn)
            key = cls._key(path)
            if key == current or path in cls._queue or path == cls._proc_file:
                continue
            try:
                mtime = os.path.getmtime(path)
            except OSError:
                continue
            if done.get(key) != mtime:
                stale.append(path)
        return stale

    @classmethod
    def _start(cls, path):
        import os
        import subprocess
        from bl_previews_utils import bl_previews_render as preview_render
        cmd = [
            bpy.app.binary_path, "--background", "--factory-startup", "-noaudio",
            path, "--python",
            os.path.join(os.path.dirname(preview_render.__file__), "bl_previews_render.py"),
            "--", "--no_scenes", "--no_backups",
        ]
        try:
            cls._proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            cls._proc_file = path
        except OSError:
            cls._proc = None
            cls._proc_file = ""

    @classmethod
    def _refresh_browsers(cls):
        wm = bpy.context.window_manager
        for win in wm.windows:
            for area in win.screen.areas:
                if area.type != 'FILE_BROWSER':
                    continue
                space = area.spaces.active
                if not _is_asset_browser_space(space):
                    continue
                region = next((r for r in area.regions if r.type == 'WINDOW'), None)
                if region is None:
                    continue
                override = {"window": win, "screen": win.screen, "area": area, "region": region}
                try:
                    bpy.ops.file.refresh(override)
                except RuntimeError:
                    pass
                area.tag_redraw()

    @classmethod
    def tick(cls):
        import time
        if cls._proc is not None:
            if cls._proc.poll() is None:
                return
            if cls._proc.returncode == 0:
                cls.mark_done(cls._proc_file)
            else:
                # Do not retry a broken file until it changes again.
                cls.mark_done(cls._proc_file)
                print("Asset previews: generation failed for %r" % cls._proc_file)
            cls._proc = None
            cls._proc_file = ""
            if not cls._queue:
                cls._refresh_browsers()
        if cls._queue:
            cls._start(cls._queue.pop(0))
            return

        now = time.monotonic()
        if now - cls._last < cls.INTERVAL:
            return
        cls._last = now
        if not cls.enabled():
            return
        wm = bpy.context.window_manager
        if wm is None:
            return
        folders = set()
        for win in wm.windows:
            for area in win.screen.areas:
                if area.type == 'FILE_BROWSER':
                    space = area.spaces.active
                    if _is_asset_browser_space(space) and space.params:
                        folder = FILE_OT_asset_previews_generate.library_folder(space.params.directory)
                        if folder:
                            folders.add(folder)
        for folder in sorted(folders):
            cls._queue.extend(cls._stale(folder))
        if cls._queue:
            cls._start(cls._queue.pop(0))


def _is_asset_browser_space(space):
    return (space is not None and getattr(space, "browse_mode", None) == 'ASSETS' and
            space.active_operator is None)


@bpy.app.handlers.persistent
def _asset_previews_auto_handler(scene):
    if bpy.app.background:
        return
    try:
        _AssetPreviewsAuto.tick()
    except Exception as ex:
        print("Asset previews:", ex)


def _asset_previews_auto_register():
    handlers = bpy.app.handlers.scene_update_post
    for fn in list(handlers):
        if getattr(fn, "__name__", "") == _asset_previews_auto_handler.__name__:
            handlers.remove(fn)
    handlers.append(_asset_previews_auto_handler)


def _asset_previews_auto_get(self):
    return _AssetPreviewsAuto.enabled()


def _asset_previews_auto_set(self, value):
    _AssetPreviewsAuto.set_enabled(value)


bpy.types.WindowManager.asset_previews_auto = bpy.props.BoolProperty(
    name="Auto Previews",
    description="Generate the previews of new or changed .blend files of the asset "
                "library in the background",
    get=_asset_previews_auto_get,
    set=_asset_previews_auto_set,
)
_asset_previews_auto_register()


class FILE_OT_asset_library_browse(Operator):
    """Choose a folder in a file selector and add it as an asset library"""
    bl_idname = "file.asset_library_browse"
    bl_label = "Add Library Folder"
    bl_options = {'REGISTER'}

    directory: StringProperty(
        maxlen=1024,
        subtype='DIR_PATH',
        options={'HIDDEN', 'SKIP_SAVE'},
    )
    filter_folder: BoolProperty(
        default=True,
        options={'HIDDEN', 'SKIP_SAVE'},
    )

    @classmethod
    def poll(cls, context):
        space = context.space_data
        return (space and space.type == 'FILE_BROWSER' and
                space.browse_mode == 'ASSETS' and space.active_operator is None)

    def invoke(self, context, event):
        # The selector takes over this File Browser area (maximized) and gives it
        # back in Assets mode when it closes.
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        if not self.directory:
            return {'CANCELLED'}
        return bpy.ops.file.asset_library_add(directory=self.directory)


class WM_OT_asset_texts_import(Operator):
    """Copy the scripts (Texts) of the file an asset came from; names already in this file are kept"""
    bl_idname = "wm.asset_texts_import"
    bl_label = "Copy Scripts"
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    filepath: StringProperty(
        subtype='FILE_PATH',
        options={'HIDDEN', 'SKIP_SAVE'},
    )

    def _names(self):
        # Opening the library without assigning to data_to only reads the names.
        with bpy.data.libraries.load(self.filepath) as (data_from, data_to):
            names = list(data_from.texts)
        missing = [n for n in names if n not in bpy.data.texts]
        existing = [n for n in names if n in bpy.data.texts]
        return missing, existing

    def execute(self, context):
        try:
            missing, existing = self._names()
        except OSError:
            return {'CANCELLED'}
        if not missing:
            return {'CANCELLED'}
        for name in missing:
            bpy.ops.wm.import_libload_text(filepath=self.filepath, text=name)
        msg = "Copied scripts: " + ", ".join(missing)
        if existing:
            msg += " (already in the project: " + ", ".join(existing) + ")"
        self.report({'INFO'}, msg)
        return {'FINISHED'}


classes = (
    WM_OT_asset_texts_import,
    FILE_OT_asset_library_browse,
    FILE_OT_asset_previews_generate,
    WM_OT_previews_batch_clear,
    WM_OT_previews_batch_generate,
    WM_OT_blend_strings_utf8_validate,
)
