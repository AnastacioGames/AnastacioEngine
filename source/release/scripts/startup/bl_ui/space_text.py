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

# <pep8-80 compliant>
import bpy
from bpy.types import Header, Menu, Panel
from bpy.app.translations import pgettext_iface as iface_


class TEXT_OT_switch(bpy.types.Operator):
    bl_idname = "text.switch"
    bl_label = "Switch Text"
    bl_description = "Make this text the active one in the editor"
    bl_options = {'INTERNAL'}

    text_name: bpy.props.StringProperty()

    def execute(self, context):
        text = bpy.data.texts.get(self.text_name)
        if text is None:
            return {'CANCELLED'}
        context.space_data.text = text
        return {'FINISHED'}


class TEXT_HT_header(Header):
    bl_space_type = 'TEXT_EDITOR'

    def draw(self, context):
        layout = self.layout

        st = context.space_data
        text = st.text

        st.show_line_numbers = True
        st.show_word_wrap = True
        st.show_syntax_highlight = True

        row = layout.row(align=True)
        row.template_header()

        TEXT_MT_editor_menus.draw_collapsible(context, layout)

        if text and text.is_modified:
            sub = row.row(align=True)
            sub.alert = True
            sub.operator("text.resolve_conflict", text="", icon='HELP')

        row = layout.row(align=True)
        row.template_ID(st, "text", new="text.new", unlink="text.unlink", open="text.open")

        if context.window_manager.text_editor_show_tabs and len(bpy.data.texts) > 0:
            row = layout.row(align=True)
            for t in bpy.data.texts:
                op = row.operator(
                    "text.switch",
                    text=t.name,
                    depress=(t == text),
                )
                op.text_name = t.name

        if text:
            is_osl = text.name.endswith((".osl", ".osl"))

            if is_osl:
                row = layout.row()
                row.operator("node.shader_script_update")
            else:
                row = layout.row(align=True)
                
                split = text.name.split(".")
                if (len(split) <= 1 or len(split) > 1 and split[1] not in ("vert", "frag")):
                    row.operator("text.run_script", text="", icon="PLAY")
                else:
                    row.operator("text.run_shader_script", text="", icon="FILE_REFRESH")

                row = layout.row()
                row.active = text.name.endswith(".py")
                row.prop(text, "use_module")

            row = layout.row()
            if text.filepath:
                if text.is_dirty:
                    row.label(
                        iface_(f"File: *{text.filepath:s} (unsaved)"),
                        translate=False,
                    )
                else:
                    row.label(
                        iface_(f"File: {text.filepath:s}"),
                        translate=False,
                    )
            else:
                row.label(
                    "Text: External"
                    if text.library
                    else "Text: Internal"
                )


class TEXT_MT_editor_menus(Menu):
    bl_idname = "TEXT_MT_editor_menus"
    bl_label = ""

    def draw(self, context):
        self.draw_menus(self.layout, context)

    @staticmethod
    def draw_menus(layout, context):
        st = context.space_data
        text = st.text

        layout.menu("TEXT_MT_view")
        layout.menu("TEXT_MT_text")

        if text:
            layout.menu("TEXT_MT_edit")
            layout.menu("TEXT_MT_format")

        layout.menu("TEXT_MT_templates")


# Sidebar (N panel), organized in the Blender 2.8 style.

class TEXT_PT_view(Panel):
    bl_space_type = 'TEXT_EDITOR'
    bl_region_type = 'UI'
    bl_category = "Text"
    bl_label = "View"

    def draw(self, context):
        layout = self.layout

        st = context.space_data

        # These properties carry an RNA icon, so they are drawn as compact
        # icon toggles in one row instead of full-width buttons.
        row = layout.row(align=True)
        row.prop(st, "show_line_numbers", text="")
        row.prop(st, "show_word_wrap", text="")
        row.prop(st, "show_syntax_highlight", text="")

        layout.prop(st, "show_line_highlight")


class TEXT_PT_view_margin(Panel):
    bl_space_type = 'TEXT_EDITOR'
    bl_region_type = 'UI'
    bl_category = "Text"
    bl_label = "Margin"
    bl_parent_id = "TEXT_PT_view"
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        st = context.space_data
        self.layout.prop(st, "show_margin", text="")

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        st = context.space_data

        col = layout.column()
        col.active = st.show_margin
        col.prop(st, "margin_column", text="Column")


class TEXT_PT_properties(Panel):
    bl_space_type = 'TEXT_EDITOR'
    bl_region_type = 'UI'
    bl_category = "Text"
    bl_label = "Editor"

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        st = context.space_data
        text = st.text

        col = layout.column(align=True)
        col.prop(st, "font_size")
        col.prop(st, "tab_width")

        # Checkboxes read better without the split label column.
        col = layout.column()
        col.use_property_split = False
        if text:
            col.prop(text, "use_tabs_as_spaces")
        col.prop(st, "use_live_edit")


