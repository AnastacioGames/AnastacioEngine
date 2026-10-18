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


def _close_text(context, text):
    """Remove the text from the file; the editor shows the next tab."""
    texts = list(bpy.data.texts)
    st = context.space_data
    if st and st.type == 'TEXT_EDITOR' and st.text == text:
        index = texts.index(text)
        others = texts[:index] + texts[index + 1:]
        st.text = others[min(index, len(others) - 1)] if others else None
    bpy.data.texts.remove(text)


def _loses_work(text):
    # a text only in the .range, or with changes not saved to its file, is lost when closed
    return not text.filepath or text.is_dirty


class TEXT_OT_tab_close(bpy.types.Operator):
    bl_idname = "text.tab_close"
    bl_label = "Close"
    bl_description = "Close this text (the file on disk is kept)"
    bl_options = {'INTERNAL', 'UNDO'}

    text_name = bpy.props.StringProperty()
    others = bpy.props.BoolProperty(options={'HIDDEN'})

    def targets(self):
        if self.others:
            return [t for t in bpy.data.texts if t.name != self.text_name]
        text = bpy.data.texts.get(self.text_name)
        return [text] if text else []

    def invoke(self, context, event):
        if any(_loses_work(t) for t in self.targets()):
            return context.window_manager.invoke_confirm(self, event)
        return self.execute(context)

    def execute(self, context):
        targets = self.targets()
        for text in targets:
            _close_text(context, text)
        st = context.space_data
        if self.others and self.text_name in bpy.data.texts and st and st.type == 'TEXT_EDITOR':
            st.text = bpy.data.texts[self.text_name]
        return {'FINISHED'} if targets else {'CANCELLED'}


class TEXT_OT_tab_delete_file(bpy.types.Operator):
    bl_idname = "text.tab_delete_file"
    bl_label = "Delete File"
    bl_description = "Close this text and delete its file from the disk (cannot be undone)"
    bl_options = {'INTERNAL'}

    text_name = bpy.props.StringProperty()

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        import os
        text = bpy.data.texts.get(self.text_name)
        if text is None or not text.filepath:
            return {'CANCELLED'}
        path = bpy.path.abspath(text.filepath)
        try:
            if os.path.isfile(path):
                os.remove(path)
        except OSError as exc:
            self.report({'ERROR'}, "Could not delete %s: %s" % (path, exc))
            return {'CANCELLED'}
        _close_text(context, text)
        self.report({'INFO'}, "Deleted %s" % path)
        return {'FINISHED'}


def _text_open(context):
    st = context.space_data
    return st is not None and st.type == 'TEXT_EDITOR' and st.text is not None


class TEXT_MT_floating_bar(Menu):
    """Fixed floating buttons at the bottom right of the Text Editor (drawn by space_text.c)"""
    bl_label = ""

    @classmethod
    def poll(cls, context):
        return _text_open(context)

    def draw(self, context):
        layout = self.layout
        layout.operator("ed.undo", text="", icon='LOOP_BACK')
        layout.operator("ed.redo", text="", icon='LOOP_FORWARDS')
        layout.separator()
        layout.operator("text.cut", text="", icon='CUT')
        layout.operator("text.copy", text="", icon='COPYDOWN')
        layout.operator("text.paste", text="", icon='PASTEDOWN')
        layout.separator()
        layout.operator("text.start_find", text="", icon='VIEWZOOM')
        layout.separator()
        props = layout.operator("wm.context_cycle_int", text="", icon='ZOOMOUT')
        props.data_path = "space_data.font_size"
        props.reverse = True
        props = layout.operator("wm.context_cycle_int", text="", icon='ZOOMIN')
        props.data_path = "space_data.font_size"
        props.reverse = False
        layout.separator()
        layout.operator("text.save", text="Save", icon='FILE_TICK')


