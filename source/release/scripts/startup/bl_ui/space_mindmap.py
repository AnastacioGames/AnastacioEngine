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
import os

import bpy
from bpy.props import StringProperty
from bpy.types import Header, Operator
from bpy_extras.io_utils import ExportHelper, ImportHelper


class MINDMAP_HT_header(Header):
    bl_space_type = 'MINDMAP_EDITOR'

    def draw(self, context):
        layout = self.layout
        layout.row(align=True).template_header()
        space = context.space_data
        layout.template_ID(space, "text", new="mindmap.new", open="mindmap.import_map")
        if space.text:
            layout.operator("mindmap.export_map", text="Export .mm", icon='EXPORT')


class MINDMAP_OT_new(Operator):
    """Create a new mind map"""
    bl_idname = "mindmap.new"
    bl_label = "New Mind Map"
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.space_data and context.space_data.type == 'MINDMAP_EDITOR'

    def execute(self, context):
        text = bpy.data.texts.new("Map.mm")
        text.write('<map version="1.0.1">\n<node TEXT="New Map"/>\n</map>\n')
        context.space_data.text = text
        return {'FINISHED'}


class MINDMAP_OT_import_map(Operator, ImportHelper):
    """Open a FreeMind .mm file as a new map"""
    bl_idname = "mindmap.import_map"
    bl_label = "Import Mind Map"
    bl_options = {'UNDO'}

    filename_ext = ".mm"
    filter_glob = StringProperty(default="*.mm", options={'HIDDEN'})

    @classmethod
    def poll(cls, context):
        return context.space_data and context.space_data.type == 'MINDMAP_EDITOR'

    def execute(self, context):
        with open(self.filepath, "rb") as handle:
            data = handle.read()
        try:
            content = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            content = data.decode("cp1252", "replace")
        text = bpy.data.texts.new(os.path.basename(self.filepath))
        text.write(content)
        context.space_data.text = text
        return {'FINISHED'}


class MINDMAP_OT_export_map(Operator, ExportHelper):
    """Save the current map as a FreeMind .mm file"""
    bl_idname = "mindmap.export_map"
    bl_label = "Export Mind Map"

    filename_ext = ".mm"
    filter_glob = StringProperty(default="*.mm", options={'HIDDEN'})

    @classmethod
    def poll(cls, context):
        space = context.space_data
        return space and space.type == 'MINDMAP_EDITOR' and space.text

    def execute(self, context):
        with open(self.filepath, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(context.space_data.text.as_string())
        return {'FINISHED'}


classes = (
    MINDMAP_HT_header,
    MINDMAP_OT_new,
    MINDMAP_OT_import_map,
    MINDMAP_OT_export_map,
)

if __name__ == "__main__":  # only for live edit.
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)
