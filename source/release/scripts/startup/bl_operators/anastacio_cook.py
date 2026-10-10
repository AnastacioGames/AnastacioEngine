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

import math
import os
import time
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


def _install_cooked(fresh_target, target):
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


def _result_message(target):
    if os.path.isfile(target):
        return "Cooked: %s (%.1f MB)" % (os.path.basename(target), os.path.getsize(target) / 1048576.0)
    return "Nothing to cook (no convex hull shapes or material shaders)"


# Cooking screen: a pot on a row of blue gas flames, drawn over the largest editor while the runtime cooks.

def _iface(text):
    return bpy.app.translations.pgettext_iface(text)


def _rect(bgl, x0, y0, x1, y1, color):
    bgl.glColor4f(*color)
    bgl.glRecti(int(x0), int(y0), int(x1), int(y1))


def _round_rect(bgl, x0, y0, x1, y1, radius, color):
    bgl.glColor4f(*color)
    bgl.glBegin(bgl.GL_POLYGON)
    for cx, cy, start in ((x1 - radius, y0 + radius, -90), (x1 - radius, y1 - radius, 0),
                          (x0 + radius, y1 - radius, 90), (x0 + radius, y0 + radius, 180)):
        for step in range(7):
            angle = math.radians(start + step * 15)
            bgl.glVertex2f(cx + math.cos(angle) * radius, cy + math.sin(angle) * radius)
    bgl.glEnd()


def _text(blf, text, x, y, size, color, dpi):
    import bgl
    bgl.glColor4f(*color)
    blf.size(0, size, dpi)
    width = blf.dimensions(0, text)[0]
    blf.position(0, x - width / 2, y, 0)
    blf.draw(0, text)


def _draw_pot(bgl, ox, oy, k, t, lit):
    # Geometry from the approved mockup: a 260x200 box, y pointing down.
    def P(x, y):
        return ox + x * k, oy + (200 - y) * k

    def box(x0, y0, x1, y1, color):
        a, b = P(x0, y1)
        c, d = P(x1, y0)
        _rect(bgl, a, b, c, d, color)

    # Steam.
    if lit:
        bgl.glLineWidth(max(1.0, 3.0 * k))
        for i, x in enumerate((100, 130, 160)):
            phase = (t / 2.4 + i / 3.0) % 1.0
            alpha = (phase / 0.3 if phase < 0.3 else (1.0 - phase) / 0.7) * 0.7
            rise = 8 - 36 * phase
            bgl.glColor4f(0.73, 0.73, 0.73, alpha)
            bgl.glBegin(bgl.GL_LINE_STRIP)
            for step in range(13):
                f = step / 12.0
                bgl.glVertex2f(*P(x + math.sin(f * math.pi * 2) * -5, 40 + rise - f * 48))
            bgl.glEnd()
        bgl.glLineWidth(1.0)

    # Lid, knob, handles and the body with a metal gradient.
    box(122, 36, 138, 46, (0.4, 0.4, 0.4, 1))
    box(70, 44, 190, 54, (0.67, 0.70, 0.73, 1))
    box(48, 66, 76, 75, (0.27, 0.27, 0.27, 1))
    box(184, 66, 212, 75, (0.27, 0.27, 0.27, 1))
    bgl.glBegin(bgl.GL_QUAD_STRIP)
    for x, shade in ((74, (0.60, 0.64, 0.68)), (130, (0.84, 0.86, 0.89)), (186, (0.49, 0.52, 0.56))):
        bgl.glColor4f(shade[0], shade[1], shade[2], 1)
        bgl.glVertex2f(*P(x, 126))
        bgl.glVertex2f(*P(x, 56))
    bgl.glEnd()

    # Horizontal row of flames under the pot.
    if lit:
        for i in range(11):
            x = 72 + i * 11.6
            speed = 2.2 + (i * 7 % 5) * 0.35
            grow = 0.95 + 0.2 * math.sin(t * speed * math.pi * 2 + i * 1.7)
            tip = 22 * grow
            bgl.glBegin(bgl.GL_TRIANGLE_FAN)
            bgl.glColor4f(0.37, 0.72, 1.0, 0.9)
            bgl.glVertex2f(*P(x, 156 - tip * 0.35))
            bgl.glColor4f(0.12, 0.31, 0.85, 1)
            bgl.glVertex2f(*P(x - 5, 156))
            bgl.glVertex2f(*P(x + 5, 156))
            bgl.glColor4f(0.37, 0.72, 1.0, 0.8)
            bgl.glVertex2f(*P(x + 3, 156 - tip * 0.5))
            bgl.glColor4f(0.91, 0.96, 1.0, 0.15)
            bgl.glVertex2f(*P(x, 156 - tip))
            bgl.glColor4f(0.37, 0.72, 1.0, 0.8)
            bgl.glVertex2f(*P(x - 3, 156 - tip * 0.5))
            bgl.glColor4f(0.12, 0.31, 0.85, 1)
            bgl.glVertex2f(*P(x - 5, 156))
            bgl.glEnd()

    # Burner.
    box(60, 156, 200, 164, (0.33, 0.33, 0.33, 1))
    box(40, 166, 220, 172, (0.2, 0.2, 0.2, 1))


