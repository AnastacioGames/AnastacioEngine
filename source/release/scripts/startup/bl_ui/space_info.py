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
from bpy.types import Header, Menu


class INFO_HT_header(Header):
    bl_space_type = 'INFO'

    def draw(self, context):
        layout = self.layout

        window = context.window
        scene = context.scene
        rd = scene.render

        row = layout.row(align=True)

        INFO_MT_editor_menus.draw_collapsible(context, layout)

        if window.screen.show_fullscreen:
            layout.operator("screen.back_to_previous", icon='SCREEN_BACK', text="Back to Previous")
        else:
            row = layout.row(align=True)
            row.template_screen_tabs()
            row.operator("screen.new", text="", icon='ZOOMIN')
            row.operator("screen.delete", text="", icon='X')
            # Scene add/copy/delete moved into the Outliner header, next to
            # the "Scenes" root (see OUTLINER_MT_scene_add in
            # space_outliner.py). Deleting a scene is done via right-click
            # on the scene entry in the Outliner.
            # layout.template_ID(context.screen, "scene", new="scene.new", unlink="scene.delete")

        layout.separator_spacer()

        layout.operator("wm.splash", text="", icon='BLENDER', emboss=False)
        layout.operator("wm.splash_about", text="Range Engine - Custom Version", emboss=False)

        layout.separator_spacer()

        #if rd.has_multiple_engines: # Moved to properties_render
        #    layout.prop(rd, "engine", text="")

        #layout.separator(factor=1)

        #row = layout.row(align=1)

        if bpy.app.autoexec_fail is True and bpy.app.autoexec_fail_quiet is False:
            row.label("Auto-run disabled", icon='ERROR')
            if bpy.data.is_saved:
                props = row.operator("wm.revert_mainfile", icon='SCREEN_BACK', text="Reload Trusted")
                props.use_scripts = True

            row.operator("script.autoexec_warn_clear", text="Ignore")

            # include last so text doesn't push buttons out of the header
            row.label(bpy.app.autoexec_fail_message)
            return

        layout.separator_spacer()

        layout.template_running_jobs()
        layout.template_reports_banner()

        layout.separator(factor=1)

        row = layout.row(align=1)


class INFO_MT_editor_menus(Menu):
    bl_idname = "INFO_MT_editor_menus"
    bl_label = ""

    def draw(self, context):
        self.draw_menus(self.layout, context)

    @staticmethod
    def draw_menus(layout, context):
        scene = context.scene
        rd = scene.render

        layout.menu("INFO_MT_file")

        if rd.use_game_engine:
            layout.menu("INFO_MT_game")
        else:
            layout.menu("INFO_MT_render")

        layout.menu("INFO_MT_window")
        layout.menu("INFO_MT_help")


