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
from bpy.types import Header, Menu, Panel

_header_icons = None


def _cube_icon():
    # Golden cube of the Anastacio Engine logo, next to the Blender icon in the header.
    global _header_icons
    if _header_icons is None:
        import bpy.utils.previews
        _header_icons = bpy.utils.previews.new()
        _header_icons.load("cube", os.path.join(os.path.dirname(__file__), "icons", "anastacio_cube.png"), 'IMAGE')
    return _header_icons["cube"].icon_id


class INFO_HT_header(Header):
    bl_space_type = 'INFO'

    def draw(self, context):
        layout = self.layout

        window = context.window
        scene = context.scene
        rd = scene.render

        row = layout.row(align=True)

        if context.area.show_header_menus:
            INFO_MT_editor_menus.draw_collapsible(context, layout)

        if window.screen.show_fullscreen:
            layout.operator("screen.back_to_previous", icon='SCREEN_BACK', text="Back to Previous")
        # Screen and scene selectors sit in the right corner (end of draw).

        wm = context.window_manager
        if wm.info_show_screen_recorder:
            # Left side, next to the menus, away from the window corner.
            layout.separator(factor=4)
            row = layout.row(align=True)
            if not wm.is_screencast_running:
                # While recording, the red "Recording mm:ss" button (running jobs) stops it.
                row.operator("screen.screencast", text="Rec", icon='REC')
            row.popover(panel="INFO_PT_screen_recorder", text="" if not wm.is_screencast_running else "Rec")

        layout.separator_spacer()

        layout.operator("wm.splash", text="", icon='BLENDER', emboss=False)
        layout.operator("wm.splash_about", text="Anastacio Engine - Custom Version", icon_value=_cube_icon(), emboss=False)

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

        layout.template_running_jobs()
        wm = context.window_manager
        if getattr(wm, "ae_bake_status", ""):  # Bake Lightmap (anastacio_lightmap.py)
            row = layout.row()
            row.ui_units_x = 14
            row.prop(wm, "ae_bake_progress", text=wm.ae_bake_status, slider=True)
        layout.template_reports_banner()

        if not window.screen.show_fullscreen:
            layout.separator(factor=1)
            if context.space_data.show_screen_selector:
                row = layout.row(align=True)
                if context.user_preferences.view.screen_selector == 'CLASSIC':
                    layout.template_ID(window, "screen", new="screen.new", unlink="screen.delete")
                else:
                    row.template_screen_tabs()
                    row.operator("screen.new", text="", icon='ZOOMIN')
                    # Delete via right-click on a tab (context menu).
            # Scene add/copy/delete moved into the Outliner header, next to
            # the "Scenes" root (see OUTLINER_MT_scene_add in
            # space_outliner.py). Deleting a scene is done via right-click
            # on the scene entry in the Outliner.
            if context.space_data.show_scene_selector:
                layout.template_ID(context.screen, "scene", new="scene.new", unlink="scene.delete")

        layout.separator(factor=1)


class INFO_PT_screen_recorder(Panel):
    bl_space_type = 'INFO'
    bl_region_type = 'HEADER'
    bl_label = "Screen Recorder"
    bl_ui_units_x = 12

    def draw(self, context):
        layout = self.layout
        wm = context.window_manager

        layout.label(text="Screen Recorder", icon='REC')

        col = layout.column()
        col.scale_y = 1.4
        if wm.is_screencast_running:
            col.alert = True
            col.operator("screen.screencast", text="Stop Recording", icon='CANCEL')
        else:
            col.operator("screen.screencast", text="Start Recording", icon='REC')
        layout.label(text="Shortcut: Ctrl+Alt+F3 (start/stop)")

        layout.separator()

        col = layout.column()
        col.active = not wm.is_screencast_running
        col.prop(wm, "screencast_full")
        col.prop(wm, "screencast_show_cursor")
        col.prop(wm, "screencast_audio")
        col.prop(wm, "screencast_fps")
        col.prop(wm, "screencast_quality", text="Quality")
        layout.prop(wm, "screencast_record_standalone")

        layout.separator()

        layout.label(text="Save to:")
        layout.prop(wm, "screencast_directory", text="")
        if not wm.screencast_directory:
            layout.label(text="Empty: next to the .blend file", icon='INFO')

        row = layout.row(align=True)
        row.operator("screen.screencast_open_folder", text="Open Folder", icon='FILE_FOLDER')
        sub = row.row(align=True)
        sub.enabled = not wm.is_screencast_running
        sub.operator("screen.screencast_play_last", text="Play Last", icon='PLAY')


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

        # A popover looks different from the menus: it goes after them.
        if rd.use_game_engine:
            layout.popover(panel="INFO_PT_game_performance", text="Performance")