def _draw_cooking(op):
    context = bpy.context
    if context.area is None or context.area.as_pointer() != op._area:
        return
    import bgl
    import blf

    region = context.region
    scale = getattr(context.user_preferences.view, "ui_scale", 1.0)
    dpi = context.user_preferences.system.dpi
    t = time.time() - op._start
    width, height = 280 * scale, 240 * scale
    x0 = (region.width - width) / 2
    y0 = (region.height - height) / 2

    bgl.glEnable(bgl.GL_BLEND)
    bgl.glBlendFunc(bgl.GL_SRC_ALPHA, bgl.GL_ONE_MINUS_SRC_ALPHA)
    bgl.glShadeModel(bgl.GL_SMOOTH)
    _round_rect(bgl, x0 - 4 * scale, y0 - 6 * scale, x0 + width + 4 * scale, y0 + height + 2 * scale, 12 * scale,
                (0, 0, 0, 0.35))
    _round_rect(bgl, x0, y0, x0 + width, y0 + height, 10 * scale, (0.17, 0.17, 0.17, 0.97))

    k = 0.62 * scale
    _draw_pot(bgl, x0 + (width - 260 * k) / 2, y0 + height - 200 * k - 6 * scale, k, t, op._done is None)

    center = x0 + width / 2
    if op._done is None:
        stage, detail = op._stage, "%02d:%02d" % (int(t) // 60, int(t) % 60)
    else:
        stage, detail = op._done, ""
    _text(blf, _iface(stage), center, y0 + 82 * scale, 12, (0.87, 0.87, 0.87, 1), dpi)
    if detail:
        _text(blf, detail, center, y0 + 66 * scale, 10, (0.53, 0.53, 0.53, 1), dpi)

    # Progress bar: the runtime gives no percentage, so a blue segment sweeps across it.
    bx0, bx1, by = x0 + 20 * scale, x0 + width - 20 * scale, y0 + 50 * scale
    _rect(bgl, bx0, by, bx1, by + 5 * scale, (0.1, 0.1, 0.1, 1))
    if op._done is None:
        span = (bx1 - bx0) * 0.3
        head = bx0 + ((t / 1.6) % 1.0) * (bx1 - bx0 + span)
        bgl.glBegin(bgl.GL_QUADS)
        bgl.glColor4f(0.16, 0.42, 1.0, 1)
        bgl.glVertex2f(max(bx0, head - span), by)
        bgl.glColor4f(0.37, 0.72, 1.0, 1)
        bgl.glVertex2f(min(bx1, head), by)
        bgl.glVertex2f(min(bx1, head), by + 5 * scale)
        bgl.glColor4f(0.16, 0.42, 1.0, 1)
        bgl.glVertex2f(max(bx0, head - span), by + 5 * scale)
        bgl.glEnd()
    else:
        _rect(bgl, bx0, by, bx1, by + 5 * scale, (0.37, 0.72, 1.0, 1))

    # Cancel button (clicked in window coordinates, see GAME_OT_cook.modal()).
    if op._done is None:
        cw, ch = 90 * scale, 22 * scale
        cx0, cy0 = center - cw / 2, y0 + 14 * scale
        _round_rect(bgl, cx0, cy0, cx0 + cw, cy0 + ch, 4 * scale, (0.24, 0.24, 0.24, 1))
        _text(blf, _iface("Cancel"), center, cy0 + 7 * scale, 10, (0.87, 0.87, 0.87, 1), dpi)
        op._cancel_rect = (region.x + cx0, region.y + cy0, region.x + cx0 + cw, region.y + cy0 + ch)

    bgl.glDisable(bgl.GL_BLEND)
    bgl.glColor4f(1, 1, 1, 1)


class GAME_OT_cook(Operator):
    """Convert every scene and object once and save the results (convex hulls, compiled shaders) to the cooked file """ \
        """next to the .blend, so the game loads faster. Export Game copies it"""
    bl_idname = "game.cook"
    bl_label = "Cook"

    @classmethod
    def poll(cls, context):
        if not bpy.data.filepath:
            return False
        # Already up to date: the cooked file is newer than the saved .blend and nothing changed since.
        target = cooked_path()
        try:
            return bpy.data.is_dirty or os.path.getmtime(target) < os.path.getmtime(bpy.data.filepath)
        except OSError:
            return True

    def _prepare(self):
        """Save a copy of the scene to cook; returns (args, env, tempdir, fresh_target) or None after reporting."""
        import tempfile

        runtime = _runtime_path()
        if not os.path.isfile(runtime):
            self.report({'ERROR'}, "Game runtime not found: %s" % runtime)
            return None
        # The game runs from a copy, so unsaved changes are cooked too and the .blend is left untouched.
        tempdir = tempfile.mkdtemp(prefix="anastacio_cook_")
        copy = os.path.join(tempdir, "cook.blend")
        fresh_target = os.path.join(tempdir, "cook.cooked")
        saved = bpy.ops.wm.save_as_mainfile(filepath=copy, copy=True, relative_remap=True, compress=False)
        if 'FINISHED' not in saved:
            import shutil
            shutil.rmtree(tempdir, ignore_errors=True)
            self.report({'ERROR'}, "Could not save the temporary cooking scene")
            return None
        env = dict(os.environ, ANASTACIO_COOK=fresh_target)
        return [runtime, "-w", "320", "180", copy], env, tempdir, fresh_target

    def execute(self, context):
        import shutil
        import subprocess

        prepared = self._prepare()
        if prepared is None:
            return {'CANCELLED'}
        args, env, tempdir, fresh_target = prepared
        target = cooked_path()
        try:
            if context.window:
                context.window.cursor_set('WAIT')
            result = subprocess.run(args, env=env, timeout=600, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if result.returncode != 0:
                self.report({'ERROR'}, "Cook failed (runtime exit code %d)" % result.returncode)
                return {'CANCELLED'}
            _install_cooked(fresh_target, target)
        except subprocess.TimeoutExpired:
            self.report({'ERROR'}, "Cook did not finish in 10 minutes")
            return {'CANCELLED'}
        except (OSError, RuntimeError) as ex:
            self.report({'ERROR'}, "Cook failed: %s" % ex)
            return {'CANCELLED'}
        finally:
            if context.window:
                context.window.cursor_set('DEFAULT')
            shutil.rmtree(tempdir, ignore_errors=True)
        self.report({'INFO'}, _result_message(target))
        return {'FINISHED'}

    # From the button: the runtime cooks in the background while the cooking screen is drawn.

    def invoke(self, context, event):
        import subprocess
        import threading

        areas = [area for area in context.window.screen.areas if area.type != 'INFO']
        area = max(areas, key=lambda a: a.width * a.height) if areas else None
        space = getattr(bpy.types, type(area.spaces.active).__name__, None) if area else None
        if space is None or not hasattr(space, "draw_handler_add"):
            return self.execute(context)

        prepared = self._prepare()
        if prepared is None:
            return {'CANCELLED'}
        args, env, self._tempdir, self._fresh_target = prepared
        self._target = cooked_path()
        try:
            self._process = subprocess.Popen(args, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                             stdin=subprocess.DEVNULL)
        except OSError as ex:
            self._cleanup_tempdir()
            self.report({'ERROR'}, "Cook failed: %s" % ex)
            return {'CANCELLED'}

        self._stage = "Converting scenes..."
        self._done = None
        self._done_at = 0.0
        self._message = None
        self._cancel_rect = None
        self._start = time.time()
        self._reader = threading.Thread(target=self._read_output, daemon=True)
        self._reader.start()

        self._area = area.as_pointer()
        self._space = space
        self._handle = space.draw_handler_add(_draw_cooking, (self,), 'WINDOW', 'POST_PIXEL')
        self._timer = context.window_manager.event_timer_add(1.0 / 30.0, context.window)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def _read_output(self):
        # Drains the pipe (a full one would block the runtime) and follows its stages.
        for raw in self._process.stdout:
            line = raw.decode("utf-8", "replace")
            if "[Cooked] compiling every shader" in line:
                self._stage = "Compiling shaders..."

    def _cleanup_tempdir(self):
        import shutil
        shutil.rmtree(self._tempdir, ignore_errors=True)

    def _finish(self, context):
        context.window_manager.event_timer_remove(self._timer)
        self._space.draw_handler_remove(self._handle, 'WINDOW')
        self._cleanup_tempdir()
        self._redraw(context)

    def _redraw(self, context):
        for area in context.window.screen.areas:
            if area.as_pointer() == self._area:
                area.tag_redraw()

    def modal(self, context, event):
        if self._done is not None:
            # "Cooked!" stays on screen for a moment.
            if time.time() - self._done_at > 1.5:
                self._finish(context)
                self.report({'INFO'}, self._message)
                return {'FINISHED'}
            self._redraw(context)
            return {'PASS_THROUGH'}

        cancel = event.type == 'ESC' and event.value == 'PRESS'
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS' and self._cancel_rect:
            x0, y0, x1, y1 = self._cancel_rect
            cancel = x0 <= event.mouse_x <= x1 and y0 <= event.mouse_y <= y1
        if cancel or time.time() - self._start > 600:
            self._process.kill()
            self._process.wait()
            self._finish(context)
            if cancel:
                self.report({'WARNING'}, "Cook cancelled")
            else:
                self.report({'ERROR'}, "Cook did not finish in 10 minutes")
            return {'CANCELLED'}

        returncode = self._process.poll()
        if returncode is None:
            if event.type == 'TIMER':
                self._redraw(context)
            return {'RUNNING_MODAL'} if event.type == 'LEFTMOUSE' and self._inside_card(event) else {'PASS_THROUGH'}

        self._reader.join(1.0)
        if returncode != 0:
            self._finish(context)
            self.report({'ERROR'}, "Cook failed (runtime exit code %d)" % returncode)
            return {'CANCELLED'}
        try:
            _install_cooked(self._fresh_target, self._target)
        except OSError as ex:
            self._finish(context)
            self.report({'ERROR'}, "Cook failed: %s" % ex)
            return {'CANCELLED'}
        self._message = _result_message(self._target)
        size = os.path.getsize(self._target) / 1048576.0 if os.path.isfile(self._target) else 0.0
        self._done = _iface("Cooked!") + (" %.1f MB" % size if size else "")
        self._done_at = time.time()
        self._redraw(context)
        return {'PASS_THROUGH'}

    def _inside_card(self, event):
        # Clicks on the card itself must not reach the editor below it.
        if not self._cancel_rect:
            return False
        x0, y0, x1, y1 = self._cancel_rect
        center_x = (x0 + x1) / 2
        scale = getattr(bpy.context.user_preferences.view, "ui_scale", 1.0)
        bottom = y0 - 14 * scale
        return abs(event.mouse_x - center_x) <= 140 * scale and bottom <= event.mouse_y <= bottom + 240 * scale


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