class INFO_MT_file(Menu):
    bl_label = "File"

    def draw(self, context):
        layout = self.layout

        layout.operator_context = 'INVOKE_AREA'
        layout.operator("wm.read_homefile", text="New File", icon='NEW')
        layout.operator("wm.create_project", text="Create Project", icon='FILE_FOLDER')
        layout.operator("wm.open_mainfile", text="Open Project", icon='FILE_FOLDER')
        layout.menu("INFO_MT_file_open_recent", text="Open Recent Project", icon='OPEN_RECENT')
        layout.operator("wm.revert_mainfile", icon='FILE_REFRESH')
        layout.operator("wm.recover_last_session", icon='RECOVER_LAST')
        layout.operator("wm.recover_auto_save", text="Recover Auto Save...", icon='RECOVER_AUTO')

        layout.separator(factor=1)

        layout.operator_context = 'EXEC_AREA' if context.blend_data.is_saved else 'INVOKE_AREA'
        layout.operator("wm.save_mainfile", text="Save Project", icon='FILE_TICK')

        layout.operator_context = 'INVOKE_AREA'
        layout.operator("wm.save_as_mainfile", text="Save Project As...", icon='SAVE_AS')
        layout.operator_context = 'INVOKE_AREA'
        layout.operator("wm.save_as_mainfile", text="Save Project Copy", icon='SAVE_COPY').copy = True

        layout.separator(factor=1)

        layout.operator("screen.settings_show", text="Engine Settings", icon='PREFERENCES')

        layout.operator_context = 'INVOKE_AREA'
        layout.operator("wm.save_homefile", icon='SAVE_PREFS')
        layout.operator("wm.read_factory_settings", icon='LOAD_FACTORY')

        if any(bpy.utils.app_template_paths()):
            app_template = context.user_preferences.app_template
            if app_template:
                layout.operator(
                    "wm.read_factory_settings",
                    text="Load Factory Template Settings",
                    icon='LOAD_FACTORY',
                ).app_template = app_template
            del app_template

        layout.menu("USERPREF_MT_app_templates", icon='FILE_BLEND')

        layout.separator(factor=1)

        layout.operator_context = 'INVOKE_AREA'
        layout.operator("wm.link", text="Link", icon='LINK_BLEND')
        layout.operator("wm.append", text="Append", icon='APPEND_BLEND')
        layout.menu("INFO_MT_file_previews")

        layout.separator(factor=1)

        layout.menu("INFO_MT_file_import", icon='IMPORT')
        layout.menu("INFO_MT_file_export", icon='EXPORT')
        import sys
        if sys.platform == "win32":
            layout.operator("wm.export_with_rangearmor", text="Export Game With RANGEARMOR", icon='RANGEARMOR')
        layout.operator_context = 'INVOKE_AREA'
        layout.operator("wm.save_as_mainfile_protected", text="Save .Range Protected File", icon='RANGEARMOR').copy = True

        layout.separator(factor=1)

        layout.menu("INFO_MT_file_external_data", icon='EXTERNAL_DATA')
        layout.operator("wm.blend_strings_utf8_validate", text="Validade .range strings", icon='FILE_BLEND')

        layout.separator(factor=1)

        layout.operator_context = 'EXEC_AREA'
        if bpy.data.is_dirty and context.user_preferences.view.use_quit_dialog:
            layout.operator_context = 'INVOKE_SCREEN'  # quit dialog
        layout.operator("wm.quit_blender", text="Exit Engine", icon='QUIT')


class INFO_MT_file_import(Menu):
    bl_idname = "INFO_MT_file_import"
    bl_label = "Import"

    def draw(self, context):
        if bpy.app.build_options.collada:
            self.layout.operator("wm.collada_import", text="Collada (Default) (.dae)")
        if bpy.app.build_options.alembic:
            self.layout.operator("wm.alembic_import", text="Alembic (.abc)")


class INFO_MT_file_export(Menu):
    bl_idname = "INFO_MT_file_export"
    bl_label = "Export"

    def draw(self, context):
        if bpy.app.build_options.collada:
            self.layout.operator("wm.collada_export", text="Collada (Default) (.dae)")
        if bpy.app.build_options.alembic:
            self.layout.operator("wm.alembic_export", text="Alembic (.abc)")


class INFO_MT_file_external_data(Menu):
    bl_label = "External Data"

    def draw(self, context):
        layout = self.layout

        icon = 'CHECKBOX_HLT' if bpy.data.use_autopack else 'CHECKBOX_DEHLT'
        layout.operator("file.autopack_toggle", icon=icon)

        layout.separator(factor=1)

        pack_all = layout.row()
        pack_all.operator("file.pack_all")
        pack_all.active = not bpy.data.use_autopack

        unpack_all = layout.row()
        unpack_all.operator("file.unpack_all")
        unpack_all.active = not bpy.data.use_autopack

        layout.separator(factor=1)

        layout.operator("file.make_paths_relative")
        layout.operator("file.make_paths_absolute")
        layout.operator("file.report_missing_files")
        layout.operator("file.find_missing_files")


class INFO_MT_file_previews(Menu):
    bl_label = "Data Previews"

    def draw(self, context):
        layout = self.layout

        layout.operator("wm.previews_ensure")
        layout.operator("wm.previews_batch_generate")

        layout.separator(factor=1)

        layout.operator("wm.previews_clear")
        layout.operator("wm.previews_batch_clear")