class INFO_MT_file(Menu):
    bl_label = "File"

    def draw(self, context):
        layout = self.layout

        layout.operator_context = 'INVOKE_AREA'
        layout.operator("wm.read_homefile", text="New File", icon='NEW')
        layout.operator("wm.create_project", text="Create Project", icon='NEWFOLDER')
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
        layout.operator("wm.blend_strings_utf8_validate", text="Validade .range strings", icon='TEXT')

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


class INFO_PT_game_performance(Panel):
    bl_space_type = 'INFO'
    bl_region_type = 'HEADER'
    bl_label = "Performance"
    # Opens centered under the button, near the left window edge: keep it narrow.
    bl_ui_units_x = 11

    def draw(self, context):
        layout = self.layout
        layout.label(text="Performance", icon='TIME')

        box = layout.box()
        box.label(text="Analyze")
        row = box.row(align=True)
        row.scale_y = 1.3
        row.operator("game.scene_doctor", text="Scene Doctor", icon='VIEWZOOM')
        row.operator("game.performance_report", text="Measure", icon='PLAY')
        row = box.row(align=True)
        row.operator("game.performance_report_last", text="Last", icon='TEXT')
        row.operator("game.performance_reports_folder", text="Folder", icon='FILE_FOLDER')
        box.label(text="What costs load, memory, frame.")

        box = layout.box()
        box.label(text="Optimize Scene")
        row = box.row(align=True)
        row.scale_y = 1.3
        row.operator("game.lod_generate_batch", text="Generate LODs", icon='MOD_DECIM')
        row.operator("game.lod_clear_generated", text="", icon='X')
        row = box.row(align=True)
        row.scale_y = 1.3
        row.operator("game.collision_proxy_generate", text="Collision Proxies", icon='MOD_PHYSICS')
        row.operator("game.collision_proxy_clear", text="", icon='X')
        box.label(text="Lighter meshes and collision.")

        box = layout.box()
        box.label(text="Prepare for Export")
        row = box.row(align=True)
        row.scale_y = 1.3
        row.operator("game.prepare_textures", text="Textures (DDS)", icon='IMAGE_DATA')
        row.operator("game.revert_prepared_textures", text="", icon='LOOP_BACK')
        row = box.row(align=True)
        row.scale_y = 1.3
        row.operator("game.prepare_audio", text="Audio (OGG)", icon='SOUND')
        box.label(text="Used on export; originals stay.")

        # Dicas medidas num celular Android: o GPU do celular é o gargalo.
        box = layout.box()
        box.label(text="Web / Android", icon='WORLD')
        world = context.scene.world
        if world and world.sky_type == 'ATMOSPHERIC':
            box.prop(world, "sky_quality")
            if world.sky_quality == 'HIGH':
                box.label(text="High sky is ~4x slower on phones.", icon='ERROR')
        col = box.column(align=True)
        col.label(text="Phone GPU is the limit: fewer")
        col.label(text="full-screen effects and filters.")
        col.label(text="Measure on the phone: ?report=1")


class INFO_MT_game(Menu):
    bl_label = "Game"

    def draw(self, context):
        layout = self.layout
        gs = context.scene.game_settings

        layout.prop(gs, "use_auto_start")
        layout.separator(factor=1)
        layout.menu("INFO_MT_game_overlays", icon='INFO')
        layout.menu("INFO_MT_game_visualization", icon='PHYSICS')
        layout.menu("INFO_MT_game_debug", icon='CONSOLE')


class INFO_MT_game_overlays(Menu):
    bl_label = "Overlays"

    def draw(self, context):
        layout = self.layout
        gs = context.scene.game_settings
        layout.prop(gs, "show_framerate_profile", text="Show Profile")
        layout.prop(gs, "show_render_queries")
        layout.prop(gs, "show_debug_properties")


class INFO_MT_game_visualization(Menu):
    bl_label = "Visualization"

    def draw(self, context):
        layout = self.layout
        gs = context.scene.game_settings
        layout.prop(gs, "show_physics_visualization", text="Physics")
        sub = layout.column()
        sub.active = gs.obstacle_simulation != 'NONE'
        sub.prop(gs, "show_obstacle_simulation", text="Obstacle Simulation")
        layout.separator(factor=1)
        layout.menu("INFO_MT_game_show_debug")


class INFO_MT_game_debug(Menu):
    bl_label = "Debug"

    def draw(self, context):
        layout = self.layout
        gs = context.scene.game_settings
        layout.prop(gs, "show_debug_mode", text="Debug Mode")
        layout.prop(gs, "show_console")
        layout.prop(gs, "use_python_console", text="Python Console")
        layout.prop(gs, "use_deprecation_warnings")


