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
from bpy.types import Header, Menu, Operator
from bpy_extras.io_utils import ExportHelper, ImportHelper


GUIDE = (
    ("Getting Started", 'INFO', (
        ("Click New in the bar", "Create a map"),
        ("Insert", "Add an idea inside the selected one"),
        ("Enter", "Add an idea next to the selected one"),
        ("F2 or double click", "Rename the idea"),
    )),
    ("Mouse", 'RESTRICT_SELECT_OFF', (
        ("Click", "Select an idea"),
        ("Shift + Click", "Add ideas to a group"),
        ("Drag an idea", "Move it to another place"),
        ("Right Click", "Open the idea menu"),
        ("Wheel / Middle Mouse", "Zoom and move the view"),
    )),
    ("Keyboard", 'FILE_TEXT', (
        ("Arrows", "Walk between ideas"),
        ("Space", "Fold or unfold a branch"),
        ("Delete", "Delete the idea"),
        ("Ctrl + C / X / V", "Copy, cut and paste branches"),
        ("Ctrl + F, then F3", "Find ideas"),
        ("Home", "Show the whole map"),
    )),
    ("Marks", 'SOLO_ON', (
        ("T", "Tool panel with the map commands"),
        ("N", "Side panel with the idea settings"),
        ("Shift + T", "Task: to do, done, none"),
        ("I", "Choose an icon of the engine"),
        ("Shift + N", "Write a note"),
        ("L, then O", "Link to an object, scene or text and open it"),
    )),
)


class MindMapMenu:
    bl_space_type = 'MINDMAP_EDITOR'

    def region_layout(self):
        layout = self.layout
        layout.operator_context = 'INVOKE_REGION_WIN'
        return layout


class MINDMAP_MT_map(MindMapMenu, Menu):
    bl_label = "Map"

    def draw(self, context):
        layout = self.region_layout()
        layout.operator("mindmap.new", icon='NEW')
        layout.operator("mindmap.import_map", text="Import .mm...", icon='IMPORT')
        layout.separator()
        layout.operator("mindmap.export_map", text="Export .mm...", icon='EXPORT')
        layout.operator("mindmap.export_png", text="Export PNG...", icon='IMAGE_DATA')


class MINDMAP_MT_edit(MindMapMenu, Menu):
    bl_label = "Edit"

    def draw(self, context):
        layout = self.region_layout()
        layout.operator("ed.undo", icon='LOOP_BACK')
        layout.operator("ed.redo", icon='LOOP_FORWARDS')
        layout.separator()
        layout.operator("mindmap.cut", icon='NONE')
        layout.operator("mindmap.copy", icon='COPYDOWN')
        layout.operator("mindmap.paste", icon='PASTEDOWN')
        layout.separator()
        layout.operator("mindmap.find", icon='VIEWZOOM')
        layout.operator("mindmap.find_next")


class MINDMAP_MT_idea(MindMapMenu, Menu):
    bl_label = "Idea"

    def draw(self, context):
        layout = self.region_layout()
        layout.operator("mindmap.add_child", icon='ZOOMIN')
        layout.operator("mindmap.add_sibling")
        layout.operator("mindmap.edit", text="Rename")
        layout.operator("mindmap.delete", icon='X')
        layout.separator()
        layout.operator_menu_enum("mindmap.set_color", "color", text="Color")
        layout.operator_menu_enum("mindmap.set_background", "color", text="Box Color")
        layout.operator_menu_enum("mindmap.set_shape", "shape", text="Shape")
        layout.operator_menu_enum("mindmap.set_icon", "icon", text="Icon")
        layout.operator("mindmap.set_engine_icon", text="Engine Icon...")
        layout.operator("mindmap.edit_note", text="Note...")
        layout.operator("mindmap.cycle_task")
        layout.separator()
        layout.operator("mindmap.set_link", text="Link...", icon='LINKED')
        layout.operator("mindmap.open_link")
        layout.operator("mindmap.clear_link")


class MINDMAP_MT_view(MindMapMenu, Menu):
    bl_label = "View"

    def draw(self, context):
        layout = self.region_layout()
        layout.operator("mindmap.toolshelf")
        layout.operator("mindmap.properties")
        layout.separator()
        layout.operator("mindmap.view_all")
        layout.operator("mindmap.toggle_fold")


class MINDMAP_MT_help(MindMapMenu, Menu):
    bl_label = "Help"

    def draw(self, context):
        self.layout.operator("mindmap.quick_guide", icon='QUESTION')


class MINDMAP_HT_header(Header):
    bl_space_type = 'MINDMAP_EDITOR'

    def draw(self, context):
        layout = self.layout
        layout.row(align=True).template_header()
        space = context.space_data
        row = layout.row(align=True)
        row.menu("MINDMAP_MT_map")
        if space.text:
            row.menu("MINDMAP_MT_edit")
            row.menu("MINDMAP_MT_idea")
            row.menu("MINDMAP_MT_view")
        row.menu("MINDMAP_MT_help")
        layout.template_ID(space, "text", new="mindmap.new", open="mindmap.import_map")
        if space.text:
            layout.operator("mindmap.export_map", text="Export .mm", icon='EXPORT')
            layout.operator("mindmap.export_png", text="PNG", icon='IMAGE_DATA')
            layout.prop(space, "show_hints", toggle=True)


class MINDMAP_OT_quick_guide(Operator):
    """Show how to use the mind map"""
    bl_idname = "mindmap.quick_guide"
    bl_label = "Quick Guide"

    def execute(self, context):
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=520)

    def draw(self, context):
        layout = self.layout
        layout.label(text="Quick Guide", icon='QUESTION')
        for title, icon, rows in GUIDE:
            box = layout.box()
            box.label(text=title, icon=icon)
            column = box.column(align=True)
            for keys, action in rows:
                split = column.split(factor=0.38)
                split.label(text=keys)
                split.label(text=action)


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


class MINDMAP_OT_export_png(Operator, ExportHelper):
    """Save the whole map as a PNG image"""
    bl_idname = "mindmap.export_png"
    bl_label = "Export Mind Map Image"

    filename_ext = ".png"
    filter_glob = StringProperty(default="*.png", options={'HIDDEN'})

    @classmethod
    def poll(cls, context):
        space = context.space_data
        return space and space.type == 'MINDMAP_EDITOR' and space.text

    def execute(self, context):
        return bpy.ops.mindmap.render_png(filepath=self.filepath)


classes = (
    MINDMAP_MT_map,
    MINDMAP_MT_edit,
    MINDMAP_MT_idea,
    MINDMAP_MT_view,
    MINDMAP_MT_help,
    MINDMAP_HT_header,
    MINDMAP_OT_quick_guide,
    MINDMAP_OT_new,
    MINDMAP_OT_import_map,
    MINDMAP_OT_export_map,
    MINDMAP_OT_export_png,
)

if __name__ == "__main__":  # only for live edit.
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)