class INFO_MT_game(Menu):
    bl_label = "Game"

    def draw(self, context):
        layout = self.layout

        gs = context.scene.game_settings

        layout.operator("view3d.game_start", icon="PLAY")

        layout.separator(factor=1)

        layout.prop(gs, "show_framerate_profile", text="Show Profile")
        layout.prop(gs, "show_render_queries")
        layout.prop(gs, "use_deprecation_warnings")
        layout.separator(factor=1)
        layout.prop(gs, "show_debug_mode", text="Debug Mode")
        layout.prop(gs, "use_auto_start")
        layout.menu("INFO_MT_game_show_debug")


class INFO_MT_game_show_debug(Menu):
    bl_label = "Show Debug"

    def draw(self, context):
        layout = self.layout

        gs = context.scene.game_settings

        layout.prop(gs, "show_debug_properties")
        layout.prop(gs, "show_physics_visualization")

        layout.separator(factor=1)
        layout.prop_menu_enum(gs, "show_bounding_box")
        layout.prop_menu_enum(gs, "show_armatures")
        layout.prop_menu_enum(gs, "show_camera_frustum")
        layout.prop_menu_enum(gs, "show_shadow_frustum")


class INFO_MT_render(Menu):
    bl_label = "Render"

    def draw(self, context):
        layout = self.layout

        layout.operator("render.render", text="Render Image", icon='RENDER_STILL').use_viewport = True
        props = layout.operator("render.render", text="Render Animation", icon='RENDER_ANIMATION')
        props.animation = True
        props.use_viewport = True

        layout.separator(factor=1)

        layout.operator("render.opengl", text="OpenGL Render Image")
        layout.operator("render.opengl", text="OpenGL Render Animation").animation = True
        layout.menu("INFO_MT_opengl_render")

        layout.separator(factor=1)

        layout.operator("render.view_show")
        layout.operator("render.play_rendered_anim", icon='PLAY')


class INFO_MT_opengl_render(Menu):
    bl_label = "OpenGL Render Options"

    def draw(self, context):
        layout = self.layout

        rd = context.scene.render
        layout.prop(rd, "use_antialiasing")
        layout.prop(rd, "use_full_sample")

        layout.prop_menu_enum(rd, "antialiasing_samples")
        layout.prop_menu_enum(rd, "alpha_mode")


class INFO_MT_window(Menu):
    bl_label = "Window"

    def draw(self, context):
        import sys

        layout = self.layout

        layout.operator("wm.window_duplicate", icon="SPLITSCREEN")
        layout.operator("wm.window_fullscreen_toggle", icon='FULLSCREEN_ENTER')

        layout.separator(factor=1)

        layout.operator("screen.screenshot", icon="CAMERA_DATA")

        if sys.platform[:3] == "win":
            layout.separator(factor=1)
            layout.operator("wm.console_toggle", icon='CONSOLE')

        if context.scene.render.use_multiview:
            layout.separator(factor=1)
            layout.operator("wm.set_stereo_3d", icon='CAMERA_STEREO')


class INFO_MT_help(Menu):
    bl_label = "About"

    def draw(self, context):
        layout = self.layout

        layout.operator(
            "wm.url_open", text="RanGE - Python API", icon='HELP',
        ).url = "https://rangeengine.tech/RangeDoc_Build/html/"
        layout.separator(factor=1)

        layout.operator(
            "wm.url_open", text="RanGE - Website", icon='URL',
        ).url = "https://rangeengine.tech"
        

        #layout.operator("wm.operator_cheat_sheet", icon='TEXT')
        layout.operator("wm.sysinfo", icon='TEXT')
        
        layout.separator(factor=1)
        layout.operator("wm.splash_about", text="Anastacio Engine About", icon="BLENDER")
        layout.separator(factor=1)
        

        '''layout.operator("wm.splash", icon='BLENDER')'''


classes = (
    INFO_HT_header,
    INFO_MT_editor_menus,
    INFO_MT_file,
    INFO_MT_file_import,
    INFO_MT_file_export,
    INFO_MT_file_external_data,
    INFO_MT_file_previews,
    INFO_MT_game,
    INFO_MT_game_show_debug,
    INFO_MT_render,
    INFO_MT_opengl_render,
    INFO_MT_window,
    INFO_MT_help,
)

if __name__ == "__main__":  # only for live edit.
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)