class INFO_MT_game_show_debug(Menu):
    bl_label = "Bounds and Frustums"

    def draw(self, context):
        layout = self.layout

        gs = context.scene.game_settings

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

        layout.operator("screen.asset_browser_show", text="Asset Browser", icon='ASSET_MANAGER')

        layout.separator(factor=1)

        layout.operator("screen.screenshot", icon="CAMERA_DATA")
        layout.operator("screen.screencast", text="Record Screen (start/stop)", icon='REC')

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

        layout.operator("wm.splash_about", text="Anastacio Engine About", icon_value=_cube_icon())
        layout.separator()

        # Same links as the splash screen.
        url = layout.operator("wm.url_open", text="Python API", icon='FILE_SCRIPT')
        url.url = "https://anastaciogames.github.io/anastacio-docs/"
        layout.operator("wm.url_open", text="GitHub", icon='URL').url = "https://github.com/AnastacioGames"
        layout.operator("wm.url_open", text="Discord", icon='DISCORD').url = "https://discord.gg/AsbjKgh4E"
        url = layout.operator("wm.url_open", text="Patreon Anastacio", icon='PATREON')
        url.url = "https://www.patreon.com/cw/AnastacioEngine"

        layout.separator()
        layout.label(text="Range Engine")
        layout.operator("wm.url_open", text="Range Website", icon='URL').url = "https://rangeengine.tech"
        url = layout.operator("wm.url_open", text="Range Python API", icon='HELP')
        url.url = "https://rangeengine.tech/RangeDoc_Build/html/"
        layout.operator("wm.url_open", text="Patreon Range", icon='PATREON').url = "https://www.patreon.com/rangeengine"

        layout.separator()
        layout.operator("wm.sysinfo", icon='TEXT')

        '''layout.operator("wm.splash", icon='BLENDER')'''


classes = (
    INFO_HT_header,
    INFO_PT_screen_recorder,
    INFO_MT_editor_menus,
    INFO_MT_file,
    INFO_MT_file_import,
    INFO_MT_file_export,
    INFO_MT_file_external_data,
    INFO_MT_file_previews,
    INFO_PT_game_performance,
    INFO_MT_game,
    INFO_MT_game_overlays,
    INFO_MT_game_visualization,
    INFO_MT_game_debug,
    INFO_MT_game_show_debug,
    INFO_MT_render,
    INFO_MT_opengl_render,
    INFO_MT_window,
    INFO_MT_help,
)


def _redraw_info_headers(self, context):
    for win in context.window_manager.windows:
        for area in win.screen.areas:
            if area.type == 'INFO':
                area.tag_redraw()


# Screen recorder settings, read by screen.screencast (also from Ctrl+Alt+F3) when the
# operator is run without them.
bpy.types.WindowManager.info_show_screen_recorder = bpy.props.BoolProperty(
    name="Screen Recorder",
    description="Show the screen recorder (Rec button and its options) in the Info header",
    default=True,
    update=_redraw_info_headers,
)
bpy.types.WindowManager.screencast_full = bpy.props.BoolProperty(
    name="Full Window",
    description="Record the whole window (otherwise only the 3D View)",
    default=True,
)
bpy.types.WindowManager.screencast_show_cursor = bpy.props.BoolProperty(
    name="Show Cursor",
    description="Draw the mouse cursor in the video, highlighted while a button is held",
    default=True,
)
bpy.types.WindowManager.screencast_audio = bpy.props.BoolProperty(
    name="Audio",
    description="Record the sound of the editor and of the game (Windows 10 2004 or newer)",
    default=True,
)
bpy.types.WindowManager.screencast_fps = bpy.props.IntProperty(
    name="Frame Rate",
    description="Frames per second to capture",
    default=30, min=1, max=120, soft_min=10, soft_max=60,
)
bpy.types.WindowManager.screencast_quality = bpy.props.EnumProperty(
    name="Quality",
    description="Video quality",
    items=(
        ('LOW', "Low", "Smallest files"),
        ('MEDIUM', "Medium", "Balanced size and quality"),
        ('HIGH', "High", "Sharp text and UI, larger files"),
        ('VERY_HIGH', "Very High", "Nearly lossless, large files"),
    ),
    default='HIGH',
)
bpy.types.WindowManager.screencast_record_standalone = bpy.props.BoolProperty(
    name="Record Standalone Player",
    description="While recording, a game started with Standalone records its own window "
                "to a separate video (<file>_standalone_<date>.mp4, same folder and settings)",
    default=True,
)
bpy.types.WindowManager.screencast_directory = bpy.props.StringProperty(
    name="Folder",
    description="Folder for the recordings (empty: next to the .blend file, or the Documents folder when it isn't saved)",
    subtype='DIR_PATH',
    default="",
)

if __name__ == "__main__":  # only for live edit.
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)
