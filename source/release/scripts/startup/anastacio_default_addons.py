# Turns on, once, addons that ship with the engine for users whose saved preferences predate them.
# New installs get them from the factory defaults (versioning_defaults.c). If the user turns one
# off later it stays off: the marker file remembers it was already done.

import os

import bpy
from bpy.app.handlers import persistent

ADDONS = ("anastacio_ragdoll",)


def _marker(module):
    config = bpy.utils.user_resource('CONFIG', create=True)
    return os.path.join(config, "default_addon_" + module) if config else None


@persistent
def _enable_once(_dummy=None):
    # Runs after the startup file loads (the context is restricted while scripts register).
    if _enable_once in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_enable_once)
    import addon_utils
    changed = False
    for module in ADDONS:
        marker = _marker(module)
        if not marker or os.path.exists(marker):
            continue
        try:
            if module not in bpy.context.user_preferences.addons:
                addon_utils.enable(module, default_set=True, persistent=True)
                changed = True
            open(marker, "w").close()
        except Exception as ex:
            print("anastacio_default_addons: %s: %s" % (module, ex))
    if changed:
        try:
            bpy.ops.wm.save_userpref()
        except Exception as ex:
            print("anastacio_default_addons: save preferences: %s" % ex)


def register():
    if bpy.app.factory_startup or bpy.app.background:
        return
    bpy.app.handlers.load_post.append(_enable_once)


def unregister():
    if _enable_once in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_enable_once)
