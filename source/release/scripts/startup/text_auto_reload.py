# Auto reload of scripts edited outside the engine (VS Code etc.).
# A Text linked to a file is reloaded when the file is saved on disk, unless the Text was also
# edited here since it was last read: then the Text Editor's own "Resolve Conflict" bar decides.

import hashlib
import os
import time

import bpy
from bpy.app.handlers import persistent

CHECK_SECONDS = 0.5
_state = {"next": 0.0}
_base = {}  # text.as_pointer() -> hash of the code last read from (or matching) the file


def _hash(source):
    return hashlib.md5(source.encode("utf-8", "surrogatepass")).hexdigest()


def _check_text(text):
    if text.library or text.is_in_memory or not text.filepath:
        return False
    key = text.as_pointer()
    if not text.is_modified:
        # Clean = same as the file: that is the base. Dirty = edited here: no base, never reloaded.
        if text.is_dirty:
            _base.pop(key, None)
        else:
            _base[key] = _hash(text.as_string())
        return False
    if not os.path.isfile(bpy.path.abspath(text.filepath)):
        return False  # deleted/renamed: left to Resolve Conflict
    base = _base.get(key)
    if base is None:
        if text.is_dirty:
            return False  # edited here before we knew it: do not lose that
    elif _hash(text.as_string()) != base:
        return False  # edited here: do not overwrite
    if not text.reload():
        return False
    _base[key] = _hash(text.as_string())
    return True


def check_texts():
    reloaded = []
    for text in bpy.data.texts:
        try:
            if _check_text(text):
                reloaded.append(text.name)
        except Exception as ex:  # one bad Text must not stop the others
            print('Text auto reload "%s": %s' % (text.name, ex))
    for name in reloaded:
        print('Text "%s" reloaded from disk' % name)
    return reloaded


@persistent
def _scene_update_post(scene):
    now = time.monotonic()
    if now < _state["next"]:
        return
    _state["next"] = now + CHECK_SECONDS
    if bpy.app.background or not getattr(scene, "range_text_auto_reload", True):
        return
    check_texts()


@persistent
def _load_post(_dummy):
    _base.clear()  # pointers of the old file are gone


def register():
    bpy.types.Scene.range_text_auto_reload = bpy.props.BoolProperty(
        name="Auto Reload from Disk",
        description="Reload scripts saved by an external editor (VS Code etc.) automatically, "
                    "unless they were also edited here",
        default=True)
    if _scene_update_post not in bpy.app.handlers.scene_update_post:
        bpy.app.handlers.scene_update_post.append(_scene_update_post)
    if _load_post not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_load_post)


def unregister():
    if _scene_update_post in bpy.app.handlers.scene_update_post:
        bpy.app.handlers.scene_update_post.remove(_scene_update_post)
    if _load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_load_post)
    del bpy.types.Scene.range_text_auto_reload
