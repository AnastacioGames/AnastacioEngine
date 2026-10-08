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

# Cooked file ("<blend>.cooked"): conversion results (convex hull points, compiled material shaders) that the game reads instead of
# computing them. Playing the .blend already records what was loaded; Cook converts every scene and object
# once and writes a clean file. Export Game copies it next to the runtime.

import os
import bpy
from bpy.types import Operator


def cooked_path(context=None):
    if not bpy.data.filepath:
        return ""
    return os.path.splitext(bpy.data.filepath)[0] + ".cooked"


def _runtime_path():
    binary = bpy.app.binary_path
    directory = os.path.dirname(binary)
    extension = os.path.splitext(binary)[1]
    names = ("AnastacioRuntime.exe", "RangeRuntime.exe") if os.name == 'nt' else ("RangeRuntime" + extension,)
    candidates = [os.path.join(directory, name) for name in names]
    return next((path for path in candidates if os.path.isfile(path)), candidates[0])


class GAME_OT_cook(Operator):
    """Convert every scene and object once and save the results (convex hulls, compiled shaders) to the cooked file """ \
        """next to the .blend, so the game loads faster. Export Game copies it"""
    bl_idname = "game.cook"
    bl_label = "Cook"

    @classmethod
    def poll(cls, context):
        return bool(bpy.data.filepath)

    def execute(self, context):
        import subprocess
        import tempfile

        runtime = _runtime_path()
        if not os.path.isfile(runtime):
            self.report({'ERROR'}, "Game runtime not found: %s" % runtime)
            return {'CANCELLED'}

        target = cooked_path()
        # The game runs from a copy, so unsaved changes are cooked too and the .blend is left untouched.
        tempdir = tempfile.mkdtemp(prefix="anastacio_cook_")
        copy = os.path.join(tempdir, "cook.blend")
        fresh_target = os.path.join(tempdir, "cook.cooked")
        try:
            saved = bpy.ops.wm.save_as_mainfile(filepath=copy, copy=True, relative_remap=True, compress=False)
            if 'FINISHED' not in saved:
                self.report({'ERROR'}, "Could not save the temporary cooking scene")
                return {'CANCELLED'}
            env = dict(os.environ, ANASTACIO_COOK=fresh_target)
            if context.window:
                context.window.cursor_set('WAIT')
            result = subprocess.run([runtime, "-w", "320", "180", copy], env=env, timeout=600,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if result.returncode != 0:
                self.report({'ERROR'}, "Cook failed (runtime exit code %d)" % result.returncode)
                return {'CANCELLED'}
            if os.path.isfile(fresh_target):
                # Replace only after success, on the destination filesystem.
                import shutil
                staged = target + ".export-tmp"
                try:
                    shutil.copy2(fresh_target, staged)
                    os.replace(staged, target)
                finally:
                    if os.path.isfile(staged):
                        os.remove(staged)
            elif os.path.isfile(target):
                # A successful empty cook must not leave results from an older scene.
                os.remove(target)
        except subprocess.TimeoutExpired:
            self.report({'ERROR'}, "Cook did not finish in 10 minutes")
            return {'CANCELLED'}
        except (OSError, RuntimeError) as ex:
            self.report({'ERROR'}, "Cook failed: %s" % ex)
            return {'CANCELLED'}
        finally:
            if context.window:
                context.window.cursor_set('DEFAULT')
            import shutil
            shutil.rmtree(tempdir, ignore_errors=True)
        if os.path.isfile(target):
            self.report({'INFO'}, "Cooked: %s (%.1f MB)" % (os.path.basename(target),
                                                         os.path.getsize(target) / 1048576.0))
        else:
            self.report({'INFO'}, "Nothing to cook (no convex hull shapes or material shaders)")
        return {'FINISHED'}


class GAME_OT_cook_clear(Operator):
    """Delete the cooked file next to the .blend: the game computes everything again"""
    bl_idname = "game.cook_clear"
    bl_label = "Clear Cooked"

    @classmethod
    def poll(cls, context):
        path = cooked_path()
        return bool(path) and os.path.isfile(path)

    def execute(self, context):
        os.remove(cooked_path())
        self.report({'INFO'}, "Cooked file deleted")
        return {'FINISHED'}


classes = (
    GAME_OT_cook,
    GAME_OT_cook_clear,
)
