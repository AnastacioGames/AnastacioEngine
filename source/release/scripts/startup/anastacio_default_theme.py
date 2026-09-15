"""Applies the AnastacioGames theme as default on the user's first launch."""

import os

import bpy

_MARKER_NAME = "anastacio_default_theme_applied"
_PRESET_XML_MAP = (
    ("user_preferences.themes[0]", "Theme"),
    ("user_preferences.ui_styles[0]", "ThemeStyle"),
)


def _marker_path():
    return os.path.join(bpy.utils.user_resource('CONFIG'), _MARKER_NAME)


def _apply_default_theme(dummy1=None, dummy2=None):
    marker = _marker_path()
    if os.path.exists(marker):
        return

    for path in bpy.utils.preset_paths("interface_theme"):
        filepath = os.path.join(path, "anastaciogames.xml")
        if os.path.exists(filepath):
            try:
                import rna_xml
                rna_xml.xml_file_run(bpy.context, filepath, _PRESET_XML_MAP)
            except Exception:
                return

            try:
                result = bpy.ops.wm.save_userpref()
            except RuntimeError:
                result = {'CANCELLED'}

            if 'FINISHED' in result:
                try:
                    os.makedirs(os.path.dirname(marker), exist_ok=True)
                    with open(marker, "w") as f:
                        f.write("1")
                except OSError:
                    pass
            return


def register():
    bpy.app.handlers.load_post.append(_apply_default_theme)
    try:
        _apply_default_theme()
    except AttributeError:
        pass


def unregister():
    if _apply_default_theme in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_apply_default_theme)
