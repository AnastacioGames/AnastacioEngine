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

# Screen recorder helpers for the Info header (bl_ui/space_info.py, INFO_PT_screen_recorder).
# The recording itself is screen.screencast (C, wm_screencast.c).

import os
import sys
import time

import bpy
from bpy.types import Operator


def _default_documents_dir():
    # Same order as BKE_appdir_folder_default(), used by screen.screencast.
    if sys.platform[:3] == "win":
        home = os.environ.get("HOME")
        if home and os.path.isdir(home):
            return home
        return os.path.join(os.path.expanduser("~"), "Documents")
    return os.environ.get("XDG_DOCUMENTS_DIR") or os.path.expanduser("~")


def screencast_directory(context):
    """Folder the next recording goes to (mirrors screencast_default_filepath in screendump.c)."""
    directory = context.window_manager.screencast_directory
    if directory:
        return os.path.normpath(bpy.path.abspath(directory))
    if bpy.data.is_saved:
        return os.path.dirname(bpy.data.filepath)
    return _default_documents_dir()


# CRF of each quality, same as screencast_quality_crf() in screendump.c.
QUALITY_CRF = {'LOW': 28, 'MEDIUM': 23, 'HIGH': 18, 'VERY_HIGH': 14}

# Last standalone player recording of this session (the editor one is wm.screencast_filepath).
last_standalone_filepath = ""


def standalone_env(context):
    """Environment that makes the standalone player record its window (GPG_Canvas.cpp),
    or None when the editor isn't recording. Returns (env, video path)."""
    wm = context.window_manager
    if not (wm.is_screencast_running and wm.screencast_record_standalone):
        return None, ""
    # Named like the editor recordings (screencast_default_filepath in screendump.c).
    stamp = time.strftime("%Y%m%d-%H%M%S")
    if bpy.data.is_saved:
        name = "%s_standalone_%s.mp4" % (os.path.splitext(os.path.basename(bpy.data.filepath))[0], stamp)
    else:
        name = "standalone_%s.mp4" % stamp
    filepath = os.path.join(screencast_directory(context), name)
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
    except OSError:
        pass
    env = os.environ.copy()
    env.update({
        "RANGE_SCREENCAST_FILE": filepath,
        "RANGE_SCREENCAST_FPS": str(wm.screencast_fps),
        "RANGE_SCREENCAST_CRF": str(QUALITY_CRF.get(wm.screencast_quality, 18)),
        "RANGE_SCREENCAST_CURSOR": "1" if wm.screencast_show_cursor else "0",
        "RANGE_SCREENCAST_AUDIO": "1" if wm.screencast_audio else "0",
    })
    return env, filepath


def last_recording(context):
    """Newest of the editor and standalone recordings of this session."""
    paths = [p for p in (context.window_manager.screencast_filepath, last_standalone_filepath)
             if p and os.path.isfile(p)]
    return max(paths, key=os.path.getmtime) if paths else ""


class SCREEN_OT_screencast_open_folder(Operator):
    """Open the folder where the screen recordings are saved"""
    bl_idname = "screen.screencast_open_folder"
    bl_label = "Open Recordings Folder"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        directory = screencast_directory(context)
        try:
            os.makedirs(directory, exist_ok=True)
        except OSError as ex:
            self.report({'ERROR'}, "Could not create '%s': %s" % (directory, ex))
            return {'CANCELLED'}
        return bpy.ops.wm.path_open(filepath=directory)


class SCREEN_OT_screencast_play_last(Operator):
    """Play the last screen recording of this session (editor or standalone player) in the system video player"""
    bl_idname = "screen.screencast_play_last"
    bl_label = "Play Last Recording"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        wm = context.window_manager
        return bool(wm.screencast_filepath or last_standalone_filepath) and not wm.is_screencast_running

    def execute(self, context):
        filepath = last_recording(context)
        if not filepath:
            self.report({'ERROR'}, "Recording not found")
            return {'CANCELLED'}
        return bpy.ops.wm.path_open(filepath=filepath)


classes = (
    SCREEN_OT_screencast_open_folder,
    SCREEN_OT_screencast_play_last,
)
