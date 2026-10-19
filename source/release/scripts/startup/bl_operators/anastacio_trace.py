"""Opens the Range Trace launcher (tools/debug/range_trace_launcher.py) for the current file."""
import os
import subprocess

import bpy


def _launcher_path():
    # build/bin/AnastacioEngine.exe -> <repo>/tools/debug. Only a source checkout has it.
    root = os.path.normpath(os.path.join(os.path.dirname(bpy.app.binary_path), '..', '..'))
    return os.path.join(root, 'tools', 'debug', 'range_trace_launcher.py')


class WM_OT_range_trace_launcher(bpy.types.Operator):
    """Run this game in the player recording what loads and what is drawn, then open the report"""
    bl_idname = "wm.range_trace_launcher"
    bl_label = "Range Trace..."

    @classmethod
    def poll(cls, context):
        return os.path.isfile(_launcher_path())

    def execute(self, context):
        if bpy.data.is_dirty and bpy.data.filepath:
            self.report({'WARNING'}, "Unsaved changes: the trace runs the file as saved on disk")
        args = ["pythonw", _launcher_path()]
        if bpy.data.filepath:
            args.append(bpy.data.filepath)
        try:
            subprocess.Popen(args, close_fds=True)
        except OSError as error:
            self.report({'ERROR'}, "Could not start pythonw: %s" % error)
            return {'CANCELLED'}
        return {'FINISHED'}


classes = (
    WM_OT_range_trace_launcher,
)
