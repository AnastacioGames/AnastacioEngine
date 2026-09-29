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

        col = layout.column()
        col.prop(ra, "preset")
        col.prop(ra, "shape")
        col.prop(ob, "empty_draw_size", text="Size")
        col.prop(ra, "inner_factor", slider=True)
        col.prop(ra, "priority")

        row = layout.row(align=True)
        row.prop(ra, "use_filter")
        sub = row.row(align=True)
        sub.active = ra.use_filter
        sub.prop(ra, "filter_type", text="")

        layout.label(text="Affects 3D speakers while the active camera is inside the area", icon='INFO')


class DATA_PT_reverb_area_advanced(DataButtonsPanel, Panel):
    bl_label = "Reverb Area: Advanced"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return DataButtonsPanel.poll(context) and context.object.use_reverb_area

    def draw(self, context):
        layout = self.layout

        ra = context.object.reverb_area

        layout.label(text="Editing any value switches Behavior to Custom")

        split = layout.split()
        col = split.column(align=True)
        col.label(text="Reverb:")
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

        col = layout.column(align=True)
        col.active = ra.use_filter
        col.label(text="Filter:")
        row = col.row(align=True)
        row.prop(ra, "filter_gain", text="Gain")
        row.prop(ra, "filter_gain_lf", text="LF")
        row.prop(ra, "filter_gain_hf", text="HF")


classes = (
    DATA_PT_empty,
    DATA_PT_reverb_area,
    DATA_PT_reverb_area_advanced,
)

if __name__ == "__main__":  # only for live edit.
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)