class TEXT_PT_find(Panel):
    bl_space_type = 'TEXT_EDITOR'
    bl_region_type = 'UI'
    bl_category = "Text"
    bl_label = "Find & Replace"

    def draw(self, context):
        layout = self.layout

        st = context.space_data

        # find
        col = layout.column(align=True)
        row = col.row(align=True)
        row.prop(st, "find_text", text="", icon='VIEWZOOM')
        row.operator("text.find_set_selected", text="", icon='EYEDROPPER')
        col.operator("text.find")

        layout.separator()

        # replace
        col = layout.column(align=True)
        row = col.row(align=True)
        row.prop(st, "replace_text", text="", icon='ARROW_LEFTRIGHT')
        row.operator("text.replace_set_selected", text="", icon='EYEDROPPER')
        col.operator("text.replace")

        layout.separator()

        # settings
        row = layout.row(align=True)
        row.prop(st, "use_match_case", text="Case", toggle=True)
        row.prop(st, "use_find_wrap", text="Wrap", toggle=True)
        row.prop(st, "use_find_all", text="All", toggle=True)


class TEXT_MT_view(Menu):
    bl_label = "View"

    def draw(self, context):
        layout = self.layout

        layout.operator("text.properties", icon='MENU_PANEL')

        layout.separator(factor=1)

        layout.prop(context.window_manager, "text_editor_show_tabs", text="Show Tabs")

        layout.separator(factor=1)

        layout.operator("text.move",
                        text="Top of File",
                        ).type = 'FILE_TOP'
        layout.operator("text.move",
                        text="Bottom of File",
                        ).type = 'FILE_BOTTOM'

        layout.separator(factor=1)

        layout.operator("screen.area_dupli")
        layout.operator("screen.screen_full_area")
        layout.operator("screen.screen_full_area", text="Toggle Fullscreen Area").use_hide_panels = True


class TEXT_MT_text(Menu):
    bl_label = "Text"

    def draw(self, context):
        layout = self.layout

        st = context.space_data
        text = st.text

        layout.operator("text.new")
        layout.operator("text.open")

        if text:
            layout.operator("text.reload")

            layout.column()
            layout.operator("text.save")
            layout.operator("text.save_as")

            if text.filepath:
                layout.operator("text.make_internal")

            layout.column()
            layout.operator("text.run_script")


class TEXT_MT_templates_components(Menu):
    bl_label = "Components"

    def draw(self, context):
        self.path_menu(
            bpy.utils.script_paths("templates_components"),
            "text.open",
            props_default={"internal": True},
        )


class TEXT_MT_templates(Menu):
    bl_label = "Templates"

    def draw(self, context):
        layout = self.layout
        layout.menu("TEXT_MT_templates_components")


class TEXT_MT_edit_select(Menu):
    bl_label = "Select"

    def draw(self, context):
        layout = self.layout

        layout.operator("text.select_all")
        layout.operator("text.select_line")


class TEXT_MT_format(Menu):
    bl_label = "Format"

    def draw(self, context):
        layout = self.layout

        layout.operator("text.indent")
        layout.operator("text.unindent")

        layout.separator(factor=1)

        layout.operator("text.comment")
        layout.operator("text.uncomment")

        layout.separator(factor=1)

        layout.operator_menu_enum("text.convert_whitespace", "type")


class TEXT_MT_edit_to3d(Menu):
    bl_label = "Text To 3D Object"

    def draw(self, context):
        layout = self.layout

        layout.operator("text.to_3d_object",
                        text="One Object",
                        ).split_lines = False
        layout.operator("text.to_3d_object",
                        text="One Object Per Line",
                        ).split_lines = True


class TEXT_MT_edit(Menu):
    bl_label = "Edit"

    @classmethod
    def poll(cls, context):
        return (context.space_data.text)

    def draw(self, context):
        layout = self.layout

        layout.operator("ed.undo")
        layout.operator("ed.redo")

        layout.separator(factor=1)

        layout.operator("text.cut")
        layout.operator("text.copy")
        layout.operator("text.paste")
        layout.operator("text.duplicate_line")

        layout.separator(factor=1)

        layout.operator("text.move_lines",
                        text="Move line(s) up").direction = 'UP'
        layout.operator("text.move_lines",
                        text="Move line(s) down").direction = 'DOWN'

        layout.separator(factor=1)

        layout.menu("TEXT_MT_edit_select")

        layout.separator(factor=1)

        layout.operator("text.jump")
        layout.operator("text.start_find", text="Find...")
        layout.operator("text.autocomplete")

        layout.separator(factor=1)

        layout.menu("TEXT_MT_edit_to3d")


class TEXT_MT_toolbox(Menu):
    bl_label = ""

    def draw(self, context):
        layout = self.layout

        layout.operator_context = 'INVOKE_DEFAULT'

        layout.operator("text.cut")
        layout.operator("text.copy")
        layout.operator("text.paste")

        layout.separator(factor=1)

        layout.operator("text.run_script")


classes = (
    TEXT_OT_switch,
    TEXT_HT_header,
    TEXT_MT_edit,
    TEXT_MT_editor_menus,
    TEXT_PT_view,
    TEXT_PT_view_margin,
    TEXT_PT_properties,
    TEXT_PT_find,
    TEXT_MT_view,
    TEXT_MT_text,
    TEXT_MT_templates,
    TEXT_MT_templates_components,
    TEXT_MT_edit_select,
    TEXT_MT_format,
    TEXT_MT_edit_to3d,
    TEXT_MT_toolbox,
)

bpy.types.WindowManager.text_editor_show_tabs = bpy.props.BoolProperty(
    name="Show Tabs",
    description="Show a row of buttons in the Text Editor header to quickly switch between open texts",
    default=True,
)

if __name__ == "__main__":  # only for live edit.
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)