class TEXT_MT_floating_bar_context(Menu):
    """Floating buttons for the kind of text open, above the fixed ones"""
    bl_label = ""

    @classmethod
    def poll(cls, context):
        return _text_open(context)

    def draw(self, context):
        layout = self.layout
        name = context.space_data.text.name.lower()
        if name.endswith(".srt"):
            layout.label(text="Subtitle")
            layout.operator("text.srt_add", text="Add", icon='ZOOMIN')
            layout.operator("text.srt_split", text="", icon='ALIGN')
            layout.operator("text.srt_merge", text="", icon='AUTOMERGE_ON')
            layout.separator()
            for delta, label in ((-0.1, "-0.1 s"), (0.1, "+0.1 s")):
                props = layout.operator("text.srt_time", text=label)
                props.edge = 'BOTH'
                props.delta = delta
            layout.separator()
            layout.operator("text.srt_style", text="", icon='COLOR').style = 'COLOR'
            layout.operator("text.srt_style", text="", icon='TRIA_UP_BAR').style = 'TOP'
            layout.separator()
            layout.operator("text.srt_check", text="Check", icon='VIEWZOOM')
        else:
            layout.label(text="Code")
            layout.operator("text.comment", text="", icon='SYNTAX_OFF')
            layout.operator("text.uncomment", text="", icon='SYNTAX_ON')
            layout.operator("text.unindent", text="", icon='BACK')
            layout.operator("text.indent", text="", icon='FORWARD')
            if name.endswith(".py"):
                layout.separator()
                layout.operator("text.run_script", text="Run", icon='PLAY')


class WM_MT_button_context(Menu):
    """Extra items of the right click menu of a button (here: the Text Editor tabs)"""
    bl_label = ""

    def draw(self, context):
        op = getattr(context, "button_operator", None)
        if op is None or op.rna_type.identifier != "TEXT_OT_switch":
            return
        name = op.text_name
        text = bpy.data.texts.get(name)
        if text is None:
            return
        layout = self.layout
        layout.separator()
        layout.operator("text.tab_close", text="Close", icon='X').text_name = name
        sub = layout.row()
        sub.enabled = len(bpy.data.texts) > 1
        props = sub.operator("text.tab_close", text="Close Others", icon='PANEL_CLOSE')
        props.text_name = name
        props.others = True
        sub = layout.row()
        sub.enabled = bool(text.filepath)
        sub.operator("text.tab_delete_file", text="Delete File...", icon='CANCEL').text_name = name


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

        if context.area.show_header_menus:
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
        st = context.space_data

        # line numbers, word wrap and syntax colors are always on (space_text.c), no toggles
        box = self.layout.box()
        box.prop(st, "show_line_highlight")
        row = box.row()
        row.prop(st, "show_margin", text="Margin")
        sub = row.row()
        sub.active = st.show_margin
        sub.prop(st, "margin_column", text="Column")


class TEXT_PT_properties(Panel):
    bl_space_type = 'TEXT_EDITOR'
    bl_region_type = 'UI'
    bl_category = "Text"
    bl_label = "Editor"

    def draw(self, context):
        st = context.space_data
        text = st.text

        box = self.layout.box()
        col = box.column(align=True)
        col.prop(st, "font_size")
        col.prop(st, "tab_width")
        col = box.column()
        if text:
            col.prop(text, "use_tabs_as_spaces")
        col.prop(st, "use_live_edit")


class TEXT_PT_find(Panel):
    bl_space_type = 'TEXT_EDITOR'
    bl_region_type = 'UI'
    bl_category = "Text"
    bl_label = "Find & Replace"

    def draw(self, context):
        st = context.space_data

        box = self.layout.box()
        col = box.column(align=True)
        row = col.row(align=True)
        row.prop(st, "find_text", text="", icon='VIEWZOOM')
        row.operator("text.find_set_selected", text="", icon='EYEDROPPER')
        col.operator("text.find")

        col = box.column(align=True)
        row = col.row(align=True)
        row.prop(st, "replace_text", text="", icon='ARROW_LEFTRIGHT')
        row.operator("text.replace_set_selected", text="", icon='EYEDROPPER')
        col.operator("text.replace")

        row = box.row(align=True)
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


class TEXT_MT_templates_glsl(Menu):
    bl_label = "2D Filters (GLSL)"

    def draw(self, context):
        self.path_menu(
            bpy.utils.script_paths("templates_glsl"),
            "text.open",
            props_default={"internal": True},
        )


class TEXT_MT_templates(Menu):
    bl_label = "Templates"

    def draw(self, context):
        layout = self.layout
        layout.menu("TEXT_MT_templates_components")
        layout.menu("TEXT_MT_templates_glsl")


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
    TEXT_OT_tab_close,
    TEXT_OT_tab_delete_file,
    WM_MT_button_context,
    TEXT_MT_floating_bar,
    TEXT_MT_floating_bar_context,
    TEXT_OT_switch,
    TEXT_HT_header,
    TEXT_MT_edit,
    TEXT_MT_editor_menus,
    TEXT_PT_view,
    TEXT_PT_properties,
    TEXT_PT_find,
    TEXT_MT_view,
    TEXT_MT_text,
    TEXT_MT_templates,
    TEXT_MT_templates_components,
    TEXT_MT_templates_glsl,
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
