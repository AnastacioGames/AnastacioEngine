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
import bpy
from bpy.types import Panel


class DataButtonsPanel:
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"

    @classmethod
    def poll(cls, context):
        return (context.object and context.object.type == 'EMPTY')


class DATA_PT_empty(DataButtonsPanel, Panel):
    bl_label = "Empty"

    def draw(self, context):
        layout = self.layout

        ob = context.object

        box = layout.box()
        box.label(text="Empty:", icon="EMPTY_DATA")
        box.prop(ob, "empty_draw_type", text="Display")

        if ob.empty_draw_type == 'IMAGE':
            box.template_ID(ob, "data", open="image.open", unlink="object.unlink_data")
            box.template_image(ob, "data", ob.image_user, compact=True)

            row = box.row(align=True)
            row = box.row(align=True)

            box.prop(ob, "color", text="Transparency", index=3, slider=True)
            row = box.row(align=True)
            row.prop(ob, "empty_image_offset", text="Offset X", index=0)
            row.prop(ob, "empty_image_offset", text="Offset Y", index=1)

        box.prop(ob, "empty_draw_size", text="Size")


class DATA_PT_reverb_area(DataButtonsPanel, Panel):
    bl_label = "Reverb Area"

    def draw_header(self, context):
        self.layout.prop(context.object, "use_reverb_area", text="")

    def draw(self, context):
        layout = self.layout

        ob = context.object
        ra = ob.reverb_area
        layout.active = ob.use_reverb_area

        box = layout.box()
        box.label(text="Area:", icon='SOUND')
        box.prop(ra, "preset")
        box.prop(ra, "shape")
        box.prop(ob, "empty_draw_size", text="Size")
        box.prop(ra, "inner_factor", slider=True)
        box.prop(ra, "priority")
        box.label(text="Affects 3D speakers while the active camera is inside the area", icon='INFO')

        box = layout.box()
        box.label(text="Reverb:", icon='SPEAKER')
        box.label(text="Editing any value switches Behavior to Custom")
        split = box.split()
        col = split.column(align=True)
        col.prop(ra, "gain")
        col.prop(ra, "gain_hf")
        col.prop(ra, "density")
        col.prop(ra, "diffusion")
        col.prop(ra, "decay_time")
        col.prop(ra, "decay_hf_ratio")
        col.prop(ra, "decay_limit_hf")
        col = split.column(align=True)
        col.label(text="Reflections:")
        col.prop(ra, "reflections_gain", text="Gain")
        col.prop(ra, "reflections_delay", text="Delay")
        col.prop(ra, "late_reverb_gain", text="Late Gain")
        col.prop(ra, "late_reverb_delay", text="Late Delay")
        col.prop(ra, "air_absorption_gain_hf")
        col.prop(ra, "room_rolloff_factor")

        box = layout.box()
        box.label(text="Filter:", icon='FILTER')
        row = box.row(align=True)
        row.prop(ra, "use_filter")
        sub = row.row(align=True)
        sub.active = ra.use_filter
        sub.prop(ra, "filter_type", text="")
        row = box.row(align=True)
        row.active = ra.use_filter
        row.prop(ra, "filter_gain", text="Gain")
        row.prop(ra, "filter_gain_lf", text="LF")
        row.prop(ra, "filter_gain_hf", text="HF")


class DATA_PT_lightning(DataButtonsPanel, Panel):
    bl_label = "Lightning"

    def draw_header(self, context):
        self.layout.prop(context.object, "use_lightning", text="")

    def draw(self, context):
        layout = self.layout

        ob = context.object
        ls = ob.lightning
        layout.active = ob.use_lightning

        box = layout.box()
        box.label(text="Where:", icon='MAN_TRANS')
        row = box.row(align=True)
        row.prop(ls, "shape", text="")
        row.prop(ob, "empty_draw_size", text="Size")
        box.prop(ls, "target")
        sub = box.column()
        sub.active = ls.target is None
        sub.prop(ls, "height")
        sub.prop(ls, "use_hit_ground")

        box = layout.box()
        box.label(text="When:", icon='TIME')
        box.row().prop(ls, "mode", expand=True)
        if ls.mode == 'AUTOMATIC':
            box.prop(ls, "rate")
            box.prop(ls, "big_chance", slider=True)
            row = box.row(align=True)
            row.prop(ls, "start_time")
            row.prop(ls, "end_time")
        else:
            box.label(text="obj.strikeLightning() or Edit Object > Lightning Strike", icon='INFO')

        box = layout.box()
        box.label(text="Look:", icon='LAMP_SUN')
        row = box.row(align=True)
        row.prop(ls, "intensity")
        row.prop(ls, "width")
        box.prop(ls, "color")
        box.prop(ls, "flash_distance")
        box.prop(ls, "use_preview")
        box.prop(ls, "use_sound", text="Thunder Sound")
        box.label(text="The screen flash needs World > Rain on", icon='INFO')


classes = (
    DATA_PT_empty,
    DATA_PT_reverb_area,
    DATA_PT_lightning,
)

if __name__ == "__main__":  # only for live edit.
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)
