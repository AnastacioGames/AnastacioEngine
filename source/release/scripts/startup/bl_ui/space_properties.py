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
from bpy.types import Header, Panel


class PROPERTIES_HT_header(Header):
    bl_space_type = 'PROPERTIES'

    def draw(self, context):
        layout = self.layout

        view = context.space_data

        row = layout.row()
        row.template_header()

        top_row = layout.row(align=True)
        top_row.scale_x = 1.3
        top_row.scale_y = 1.3
        top_context = ('RENDER', 'RENDER_LAYER', 'SCENE', 'WORLD', 'CUTSCENE', 'EXPORT')
        valid_flag = view.context_valid_flag
        for item in view.bl_rna.properties["context"].enum_items:
            if item.identifier in top_context and (valid_flag & (1 << item.value)):
                top_row.prop_enum(view, "context", item.identifier, text="")

class PROPERTIES_PT_navigation_bar(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'NAVIGATION_BAR'
    bl_label = "Navigation Bar"
    bl_options = {'HIDE_HEADER'}

    def draw(self, context):
        layout = self.layout

        view = context.space_data

        layout.scale_x = 1.5
        layout.scale_y = 1.4

        col = layout.column(align=True)

        top_context = ('RENDER', 'RENDER_LAYER', 'SCENE', 'WORLD', 'CUTSCENE', 'EXPORT')
        valid_flag = view.context_valid_flag

        for item in view.bl_rna.properties["context"].enum_items:
            if item.identifier in top_context:
                continue
            if valid_flag & (1 << item.value):
                col.prop_enum(view, "context", item.identifier, text="")

classes = (
    PROPERTIES_HT_header,
    PROPERTIES_PT_navigation_bar,
)

if __name__ == "__main__":  # only for live edit.
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)
