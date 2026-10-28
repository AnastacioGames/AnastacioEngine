# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
# ##### END GPL LICENSE BLOCK #####

"""Game > Performance Report: runs the open scene in the game player with the trace on and, when the
game is closed, writes a report (frame time, spikes, loading during play, what was never drawn) and
opens it in the browser."""

import os
import time

import bpy
from bpy.props import EnumProperty
from bpy.types import Operator

# Weak PC simulator (RANGE_WEAK_GPU, KX_WeakGpu in the engine): the GPU runs about N times slower.
WEAK_GPU_ITEMS = (
    ('1', "Off", "Measure with this computer as it is"),
    ('2', "2x Slower GPU", "A GPU about half as fast as this one"),
    ('4', "4x Slower GPU", "Roughly a recent integrated GPU next to a mid-range card"),
    ('8', "8x Slower GPU", "Roughly an old notebook (Intel HD 4000/4400) next to a mid-range card"),
    ('16', "16x Slower GPU", "Roughly an old notebook (Intel HD 4000/4400) next to a strong dedicated card (RX 6800M, RTX 3070)"),
    ('32', "32x Slower GPU", "Roughly an old notebook next to a high-end desktop card"),
)


def reports_dir():
    return bpy.utils.user_resource('DATAFILES', path="performance_reports", create=True)


class GAME_OT_performance_report(Operator):
    """Play the game in the player and write a performance report when it is closed"""
    bl_idname = "game.performance_report"
    bl_label = "Performance Report"

    _process = None
    _timer = None
    _folder = ""
    _tempfile = ""

    @classmethod
    def poll(cls, context):
        return context.scene is not None

    def execute(self, context):
        import subprocess
        import tempfile
        from bl_operators.anastacio_cook import _runtime_path

        runtime = _runtime_path()
        if not os.path.isfile(runtime):
            self.report({'ERROR'}, "Game runtime not found: %s" % runtime)
            return {'CANCELLED'}

        name = bpy.path.display_name_from_filepath(bpy.data.filepath) or "untitled"
        self._folder = os.path.join(reports_dir(), "%s-%s" % (bpy.path.clean_name(name), time.strftime("%Y%m%d-%H%M%S")))
        os.makedirs(self._folder, exist_ok=True)

        # Saved scene: run the file itself, so paths relative to the game folder (LibLoad, scripts,
        # sounds) work. Unsaved changes: a copy in the same folder, removed when the game closes.
        self._tempfile = ""
        if bpy.data.filepath and not bpy.data.is_dirty:
            game = bpy.data.filepath
        else:
            folder = os.path.dirname(bpy.data.filepath) if bpy.data.filepath else tempfile.gettempdir()
            game = os.path.join(folder, "_performance_report_%d.range" % os.getpid())
            saved = bpy.ops.wm.save_as_mainfile(filepath=game, copy=True, relative_remap=True, compress=False)
            if 'FINISHED' not in saved:
                self.report({'ERROR'}, "Could not save the scene to measure")
                return {'CANCELLED'}
            self._tempfile = game

        env = dict(os.environ,
                   RANGE_TRACE=self._folder,
                   RANGE_TRACE_MODULES="load,usage,frames,work,scripts,runtime",
                   RANGE_SHADER_LOG=os.path.join(self._folder, "shaders.txt"),
                   # GPU time per render step (KX_EngineProfiler), for the report's GPU section.
                   RANGE_PROFILE=os.path.join(self._folder, "profile.txt"))
        weak = int(context.window_manager.range_weak_gpu)
        env.pop("RANGE_WEAK_GPU", None)
        if weak > 1:
            env["RANGE_WEAK_GPU"] = str(weak)
        import json
        with open(os.path.join(self._folder, "settings.json"), "w", encoding="utf-8") as f:
            json.dump({"weak_gpu": weak, "world": world_settings(context.scene)}, f)
        self._process = subprocess.Popen([runtime, game], env=env, cwd=os.path.dirname(game))

        wm = context.window_manager
        self._timer = wm.event_timer_add(0.5, window=context.window)
        wm.modal_handler_add(self)
        self.report({'INFO'}, "Play the game, then close it to see the report")
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type != 'TIMER' or self._process.poll() is None:
            return {'PASS_THROUGH'}
        context.window_manager.event_timer_remove(self._timer)
        if self._tempfile:
            for path in (self._tempfile, self._tempfile + "1"):
                try:
                    os.remove(path)
                except OSError:
                    pass

        if not os.path.isfile(os.path.join(self._folder, "trace.jsonl")):
            self.report({'ERROR'}, "The game wrote no trace (exit code %d)" % self._process.returncode)
            return {'CANCELLED'}
        try:
            import anastacio_perf_report
            report = anastacio_perf_report.write_html(self._folder, title=bpy.data.filepath)
        except Exception as ex:
            self.report({'ERROR'}, "Could not write the report: %s" % ex)
            return {'CANCELLED'}
        bpy.ops.wm.url_open(url="file:///" + report.replace("\\", "/"))
        self.report({'INFO'}, "Performance report: %s" % report)
        return {'FINISHED'}


class GAME_OT_performance_reports_folder(Operator):
    """Open the folder with the performance reports"""
    bl_idname = "game.performance_reports_folder"
    bl_label = "Open Reports Folder"

    def execute(self, context):
        bpy.ops.wm.path_open(filepath=reports_dir())
        return {'FINISHED'}


class GAME_OT_performance_report_last(Operator):
    """Open the most recent performance report"""
    bl_idname = "game.performance_report_last"
    bl_label = "Open Last Report"

    def execute(self, context):
        folder = reports_dir()
        reports = [os.path.join(folder, n, "report.html") for n in os.listdir(folder)]
        reports = [r for r in reports if os.path.isfile(r)]
        if not reports:
            self.report({'WARNING'}, "No performance report yet: use Play and Measure")
            return {'CANCELLED'}
        last = max(reports, key=os.path.getmtime)
        bpy.ops.wm.url_open(url="file:///" + last.replace("\\", "/"))
        return {'FINISHED'}


def world_settings(scene):
    """Sky options that cost per pixel, for the report's sky advice."""
    world = scene.world
    if not world:
        return {}
    out = {}
    for prop in ("sky_type", "use_sky_stars", "star_style", "use_sky_moon", "sky_quality"):
        if hasattr(world, prop):
            out[prop] = getattr(world, prop)
    weather = getattr(world, "weather_settings", None)
    if weather is not None and hasattr(weather, "use_lens_flare"):
        out["use_lens_flare"] = weather.use_lens_flare
    return out


def register_props():
    bpy.types.WindowManager.range_weak_gpu = EnumProperty(
        name="Simulate Weak PC",
        description="Measure runs the game with a GPU about this many times slower than this one",
        items=WEAK_GPU_ITEMS, default='1')


def unregister_props():
    del bpy.types.WindowManager.range_weak_gpu


classes = (
    GAME_OT_performance_report,
    GAME_OT_performance_report_last,
    GAME_OT_performance_reports_folder,
)
