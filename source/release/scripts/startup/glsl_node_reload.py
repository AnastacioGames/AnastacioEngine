# Nodes GLSL from the library (Add > GLSL Library) keep the path of their .glsl in
# text["glsl_node_file"]. When that file is saved outside the engine, the Text is updated and the
# nodes that use it are rebuilt (sockets and shader). A Text edited inside the engine is not
# overwritten: its code no longer matches the hash of the last version read from the file.

import hashlib
import os
import time

import bpy
from bpy.app.handlers import persistent

CHECK_SECONDS = 1.0
_state = {"next": 0.0}


def source_hash(source):
    return hashlib.md5(source.encode("utf-8")).hexdigest()


def mark_text(text, path, source):
    """Called when a Text is made from a library file: what it was read from, and when."""
    try:
        text["glsl_node_mtime"] = os.path.getmtime(path)
    except OSError:
        text["glsl_node_mtime"] = 0.0
    text["glsl_node_hash"] = source_hash(source)


def _rebuild_nodes(text):
    trees = [m.node_tree for m in bpy.data.materials if m.node_tree] + list(bpy.data.node_groups)
    for tree in trees:
        if tree.library:
            continue
        uses = False
        for node in tree.nodes:
            if node.bl_idname == "ShaderNodeGLSLScript" and node.script == text:
                node.script = text  # tags the node: the update re-reads the code
                uses = True
        if uses:
            # Sockets now and a new shader (same as node.glsl_node_add).
            tree.interface_update(bpy.context)


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except (OSError, UnicodeDecodeError):
        return None


def _check_text(text):
    """True when the Text was reloaded from its file."""
    path = text.get("glsl_node_file")
    if not path or text.library:
        return False
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return False
    if "glsl_node_hash" not in text:
        # Made before this check existed. Same code as the file: it is the starting point. Otherwise
        # it may have been edited here: keep the file's hash so it counts as edited.
        source = _read(path)
        if source is not None:
            text["glsl_node_hash"] = source_hash(source)
            text["glsl_node_mtime"] = mtime
        return False
    if mtime == text.get("glsl_node_mtime", 0.0):
        return False
    if source_hash(text.as_string()) != text["glsl_node_hash"]:
        text["glsl_node_mtime"] = mtime  # said once per save
        print('GLSL node "%s": %s changed on disk, but the Text was edited here; not reloaded'
              % (text.name, os.path.basename(path)))
        return False
    source = _read(path)
    if source is None:
        return False  # tried again on the next check (file being written, locked...)
    text["glsl_node_mtime"] = mtime
    if source == text.as_string():
        return False
    text.from_string(source)
    text["glsl_node_hash"] = source_hash(source)
    _rebuild_nodes(text)
    return True


def check_texts():
    reloaded = []
    for text in bpy.data.texts:
        try:
            if _check_text(text):
                reloaded.append(text.name)
        except Exception as ex:  # one bad Text must not stop the others
            print('GLSL node reload "%s": %s' % (text.name, ex))
    return reloaded


@persistent
def _scene_update_post(_scene):
    now = time.monotonic()
    if now < _state["next"]:
        return
    _state["next"] = now + CHECK_SECONDS
    if bpy.app.background:
        return
    check_texts()


def register():
    if _scene_update_post not in bpy.app.handlers.scene_update_post:
        bpy.app.handlers.scene_update_post.append(_scene_update_post)


def unregister():
    if _scene_update_post in bpy.app.handlers.scene_update_post:
        bpy.app.handlers.scene_update_post.remove(_scene_update_post)
