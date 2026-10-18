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

# Painel Subtitles do Text Editor: aparece com um .srt aberto e edita as legendas em um clique
# (adicionar, tempos, sincronizar, cor, posicao, verificacao). Opera na legenda onde esta o cursor.

import re

import bpy
from bpy.types import Operator, Panel

TIME_LINE = re.compile(r"^\s*(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)")
COLOR_TAG = re.compile(r'<font\s+color\s*=\s*"?#?([0-9a-fA-F]{6})"?\s*>(.*?)</font>', re.I)
TOP_TAG = "{\\an8}"
# limites comuns de legendagem (Netflix e afins)
MAX_LINE = 42
MAX_LINES = 2
MAX_CPS = 21.0
MIN_DURATION = 0.7
GAP = 0.1


def is_srt(text):
    return text is not None and text.name.lower().endswith(".srt")


def format_time(seconds):
    ms = int(round(max(0.0, seconds) * 1000))
    return "%02d:%02d:%02d,%03d" % (ms // 3600000, ms // 60000 % 60, ms // 1000 % 60, ms % 1000)


def parse(lines):
    """Blocos do .srt: dicts com start, end (s), body (linhas) e first/last (linhas do arquivo)."""
    cues = []
    i = 0
    while i < len(lines):
        match = TIME_LINE.match(lines[i])
        if not match:
            i += 1
            continue
        g = [int(v) for v in match.groups()]
        first = i - 1 if i > 0 and lines[i - 1].strip().isdigit() else i
        j = i + 1
        while j < len(lines) and lines[j].strip():
            j += 1
        cues.append({
            "start": g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000.0,
            "end": g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000.0,
            "body": lines[i + 1:j],
            "first": first,
            "last": j - 1,
        })
        i = j
    return cues


def build(cues):
    blocks = []
    for n, cue in enumerate(cues, 1):
        blocks.append("%d\n%s --> %s\n%s" % (n, format_time(cue["start"]), format_time(cue["end"]),
                                             "\n".join(cue["body"])))
    return "\n\n".join(blocks) + "\n"


def plain(line):
    return re.sub(r"<[^>]*>|\{\\[^}]*\}", "", line)


def cue_at_cursor(text, cues):
    """Indice da legenda do cursor (a anterior quando o cursor esta entre duas), -1 sem legendas."""
    row = text.current_line_index
    index = -1
    for n, cue in enumerate(cues):
        if cue["first"] <= row:
            index = n
    return 0 if index < 0 and cues else index


def write(text, cues, select=None, body_line=0):
    """Reescreve o texto (renumerado) e poe o cursor na linha body_line da legenda select."""
    text.from_string(build(cues))
    if select is not None and 0 <= select < len(cues):
        line = parse(text.as_string().split("\n"))[select]["first"] + 2 + body_line
        text.current_line_index = line
        _cursor(line)


def _cursor(line):
    space = bpy.context.space_data
    if space and space.type == 'TEXT_EDITOR':
        try:
            bpy.ops.text.jump(line=line + 1)
        except RuntimeError:
            pass


def problems(cues):
    """[(indice, mensagem)] com os erros e avisos comuns de legendagem."""
    found = []
    for n, cue in enumerate(cues):
        duration = cue["end"] - cue["start"]
        body = [plain(l) for l in cue["body"]]
        label = "#%d" % (n + 1)
        if duration <= 0:
            found.append((n, "%s ends before it starts" % label))
        elif duration < MIN_DURATION:
            found.append((n, "%s is too short (%.2f s)" % (label, duration)))
        if n and cue["start"] < cues[n - 1]["end"]:
            found.append((n, "%s overlaps the one before" % label))
        if not any(l.strip() for l in body):
            found.append((n, "%s has no text" % label))
        if len(body) > MAX_LINES:
            found.append((n, "%s has %d lines (max %d)" % (label, len(body), MAX_LINES)))
        long_lines = [l for l in body if len(l) > MAX_LINE]
        if long_lines:
            found.append((n, "%s has a line over %d characters" % (label, MAX_LINE)))
        chars = sum(len(l) for l in body)
        if duration > 0 and chars / duration > MAX_CPS:
            found.append((n, "%s is fast to read (%.0f characters/s, max %.0f)" % (label, chars / duration, MAX_CPS)))
    return found


class SrtOperator:
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return is_srt(getattr(context.space_data, "text", None))

    def cues(self, context):
        text = context.space_data.text
        return text, parse(text.as_string().split("\n"))


class TEXT_OT_srt_add(SrtOperator, Operator):
    """Add a subtitle after the one at the cursor"""
    bl_idname = "text.srt_add"
    bl_label = "Add Subtitle"

    duration = bpy.props.FloatProperty(name="Duration", default=2.0, min=0.1, unit='TIME')

    def execute(self, context):
        text, cues = self.cues(context)
        n = cue_at_cursor(text, cues)
        start = cues[n]["end"] + GAP if n >= 0 else 0.5
        cues.insert(n + 1, {"start": start, "end": start + self.duration, "body": ["New subtitle"]})
        # empurra as seguintes que ficariam sobrepostas
        for k in range(n + 2, len(cues)):
            push = cues[k - 1]["end"] + GAP - cues[k]["start"]
            if push <= 0:
                break
            cues[k]["start"] += push
            cues[k]["end"] += push
        write(text, cues, n + 1)
        return {'FINISHED'}


class TEXT_OT_srt_duplicate(SrtOperator, Operator):
    """Copy the subtitle at the cursor right after it"""
    bl_idname = "text.srt_duplicate"
    bl_label = "Duplicate"

    def execute(self, context):
        text, cues = self.cues(context)
        n = cue_at_cursor(text, cues)
        if n < 0:
            return {'CANCELLED'}
        cue = dict(cues[n], body=list(cues[n]["body"]))
        length = cue["end"] - cue["start"]
        cue["start"] = cues[n]["end"] + GAP
        cue["end"] = cue["start"] + length
        cues.insert(n + 1, cue)
        write(text, cues, n + 1)
        return {'FINISHED'}


class TEXT_OT_srt_remove(SrtOperator, Operator):
    """Remove the subtitle at the cursor"""
    bl_idname = "text.srt_remove"
    bl_label = "Remove"

    def execute(self, context):
        text, cues = self.cues(context)
        n = cue_at_cursor(text, cues)
        if n < 0:
            return {'CANCELLED'}
        del cues[n]
        write(text, cues, min(n, len(cues) - 1))
        return {'FINISHED'}


class TEXT_OT_srt_merge(SrtOperator, Operator):
    """Join the subtitle at the cursor with the next one"""
    bl_idname = "text.srt_merge"
    bl_label = "Merge with Next"

    def execute(self, context):
        text, cues = self.cues(context)
        n = cue_at_cursor(text, cues)
        if n < 0 or n + 1 >= len(cues):
            self.report({'WARNING'}, "No next subtitle to merge with")
            return {'CANCELLED'}
        nxt = cues.pop(n + 1)
        cues[n]["end"] = max(cues[n]["end"], nxt["end"])
        cues[n]["body"] = cues[n]["body"] + nxt["body"]
        write(text, cues, n)
        return {'FINISHED'}


class TEXT_OT_srt_split(SrtOperator, Operator):
    """Split the subtitle at the cursor in two, half of the time and of the lines each"""
    bl_idname = "text.srt_split"
    bl_label = "Split"

    def execute(self, context):
        text, cues = self.cues(context)
        n = cue_at_cursor(text, cues)
        if n < 0:
            return {'CANCELLED'}
        cue = cues[n]
        middle = (cue["start"] + cue["end"]) / 2
        body = cue["body"] or [""]
        if len(body) > 1:
            cut = len(body) // 2
            first, rest = body[:cut], body[cut:]
        else:
            # uma linha so: corta nas palavras, no meio, mantendo cor e posicao nas duas partes
            line = body[0]
            top = TOP_TAG if TOP_TAG in line else ""
            color = COLOR_TAG.search(line)
            words = plain(line).split()
            cut = max(1, len(words) // 2)
            halves = [" ".join(words[:cut]), " ".join(words[cut:]) or "..."]
            if color:
                halves = ['<font color="#%s">%s</font>' % (color.group(1), h) for h in halves]
            first, rest = [top + halves[0]], [top + halves[1]]
        second = {"start": middle + GAP / 2, "end": cue["end"], "body": rest}
        cue["end"] = middle - GAP / 2
        cue["body"] = first
        cues.insert(n + 1, second)
        write(text, cues, n + 1)
        return {'FINISHED'}


class TEXT_OT_srt_time(SrtOperator, Operator):
    """Move the start or the end of the subtitle at the cursor"""
    bl_idname = "text.srt_time"
    bl_label = "Adjust Time"

    edge = bpy.props.EnumProperty(items=(('START', "Start", ""), ('END', "End", ""), ('BOTH', "Both", "")))
    delta = bpy.props.FloatProperty(name="Seconds", default=0.1)

    def execute(self, context):
        text, cues = self.cues(context)
        n = cue_at_cursor(text, cues)
        if n < 0:
            return {'CANCELLED'}
        cue = cues[n]
        if self.edge in {'START', 'BOTH'}:
            cue["start"] = max(0.0, cue["start"] + self.delta)
        if self.edge in {'END', 'BOTH'}:
            cue["end"] = max(cue["start"] + 0.1, cue["end"] + self.delta)
        write(text, cues, n)
        return {'FINISHED'}


class TEXT_OT_srt_shift(SrtOperator, Operator):
    """Move many subtitles in time, to sync them with the video"""
    bl_idname = "text.srt_shift"
    bl_label = "Shift Subtitles"

    seconds = bpy.props.FloatProperty(name="Seconds", default=0.5,
                                      description="Positive delays the subtitles, negative brings them earlier")
    scope = bpy.props.EnumProperty(name="Which", items=(
        ('ALL', "All", "Every subtitle"),
        ('FROM_CURSOR', "From Cursor", "The one at the cursor and the ones after it"),
    ))

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        text, cues = self.cues(context)
        n = cue_at_cursor(text, cues)
        first = 0 if self.scope == 'ALL' else max(0, n)
        for cue in cues[first:]:
            cue["start"] = max(0.0, cue["start"] + self.seconds)
            cue["end"] = max(cue["start"] + 0.1, cue["end"] + self.seconds)
        write(text, cues, max(0, n))
        return {'FINISHED'}


class TEXT_OT_srt_tidy(SrtOperator, Operator):
    """Sort the subtitles by time, number them again and close the overlaps"""
    bl_idname = "text.srt_tidy"
    bl_label = "Sort and Renumber"

    def execute(self, context):
        text, cues = self.cues(context)
        cues.sort(key=lambda cue: cue["start"])
        fixed = 0
        for k in range(1, len(cues)):
            if cues[k]["start"] < cues[k - 1]["end"]:
                cues[k - 1]["end"] = max(cues[k - 1]["start"] + 0.1, cues[k]["start"] - GAP)
                fixed += 1
        write(text, cues, 0)
        self.report({'INFO'}, "%d subtitles, %d overlaps closed" % (len(cues), fixed))
        return {'FINISHED'}


class TEXT_OT_srt_style(SrtOperator, Operator):
    """Format the subtitle at the cursor"""
    bl_idname = "text.srt_style"
    bl_label = "Subtitle Style"

    style = bpy.props.EnumProperty(items=(
        ('COLOR', "Color", "Paint the text with the color picked in the panel"),
        ('TOP', "Top", "Show this subtitle at the top of the screen (for when something important is "
                       "at the bottom)"),
        ('CLEAR', "Clear", "Remove the color and the position"),
    ))

    def execute(self, context):
        text, cues = self.cues(context)
        n = cue_at_cursor(text, cues)
        if n < 0:
            return {'CANCELLED'}
        cue = cues[n]
        body = list(cue["body"])
        if self.style in {'COLOR', 'CLEAR'}:
            body = [COLOR_TAG.sub(r"\2", l) for l in body]
        top = any(TOP_TAG in l for l in body)
        body = [l.replace(TOP_TAG, "") for l in body]
        if self.style == 'COLOR':
            c = context.window_manager.srt_color
            hexa = "%02X%02X%02X" % tuple(int(round(max(0.0, min(1.0, v)) * 255)) for v in c)
            body = ['<font color="#%s">%s</font>' % (hexa, l) if l else l for l in body]
        elif self.style == 'TOP':
            top = not top
        elif self.style == 'CLEAR':
            top = False
        if top and body:
            body[0] = TOP_TAG + body[0]
        cue["body"] = body
        write(text, cues, n)
        return {'FINISHED'}


class TEXT_OT_srt_check(SrtOperator, Operator):
    """Look for overlaps, wrong times, long lines and subtitles too fast to read"""
    bl_idname = "text.srt_check"
    bl_label = "Check"

    def execute(self, context):
        text, cues = self.cues(context)
        found = problems(cues)
        if not found:
            self.report({'INFO'}, "%d subtitles, no problems" % len(cues))
            return {'FINISHED'}
        for _n, message in found[:8]:
            print("Subtitles:", message)
        self.report({'WARNING'}, "%d problems; first: %s" % (len(found), found[0][1]))
        write(text, cues, found[0][0])
        return {'FINISHED'}


class TEXT_PT_subtitles(Panel):
    bl_space_type = 'TEXT_EDITOR'
    bl_region_type = 'UI'
    bl_category = "Text"
    bl_label = "Subtitles"

    @classmethod
    def poll(cls, context):
        return is_srt(context.space_data.text)

    def draw(self, context):
        layout = self.layout
        text = context.space_data.text
        cues = parse(text.as_string().split("\n"))
        n = cue_at_cursor(text, cues)

        box = layout.box()
        if n >= 0:
            cue = cues[n]
            duration = cue["end"] - cue["start"]
            chars = sum(len(plain(l)) for l in cue["body"])
            box.label(text="Subtitle %d of %d" % (n + 1, len(cues)), icon='FONT_DATA')
            col = box.column(align=True)
            col.label(text="%s  >  %s" % (format_time(cue["start"]), format_time(cue["end"])))
            cps = chars / duration if duration > 0 else 0.0
            col.label(text="%.2f s   %d characters   %.0f /s" % (duration, chars, cps),
                      icon='ERROR' if cps > MAX_CPS or duration <= 0 else 'TIME')
        else:
            box.label(text="No subtitle yet", icon='INFO')

        box = layout.box()
        box.label(text="Edit:")
        col = box.column(align=True)
        col.operator("text.srt_add", icon='ZOOMIN')
        row = col.row(align=True)
        row.operator("text.srt_duplicate", icon='COPYDOWN')
        row.operator("text.srt_remove", icon='X')
        row = col.row(align=True)
        row.operator("text.srt_split", icon='ALIGN')
        row.operator("text.srt_merge", icon='AUTOMERGE_ON')

        box = layout.box()
        box.label(text="Timing:")
        col = box.column(align=True)
        for edge, label in (('START', "Start"), ('END', "End"), ('BOTH', "Move")):
            row = col.row(align=True)
            row.label(text=label)
            for delta, name in ((-0.5, "-0.5"), (-0.1, "-0.1"), (0.1, "+0.1"), (0.5, "+0.5")):
                op = row.operator("text.srt_time", text=name)
                op.edge = edge
                op.delta = delta
        col = box.column(align=True)
        col.operator("text.srt_shift", text="Sync / Shift Subtitles...", icon='TIME')
        col.operator("text.srt_tidy", icon='SORTTIME')

        box = layout.box()
        box.label(text="Style:")
        row = box.row(align=True)
        row.prop(context.window_manager, "srt_color", text="")
        row.operator("text.srt_style", text="Color", icon='COLOR').style = 'COLOR'
        row = box.row(align=True)
        row.operator("text.srt_style", text="Top of Screen", icon='TRIA_UP_BAR').style = 'TOP'
        row.operator("text.srt_style", text="Clear", icon='X').style = 'CLEAR'

        box = layout.box()
        row = box.row(align=True)
        row.operator("text.srt_check", icon='VIEWZOOM')
        row.operator("text.save", text="Save", icon='FILE_TICK')
        box.label(text="Max %d characters a line, %d lines, %d characters/s" % (MAX_LINE, MAX_LINES, MAX_CPS))


bpy.types.WindowManager.srt_color = bpy.props.FloatVectorProperty(
    name="Subtitle Color", subtype='COLOR', size=3, min=0.0, max=1.0, default=(1.0, 0.85, 0.2))

classes = (
    TEXT_OT_srt_add,
    TEXT_OT_srt_duplicate,
    TEXT_OT_srt_remove,
    TEXT_OT_srt_merge,
    TEXT_OT_srt_split,
    TEXT_OT_srt_time,
    TEXT_OT_srt_shift,
    TEXT_OT_srt_tidy,
    TEXT_OT_srt_style,
    TEXT_OT_srt_check,
    TEXT_PT_subtitles,
)

if __name__ == "__main__":  # only for live edit.
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)
