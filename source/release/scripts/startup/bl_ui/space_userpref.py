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
import bpy, os, json
from bpy.types import (
    Header,
    Menu,
    Panel,
)
from bpy.props import (
    StringProperty,
    EnumProperty,
    FloatProperty,
    BoolProperty
)
from bpy.app.translations import pgettext_iface as iface_
from bpy.app.translations import contexts as i18n_contexts

def opengl_lamp_buttons(column, lamp):
    split = column.row()

    split.prop(lamp, "use", text="", icon='OUTLINER_OB_LAMP' if lamp.use else 'LAMP_DATA')

    col = split.column()
    col.active = lamp.use
    row = col.row()
    row.label(text="Diffuse:")
    row.prop(lamp, "diffuse_color", text="")
    row = col.row()
    row.label(text="Specular:")
    row.prop(lamp, "specular_color", text="")

    col = split.column()
    col.active = lamp.use
    col.prop(lamp, "direction", text="")


class USERPREF_HT_header(Header):
    bl_space_type = 'USER_PREFERENCES'

    def draw(self, context):
        layout = self.layout

        layout.template_header()

        userpref = context.user_preferences

        layout.operator_context = 'EXEC_AREA'
        layout.operator("wm.save_userpref")

        layout.operator_context = 'INVOKE_DEFAULT'

        if userpref.active_section == 'INPUT':
            layout.operator("wm.keyconfig_import")
            layout.operator("wm.keyconfig_export")
        elif userpref.active_section == 'ADDONS':
            layout.operator("wm.addon_install", icon='FILESEL')
            layout.operator("wm.addon_refresh", icon='FILE_REFRESH')
            layout.menu("USERPREF_MT_addons_online_resources")
        elif userpref.active_section == 'THEMES':
            layout.operator("ui.reset_default_theme")
            layout.operator("wm.theme_install")


class USERPREF_PT_navigation(Panel):
    bl_label = ""
    bl_space_type = 'USER_PREFERENCES'
    bl_region_type = 'NAVIGATION_BAR'
    bl_options = {'HIDE_HEADER'}

    def draw(self, context):
        layout = self.layout

        userpref = context.user_preferences

        # Keep the navigation compact and visually grouped.  The old 1.3x
        # scaling made the sidebar consume too much space before the content
        # could breathe, especially on smaller editor windows.
        # Draw each category in its own panel.  Keeping the enum items
        # explicit preserves the RNA enum and existing translation keys.
        def draw_group(title, sections, icon):
            group = layout.box()
            group.scale_x = 1.05
            group.scale_y = 1.12
            group.label(text=title, icon=icon)
            for section in sections:
                group.prop_enum(userpref, "active_section", section, icon=icon)

        draw_group("User Preferences:",
                   ('INTERFACE', 'EDITING', 'INPUT', 'ADDONS', 'THEMES'),
                   'PREFERENCES')
        draw_group("Game Engine:", ('INPUTSYSTEM',), 'GAME')
        draw_group("System:", ('SYSTEM_GENERAL', 'SYSTEM_FILES'), 'SETTINGS')


class USERPREF_MT_interaction_presets(Menu):
    bl_label = "Presets"
    preset_subdir = "interaction"
    preset_operator = "script.execute_preset"
    draw = Menu.draw_preset


class USERPREF_MT_app_templates(Menu):
    bl_label = "Application Templates"
    preset_subdir = "app_templates"

    def draw_ex(self, context, *, use_splash=False, use_default=False, use_install=False):
        import os

        layout = self.layout

        # now draw the presets
        layout.operator_context = 'EXEC_DEFAULT'

        if use_default:
            props = layout.operator("wm.read_homefile", text="Default")
            props.use_splash = True
            props.app_template = ""
            layout.separator(factor=1)

        template_paths = bpy.utils.app_template_paths()

        # expand template paths
        app_templates = []
        for path in template_paths:
            for d in os.listdir(path):
                if d.startswith(("__", ".")):
                    continue
                template = os.path.join(path, d)
                if os.path.isdir(template):
                    # template_paths_expand.append(template)
                    app_templates.append(d)

        for d in sorted(app_templates):
            props = layout.operator(
                "wm.read_homefile",
                text=bpy.path.display_name(d),
            )
            props.use_splash = True
            props.app_template = d

        if use_install:
            layout.separator(factor=1)
            layout.operator_context = 'INVOKE_DEFAULT'
            props = layout.operator("wm.app_template_install")

    def draw(self, context):
        self.draw_ex(context, use_splash=False, use_default=True, use_install=True)

class USERPREF_MT_appconfigs(Menu):
    bl_label = "AppPresets"
    preset_subdir = "keyconfig"
    preset_operator = "wm.appconfig_activate"

    def draw(self, context):
        self.layout.operator("wm.appconfig_default", text="Blender (default)")

        # now draw the presets
        Menu.draw_preset(self, context)

class USERPREF_PT_interface(Panel):
    bl_space_type = 'USER_PREFERENCES'
    bl_label = "Interface"
    bl_region_type = 'WINDOW'
    bl_options = {'HIDE_HEADER'}

    @classmethod
    def poll(cls, context):
        userpref = context.user_preferences
        return (userpref.active_section == 'INTERFACE')

    def draw(self, context):
        layout = self.layout

        userpref = context.user_preferences
        view = userpref.view

        row = layout.row()

        # Use boxed groups so each part reads as an independent settings panel.
        col = row.column()
        col = col.box()
        col.label(text="Display:")
        col.prop(view, "ui_scale", text="Scale")
        col.prop(view, "ui_line_width", text="Line Width")
        col.prop(view, "header_size", text="Header Size")
        col.prop(view, "show_tooltips")
        col.prop(view, "show_tooltips_python")
        col.prop(view, "show_developer_ui")
        col.prop(view, "show_object_info", text="Object Info")
        col.prop(view, "show_large_cursors")
        col.prop(view, "show_view_name", text="View Name")
        col.prop(view, "show_playback_fps", text="Playback FPS")
        col.prop(view, "use_global_scene")
        col.prop(view, "object_origin_size")

        col.separator(factor=1)
        col.separator(factor=1)
        col.separator(factor=1)

        col.prop(view, "show_mini_axis", text="Display Mini Axis")
        sub = col.column()
        sub.active = view.show_mini_axis
        sub.prop(view, "mini_axis_size", text="Size")
        sub.prop(view, "mini_axis_brightness", text="Brightness")

        col.separator(factor=1)

        col.label("Warnings")
        col.prop(view, "use_quit_dialog")

        row.separator(factor=1)
        row.separator(factor=1)

        view_panel = row.column()
        col = view_panel.box()
        col.label(text="View Manipulation:")
        col.prop(view, "use_mouse_depth_cursor")
        col.prop(view, "use_cursor_lock_adjust")
        col.prop(view, "use_mouse_depth_navigate")
        col.prop(view, "use_zoom_to_mouse")
        col.prop(view, "use_rotate_around_active")
        col.prop(view, "use_global_pivot")
        col.prop(view, "use_camera_lock_parent")

        col.separator(factor=1)

        col.prop(view, "use_auto_perspective")
        col.prop(view, "smooth_view")
        col.prop(view, "rotation_angle")

        col.separator(factor=1)
        col.separator(factor=1)

        # Keep the viewport timing/grid controls in their own sub-panel.
        col = view_panel.box()
        col.label(text="2D Viewports:")
        col.prop(view, "view2d_grid_spacing_min", text="Minimum Grid Spacing")
        col.prop(view, "timecode_style")
        col.prop(view, "view_frame_type")
        if view.view_frame_type == 'SECONDS':
            col.prop(view, "view_frame_seconds")
        elif view.view_frame_type == 'KEYFRAMES':
            col.prop(view, "view_frame_keyframes")

        row.separator(factor=1)
        row.separator(factor=1)

        manip_panel = row.column()
        col = manip_panel.box()
        # Toolbox doesn't exist yet
        # col.label(text="Toolbox:")
        #col.prop(view, "show_column_layout")
        #col.label(text="Open Toolbox Delay:")
        #col.prop(view, "open_left_mouse_delay", text="Hold LMB")
        #col.prop(view, "open_right_mouse_delay", text="Hold RMB")
        col.prop(view, "show_manipulator")
        sub = col.column()
        sub.active = view.show_manipulator
        sub.prop(view, "manipulator_size", text="Size")
        sub.prop(view, "manipulator_handle_size", text="Handle Size")
        sub.prop(view, "manipulator_hotspot", text="Hotspot")

        col.separator(factor=1)
        col.separator(factor=1)
        col.separator(factor=1)

        # Menus and pie-menu timing are independent groups of controls.
        col = manip_panel.box()
        col.label(text="Menus:")
        col.prop(view, "use_mouse_over_open")
        sub = col.column()
        sub.active = view.use_mouse_over_open

        sub.prop(view, "open_toplevel_delay", text="Top Level")
        sub.prop(view, "open_sublevel_delay", text="Sub Level")

        col.separator(factor=1)
        col = manip_panel.box()
        col.label(text="Pie Menus:")
        sub = col.column(align=True)
        sub.prop(view, "pie_animation_timeout")
        sub.prop(view, "pie_initial_timeout")
        sub.prop(view, "pie_menu_radius")
        sub.prop(view, "pie_menu_threshold")
        sub.prop(view, "pie_menu_confirm")
        col.separator(factor=1)

        col.prop(view, "show_splash")
        col.separator(factor=1)

        col.label(text="App Template:")
        col.label(text="Options intended for use with app-templates only.")
        col.prop(view, "show_layout_ui")
        col.prop(view, "show_view3d_cursor")


class USERPREF_PT_edit(Panel):
    bl_space_type = 'USER_PREFERENCES'
    bl_label = "Edit"
    bl_region_type = 'WINDOW'
    bl_options = {'HIDE_HEADER'}

    @classmethod
    def poll(cls, context):
        userpref = context.user_preferences
        return (userpref.active_section == 'EDITING')

    def draw(self, context):
        layout = self.layout

        userpref = context.user_preferences
        edit = userpref.edit

        row = layout.row()

        col = row.column()
        panel = col.box()
        panel.label(text="Link Materials To:")
        panel.prop(edit, "material_link", text="")
        panel = col.box()
        panel.label(text="New Objects:")
        panel.prop(edit, "use_enter_edit_mode")
        panel.label(text="Align To:")
        panel.prop(edit, "object_align", text="")
        panel = col.box()
        panel.label(text="Undo:")
        panel.prop(edit, "use_global_undo")
        panel.prop(edit, "undo_steps", text="Steps")
        panel.prop(edit, "undo_memory_limit", text="Memory Limit")

        row.separator(factor=1)
        row.separator(factor=1)

        col = row.column()
        panel = col.box()
        panel.label(text="Grease Pencil:")
        panel.prop(edit, "grease_pencil_eraser_radius", text="Eraser Radius")
        panel.prop(edit, "grease_pencil_manhattan_distance", text="Manhattan Distance")
        panel.prop(edit, "grease_pencil_euclidean_distance", text="Euclidean Distance")
        panel.prop(edit, "grease_pencil_default_color", text="Default Color")
        panel.prop(edit, "use_grease_pencil_simplify_stroke", text="Simplify Stroke")
        panel = col.box()
        panel.label(text="Playback:")
        panel.prop(edit, "use_negative_frames")
        panel = col.box()
        panel.label(text="Node Editor:")
        panel.prop(edit, "node_margin")
        panel = col.box()
        panel.label(text="Animation Editors:")
        panel.prop(edit, "fcurve_unselected_alpha", text="F-Curve Visibility")

        row.separator(factor=1)
        row.separator(factor=1)

        col = row.column()
        panel = col.box()
        panel.label(text="Keyframing:")
        panel.prop(edit, "use_visual_keying")
        panel.prop(edit, "use_keyframe_insert_needed", text="Only Insert Needed")
        panel.prop(edit, "use_auto_keying", text="Auto Keyframing:")
        panel.prop(edit, "use_auto_keying_warning")
        panel.prop(edit, "use_keyframe_insert_available", text="Only Insert Available")
        panel = col.box()
        panel.label(text="New F-Curve Defaults:")
        panel.prop(edit, "keyframe_new_interpolation_type", text="Interpolation")
        panel.prop(edit, "keyframe_new_handle_type", text="Handles")
        panel.prop(edit, "use_insertkey_xyz_to_rgb", text="XYZ to RGB")
        panel = col.box()
        panel.label(text="Transform:")
        panel.prop(edit, "use_drag_immediately")

        row.separator(factor=1)
        row.separator(factor=1)

        col = row.column()
        panel = col.box()
        panel.label(text="Sculpt Overlay Color:")
        panel.prop(edit, "sculpt_paint_overlay_color", text="")
        panel = col.box()
        panel.label(text="Duplicate Data:")
        panel.prop(edit, "use_duplicate_mesh", text="Mesh")
        panel.prop(edit, "use_duplicate_surface", text="Surface")
        panel.prop(edit, "use_duplicate_curve", text="Curve")
        panel.prop(edit, "use_duplicate_text", text="Text")
        panel.prop(edit, "use_duplicate_metaball", text="Metaball")
        panel.prop(edit, "use_duplicate_armature", text="Armature")
        panel.prop(edit, "use_duplicate_lamp", text="Lamp")
        panel.prop(edit, "use_duplicate_material", text="Material")
        panel.prop(edit, "use_duplicate_texture", text="Texture")
        #col.prop(edit, "use_duplicate_fcurve", text="F-Curve")
        panel.prop(edit, "use_duplicate_action", text="Action")
        panel.prop(edit, "use_duplicate_particle", text="Particle")


class USERPREF_PT_system_general(Panel):
    bl_space_type = 'USER_PREFERENCES'
    bl_label = "System General"
    bl_region_type = 'WINDOW'
    bl_options = {'HIDE_HEADER'}

    @classmethod
    def poll(cls, context):
        userpref = context.user_preferences
        return (userpref.active_section == 'SYSTEM_GENERAL')

    def draw(self, context):
        import sys
        layout = self.layout
        layout = layout.box()

        userpref = context.user_preferences
        system = userpref.system

        split = layout.split()

        # 1. Column
        column = split.column()
        colsplit = column.split(factor=0.85)

        col = colsplit.column()
        col.label(text="General:")

        col.prop(system, "frame_server_port")
        col.prop(system, "scrollback", text="Console Scrollback")

        col.separator(factor=1)

        col.label(text="Sound:")
        col.row().prop(system, "audio_device", expand=False)
        sub = col.column()
        sub.active = system.audio_device not in {'NONE', 'Null'}
        #sub.prop(system, "use_preview_images")
        sub.prop(system, "audio_channels", text="Channels")
        sub.prop(system, "audio_mixing_buffer", text="Mixing Buffer")
        sub.prop(system, "audio_sample_rate", text="Sample Rate")
        sub.prop(system, "audio_sample_format", text="Sample Format")

        col.separator(factor=1)

        if bpy.app.build_options.cycles:
            addon = userpref.addons.get("cycles")
            if addon is not None:
                addon.preferences.draw_impl(col, context)
            del addon

        if hasattr(system, "opensubdiv_compute_type"):
            col.label(text="OpenSubdiv compute:")
            col.row().prop(system, "opensubdiv_compute_type", text="")

        # 2. Column
        column = split.column()
        colsplit = column.split(factor=0.85)

        col = colsplit.column()
        col.label(text="OpenGL:")
        col.prop(system, "gl_clip_alpha", slider=True)
        col.prop(system, "use_mipmaps")
        col.prop(system, "use_gpu_mipmap")
        col.prop(system, "use_16bit_textures")

        col.separator(factor=1)
        col.label(text="Selection")
        col.prop(system, "select_method", text="")
        col.prop(system, "use_select_pick_depth")

        col.separator(factor=1)

        col.label(text="Anisotropic Filtering")
        col.prop(system, "anisotropic_filter", text="")

        col.separator(factor=1)

        col.label(text="Window Draw Method:")
        col.prop(system, "window_draw_method", text="")
        col.prop(system, "multi_sample", text="")
        if sys.platform == "linux" and system.multi_sample != 'NONE':
            col.label(text="Might fail for Mesh editing selection!")
            col.separator(factor=1)
        col.prop(system, "use_region_overlap")

        col.separator(factor=1)

        col.label(text="Text Draw Options:")
        col.prop(system, "use_text_antialiasing", text="Anti-aliasing")
        sub = col.column()
        sub.active = system.use_text_antialiasing
        sub.prop(system, "text_hinting", text="Hinting")

        col.separator(factor=1)

        col.label(text="Textures:")
        col.prop(system, "gl_texture_limit", text="Limit Size")
        col.prop(system, "texture_time_out", text="Time Out")
        col.prop(system, "texture_collection_rate", text="Collection Rate")

        col.separator(factor=1)

        col.label(text="Images Draw Method:")
        col.prop(system, "image_draw_method", text="")

        col.separator(factor=1)

        col.label(text="Sequencer/Clip Editor:")
        # currently disabled in the code
        # col.prop(system, "prefetch_frames")
        col.prop(system, "memory_cache_limit")

        # 3. Column
        column = split.column()

        column.label(text="Solid OpenGL Lights:")

        split = column.split(factor=0.1)
        split.label()
        split.label(text="Colors:")
        split.label(text="Direction:")

        lamp = system.solid_lights[0]
        opengl_lamp_buttons(column, lamp)

        lamp = system.solid_lights[1]
        opengl_lamp_buttons(column, lamp)

        lamp = system.solid_lights[2]
        opengl_lamp_buttons(column, lamp)

        column.separator(factor=1)

        column.label(text="Color Picker Type:")
        column.row().prop(system, "color_picker_type", text="")

        column.separator(factor=1)

        column.prop(system, "use_weight_color_range", text="Custom Weight Paint Range")
        sub = column.column()
        sub.active = system.use_weight_color_range
        sub.template_color_ramp(system, "weight_color_range", expand=True)

        column.separator(factor=1)
        column.prop(system, "font_path_ui")
        column.prop(system, "font_path_ui_mono")

        if bpy.app.build_options.international:
            column.prop(system, "use_international_fonts")
            if system.use_international_fonts:
                column.prop(system, "language")
                row = column.row()
                row.label(text="Translate:", text_ctxt=i18n_contexts.id_windowmanager)
                row = column.row(align=True)
                row.prop(system, "use_translate_interface", text="Interface", toggle=True)
                row.prop(system, "use_translate_tooltips", text="Tooltips", toggle=True)
                row.prop(system, "use_translate_new_dataname", text="New Data", toggle=True)


class USERPREF_MT_interface_theme_presets(Menu):
    bl_label = "Presets"
    preset_subdir = "interface_theme"
    preset_operator = "script.execute_preset"
    preset_type = 'XML'
    preset_xml_map = (
        ("user_preferences.themes[0]", "Theme"),
        ("user_preferences.ui_styles[0]", "ThemeStyle"),
    )
    draw = Menu.draw_preset

    def reset_cb(context):
        bpy.ops.ui.reset_default_theme()


class USERPREF_PT_theme(Panel):
    bl_space_type = 'USER_PREFERENCES'
    bl_label = "Themes"
    bl_region_type = 'WINDOW'
    bl_options = {'HIDE_HEADER'}

    # not essential, hard-coded UI delimiters for the theme layout
    ui_delimiters = {
        'VIEW_3D': {
            "text_grease_pencil",
            "text_keyframe",
            "speaker",
            "freestyle_face_mark",
            "split_normal",
            "bone_solid",
            "paint_curve_pivot",
        },
        'GRAPH_EDITOR': {
            "handle_vertex_select",
        },
        'IMAGE_EDITOR': {
            "paint_curve_pivot",
        },
        'NODE_EDITOR': {
            "layout_node",
        },
        'CLIP_EDITOR': {
            "handle_vertex_select",
        }
    }

    @staticmethod
    def _theme_generic(split, themedata, theme_area):

        col = split.column()

        global_ui_labels = {
            "wcol_regular": "Regular",
            "wcol_tool": "Tool",
            "wcol_radio": "Radio Buttons",
            "wcol_text": "Text",
            "wcol_option": "Option",
            "wcol_toggle": "Toggle",
            "wcol_num": "Number Field",
            "wcol_numslider": "Value Slider",
            "wcol_box": "Box",
            "wcol_menu": "Menu",
            "wcol_pie_menu": "Pie Menu",
            "wcol_pulldown": "Pulldown",
            "wcol_menu_back": "Menu Back",
            "wcol_tooltip": "Tooltip",
            "wcol_menu_item": "Menu Item",
            "wcol_scroll": "Scroll Bar",
            "wcol_progress": "Progress Bar",
            "wcol_list_item": "List Item",
            "wcol_state": "State",
        }

        def theme_generic_recurse(data, data_label=None):
            if theme_area == 'GLOBAL_THEME_UI' and data_label is not None:
                label = global_ui_labels.get(data_label, data_label)
            else:
                label = data.rna_type.name

            col.label(label)
            row = col.row()
            subsplit = row.split(factor=0.95)

            padding1 = subsplit.split(factor=0.15)
            padding1.column()

            subsplit = row.split(factor=0.85)

            padding2 = subsplit.split(factor=0.15)
            padding2.column()

            colsub_pair = padding1.column(), padding2.column()

            props_type = {}

            for i, prop in enumerate(data.rna_type.properties):
                if prop.identifier == "rna_type":
                    continue

                props_type.setdefault((prop.type, prop.subtype), []).append(prop)

            th_delimiters = USERPREF_PT_theme.ui_delimiters.get(theme_area)
            for props_type, props_ls in sorted(props_type.items()):
                if props_type[0] == 'POINTER':
                    for i, prop in enumerate(props_ls):
                        theme_generic_recurse(getattr(data, prop.identifier), prop.identifier)
                else:
                    if th_delimiters is None:
                        # simple, no delimiters
                        for i, prop in enumerate(props_ls):
                            colsub_pair[i % 2].row().prop(data, prop.identifier)
                    else:
                        # add hard coded delimiters
                        i = 0
                        for prop in props_ls:
                            colsub = colsub_pair[i]
                            colsub.row().prop(data, prop.identifier)
                            i = (i + 1) % 2
                            if prop.identifier in th_delimiters:
                                if i:
                                    colsub = colsub_pair[1]
                                    colsub.row().label("")
                                colsub_pair[0].row().label("")
                                colsub_pair[1].row().label("")
                                i = 0

        theme_generic_recurse(themedata)

    @staticmethod
    def _theme_widget_style(layout, widget_style):

        row = layout.row()

        subsplit = row.split(factor=0.95)

        padding = subsplit.split(factor=0.15)
        colsub = padding.column()
        colsub = padding.column()
        colsub.row().prop(widget_style, "outline")
        colsub.row().prop(widget_style, "item", slider=True)
        colsub.row().prop(widget_style, "inner", slider=True)
        colsub.row().prop(widget_style, "inner_sel", slider=True)
        colsub.row().prop(widget_style, "roundness")

        subsplit = row.split(factor=0.85)

        padding = subsplit.split(factor=0.15)
        colsub = padding.column()
        colsub = padding.column()
        colsub.row().prop(widget_style, "text")
        colsub.row().prop(widget_style, "text_sel")
        colsub.prop(widget_style, "show_shaded")
        subsub = colsub.column(align=True)
        subsub.active = widget_style.show_shaded
        subsub.prop(widget_style, "shadetop")
        subsub.prop(widget_style, "shadedown")

        layout.separator(factor=1)

    @staticmethod
    def _ui_font_style(layout, font_style):

        split = layout.split()

        col = split.column()
        col.label(text="Kerning Style:")
        col.row().prop(font_style, "font_kerning_style", expand=True)
        col.prop(font_style, "points")

        col = split.column()
        col.label(text="Shadow Offset:")
        col.prop(font_style, "shadow_offset_x", text="X")
        col.prop(font_style, "shadow_offset_y", text="Y")

        col = split.column()
        col.prop(font_style, "shadow")
        col.prop(font_style, "shadow_alpha")
        col.prop(font_style, "shadow_value")

        layout.separator(factor=1)

    @staticmethod
    def _theme_interface_options(col, ui):
        ui_state = ui.wcol_state
        col.label(text="State:")
        row = col.row()
        split = row.split(factor=0.5)
        left, right = split.column(), split.column()
        left.prop(ui_state, "inner_anim")
        left.prop(ui_state, "inner_anim_sel")
        left.prop(ui_state, "inner_driven")
        left.prop(ui_state, "inner_driven_sel")
        right.prop(ui_state, "blend")
        right.prop(ui_state, "inner_key")
        right.prop(ui_state, "inner_key_sel")
        right.prop(ui_state, "inner_overridden")
        right.prop(ui_state, "inner_overridden_sel")
        right.prop(ui_state, "inner_changed")
        right.prop(ui_state, "inner_changed_sel")

        col.separator(factor=1)
        col.label(text="Styles:")
        row = col.row()
        split = row.split(factor=0.5)
        left, right = split.column(), split.column()
        left.prop(ui, "menu_shadow_fac")
        left.prop(ui, "menu_shadow_width")
        left.prop(ui, "icon_alpha")
        right.prop(ui, "widget_emboss")

        col.separator(factor=1)
        col.label(text="Axis Colors:")
        row = col.row()
        split = row.split(factor=0.5)
        left, right = split.column(), split.column()
        left.prop(ui, "axis_x")
        left.prop(ui, "axis_y")
        left.prop(ui, "axis_z")

        col.separator(factor=1)
        col.label(text="Icon Colors:")
        row = col.row()
        split = row.split(factor=0.5)
        left, right = split.column(), split.column()
        left.prop(ui, "icon_collection")
        left.prop(ui, "icon_scene")
        left.prop(ui, "icon_object")
        left.prop(ui, "icon_object_data")
        right.prop(ui, "icon_modifier")
        right.prop(ui, "icon_shading")
        col.separator(factor=1)

    @classmethod
    def poll(cls, context):
        userpref = context.user_preferences
        return (userpref.active_section == 'THEMES')

    def draw(self, context):
        layout = self.layout

        theme = context.user_preferences.themes[0]
        layout = layout.box()

        split_themes = layout.split(factor=0.2)

        sub = split_themes.column()

        sub.label(text="Presets:")
        subrow = sub.row(align=True)

        subrow.menu("USERPREF_MT_interface_theme_presets", text=USERPREF_MT_interface_theme_presets.bl_label)
        subrow.operator("wm.interface_theme_preset_add", text="", icon='ZOOMIN')
        subrow.operator("wm.interface_theme_preset_add", text="", icon='ZOOMOUT').remove_active = True
        sub.separator(factor=1)

        sub.prop(theme, "theme_area", expand=True)

        split = layout.split(factor=0.4)

        layout.separator(factor=1)
        layout.separator(factor=1)

        split = split_themes.split()

        if theme.theme_area == 'USER_INTERFACE':
            col = split.column()
            ui = theme.user_interface

            self._theme_interface_options(col, ui)

            col.label(text="Regular:")
            self._theme_widget_style(col, ui.wcol_regular)

            col.label(text="Tool:")
            self._theme_widget_style(col, ui.wcol_tool)

            col.label(text="Radio Buttons:")
            self._theme_widget_style(col, ui.wcol_radio)

            col.label(text="Text:")
            self._theme_widget_style(col, ui.wcol_text)

            col.label(text="Option:")
            self._theme_widget_style(col, ui.wcol_option)

            col.label(text="Toggle:")
            self._theme_widget_style(col, ui.wcol_toggle)

            col.label(text="Number Field:")
            self._theme_widget_style(col, ui.wcol_num)

            col.label(text="Value Slider:")
            self._theme_widget_style(col, ui.wcol_numslider)

            col.label(text="Box:")
            self._theme_widget_style(col, ui.wcol_box)

            col.label(text="Menu:")
            self._theme_widget_style(col, ui.wcol_menu)

            col.label(text="Pie Menu:")
            self._theme_widget_style(col, ui.wcol_pie_menu)

            col.label(text="Pulldown:")
            self._theme_widget_style(col, ui.wcol_pulldown)

            col.label(text="Menu Back:")
            self._theme_widget_style(col, ui.wcol_menu_back)

            col.label(text="Tooltip:")
            self._theme_widget_style(col, ui.wcol_tooltip)

            col.label(text="Menu Item:")
            self._theme_widget_style(col, ui.wcol_menu_item)

            col.label(text="Scroll Bar:")
            self._theme_widget_style(col, ui.wcol_scroll)

            col.label(text="Progress Bar:")
            self._theme_widget_style(col, ui.wcol_progress)

            col.label(text="List Item:")
            self._theme_widget_style(col, ui.wcol_list_item)

        elif theme.theme_area == 'GLOBAL_THEME':
            col = split.column()

            col.label(text="Copy Global Theme To:")
            copy_split = col.split(factor=0.5)
            copy_left = copy_split.column()
            copy_right = copy_split.column()

            copy_left.prop(theme, "global_copy_user_interface")
            copy_left.prop(theme, "global_copy_view_3d")
            copy_left.prop(theme, "global_copy_timeline")
            copy_left.prop(theme, "global_copy_graph_editor")
            copy_left.prop(theme, "global_copy_dopesheet")
            copy_left.prop(theme, "global_copy_nla")
            copy_left.prop(theme, "global_copy_image_editor")
            copy_left.prop(theme, "global_copy_sequence_editor")
            copy_left.prop(theme, "global_copy_text_editor")
            copy_right.prop(theme, "global_copy_node_editor")
            copy_right.prop(theme, "global_copy_logic_editor")
            copy_right.prop(theme, "global_copy_properties")
            copy_right.prop(theme, "global_copy_outliner")
            copy_right.prop(theme, "global_copy_user_preferences")
            copy_right.prop(theme, "global_copy_info")
            copy_right.prop(theme, "global_copy_file_browser")
            copy_right.prop(theme, "global_copy_console")
            copy_right.prop(theme, "global_copy_clip_editor")

            col.separator(factor=1)
            col.label(text="Shared Theme Space Settings:")
            self._theme_generic(col, theme.global_theme, 'GLOBAL_THEME')

            col.separator(factor=1)
            col.label(text="All Widget Colors:")
            self._theme_widget_style(col, theme.global_ui.wcol_regular)

            col.label(text="Widget State Colors:")
            self._theme_generic(col, theme.global_ui.wcol_state, 'GLOBAL_THEME')

            col.separator()
            col.separator()
        elif theme.theme_area == 'BONE_COLOR_SETS':
            col = split.column()

            for i, ui in enumerate(theme.bone_color_sets, 1):
                col.label(iface_(f"Color Set {i:d}"), translate=False)

                row = col.row()

                subsplit = row.split(factor=0.95)

                padding = subsplit.split(factor=0.15)
                colsub = padding.column()
                colsub = padding.column()
                colsub.row().prop(ui, "normal")
                colsub.row().prop(ui, "select")
                colsub.row().prop(ui, "active")

                subsplit = row.split(factor=0.85)

                padding = subsplit.split(factor=0.15)
                colsub = padding.column()
                colsub = padding.column()
                colsub.row().prop(ui, "show_colored_constraints")
        elif theme.theme_area == 'STYLE':
            col = split.column()

            style = context.user_preferences.ui_styles[0]

            col.label(text="Panel Title:")
            self._ui_font_style(col, style.panel_title)

            col.separator(factor=1)

            col.label(text="Widget:")
            self._ui_font_style(col, style.widget)

            col.separator(factor=1)

            col.label(text="Widget Label:")
            self._ui_font_style(col, style.widget_label)
        else:
            self._theme_generic(split, getattr(theme, theme.theme_area.lower()), theme.theme_area)


class USERPREF_PT_file(Panel):
    bl_space_type = 'USER_PREFERENCES'
    bl_label = "Files"
    bl_region_type = 'WINDOW'
    bl_options = {'HIDE_HEADER'}

    @classmethod
    def poll(cls, context):
        userpref = context.user_preferences
        return (userpref.active_section == 'SYSTEM_FILES')

    def draw(self, context):
        layout = self.layout
        layout = layout.box()

        userpref = context.user_preferences
        paths = userpref.filepaths
        system = userpref.system

        split = layout.split(factor=0.7)

        col = split.column()
        col.label(text="File Paths:")

        colsplit = col.split(factor=0.95)
        col1 = colsplit.split(factor=0.3)

        sub = col1.column()
        sub.label(text="Fonts:")
        sub.label(text="Icons:")
        sub.label(text="Textures:")
        sub.label(text="Render Output:")
        sub.label(text="Scripts:")
        sub.label(text="Sounds:")
        sub.label(text="Temp:")
        sub.label(text="Render Cache:")
        sub.label(text="I18n Branches:")
        sub.label(text="Image Editor:")
        sub.label(text="Animation Player:")

        sub = col1.column()
        sub.prop(paths, "font_directory", text="")
        sub.prop(paths, "icon_directory", text="")
        sub.prop(paths, "texture_directory", text="")
        sub.prop(paths, "render_output_directory", text="")
        sub.prop(paths, "script_directory", text="")
        sub.prop(paths, "sound_directory", text="")
        sub.prop(paths, "temporary_directory", text="")
        sub.prop(paths, "render_cache_directory", text="")
        sub.prop(paths, "i18n_branches_directory", text="")
        sub.prop(paths, "image_editor", text="")
        subsplit = sub.split(factor=0.3)
        subsplit.prop(paths, "animation_player_preset", text="")
        subsplit.prop(paths, "animation_player", text="")

        col.separator(factor=1)
        col.separator(factor=1)

        colsplit = col.split(factor=0.95)
        sub = colsplit.column()

        row = sub.split(factor=0.3)
        row.label(text="Auto Execution:")
        row.prop(system, "use_scripts_auto_execute")

        if system.use_scripts_auto_execute:
            box = sub.box()
            row = box.row()
            row.label(text="Excluded Paths:")
            row.operator("wm.userpref_autoexec_path_add", text="", icon='ZOOMIN', emboss=False)
            for i, path_cmp in enumerate(userpref.autoexec_paths):
                row = box.row()
                row.prop(path_cmp, "path", text="")
                row.prop(path_cmp, "use_glob", text="", icon='FILTER')
                row.operator("wm.userpref_autoexec_path_remove", text="", icon='X', emboss=False).index = i

        col = split.column()
        col.label(text="Save & Load:")
        col.prop(paths, "use_relative_paths")
        col.prop(paths, "use_file_compression")
        col.prop(paths, "use_load_ui")
        col.prop(paths, "use_filter_files")
        col.prop(paths, "show_hidden_files_datablocks")
        col.prop(paths, "hide_recent_locations")
        col.prop(paths, "hide_system_bookmarks")
        col.prop(paths, "show_thumbnails")

        col.separator(factor=1)

        col.prop(paths, "save_version")
        col.prop(paths, "recent_files")
        col.prop(paths, "use_save_preview_images")

        col.separator(factor=1)

        col.label(text="Auto Save:")
        col.prop(paths, "use_keep_session")
        col.prop(paths, "use_auto_save_temporary_files")
        sub = col.column()
        sub.active = paths.use_auto_save_temporary_files
        sub.prop(paths, "auto_save_time", text="Timer (mins)")

        col.separator(factor=1)

        col.label(text="Text Editor:")
        col.prop(system, "use_tabs_as_spaces")

        colsplit = col.split(factor=0.95)
        col1 = colsplit.split(factor=0.3)

        sub = col1.column()
        sub.label(text="Author:")
        sub = col1.column()
        sub.prop(system, "author", text="")


class USERPREF_MT_ndof_settings(Menu):
    # accessed from the window key-bindings in C (only)
    bl_label = "3D Mouse Settings"

    def draw(self, context):
        layout = self.layout

        input_prefs = context.user_preferences.inputs

        is_view3d = context.space_data.type == 'VIEW_3D'

        layout.prop(input_prefs, "ndof_sensitivity")
        layout.prop(input_prefs, "ndof_orbit_sensitivity")
        layout.prop(input_prefs, "ndof_deadzone")

        if is_view3d:
            layout.separator(factor=1)
            layout.prop(input_prefs, "ndof_show_guide")

            layout.separator(factor=1)
            layout.label(text="Orbit Style")
            layout.row().prop(input_prefs, "ndof_view_navigate_method", text="")
            layout.row().prop(input_prefs, "ndof_view_rotate_method", text="")
            layout.separator(factor=1)
            layout.label(text="Orbit Options")
            layout.prop(input_prefs, "ndof_rotx_invert_axis")
            layout.prop(input_prefs, "ndof_roty_invert_axis")
            layout.prop(input_prefs, "ndof_rotz_invert_axis")

        # view2d use pan/zoom
        layout.separator(factor=1)
        layout.label(text="Pan Options")
        layout.prop(input_prefs, "ndof_panx_invert_axis")
        layout.prop(input_prefs, "ndof_pany_invert_axis")
        layout.prop(input_prefs, "ndof_panz_invert_axis")
        layout.prop(input_prefs, "ndof_pan_yz_swap_axis")

        layout.label(text="Zoom Options")
        layout.prop(input_prefs, "ndof_zoom_invert")

        if is_view3d:
            layout.separator(factor=1)
            layout.label(text="Fly/Walk Options")
            layout.prop(input_prefs, "ndof_fly_helicopter", icon='NDOF_FLY')
            layout.prop(input_prefs, "ndof_lock_horizon", icon='NDOF_DOM')


class USERPREF_MT_keyconfigs(Menu):
    bl_label = "KeyPresets"
    preset_subdir = "keyconfig"
    preset_operator = "wm.keyconfig_activate"

    def draw(self, context):
        props = self.layout.operator("wm.context_set_value", text="Blender (default)")
        props.data_path = "window_manager.keyconfigs.active"
        props.value = "context.window_manager.keyconfigs.default"

        # now draw the presets
        Menu.draw_preset(self, context)


class USERPREF_PT_input(Panel):
    bl_space_type = 'USER_PREFERENCES'
    bl_label = "Input"
    bl_region_type = 'WINDOW'
    bl_options = {'HIDE_HEADER'}

    @classmethod
    def poll(cls, context):
        userpref = context.user_preferences
        return (userpref.active_section == 'INPUT')

    @staticmethod
    def draw_input_prefs(inputs, layout):
        import sys

        # Keep the input preferences visually independent from the keymap.
        layout = layout.box()

        # General settings
        row = layout.row()
        col = row.column()

        sub = col.column()
        sub.label(text="Presets:")
        subrow = sub.row(align=True)

        subrow.menu("USERPREF_MT_interaction_presets", text=bpy.types.USERPREF_MT_interaction_presets.bl_label)
        subrow.operator("wm.interaction_preset_add", text="", icon='ZOOMIN')
        subrow.operator("wm.interaction_preset_add", text="", icon='ZOOMOUT').remove_active = True
        sub.separator(factor=1)

        sub.label(text="Mouse:")
        sub1 = sub.column()
        sub1.active = (inputs.select_mouse == 'RIGHT')
        sub1.prop(inputs, "use_mouse_emulate_3_button")
        sub.prop(inputs, "use_mouse_continuous")
        sub.prop(inputs, "drag_threshold")
        sub.prop(inputs, "tweak_threshold")

        sub.label(text="Select With:")
        sub.row().prop(inputs, "select_mouse", expand=True)

        sub = col.column()
        sub.label(text="Double Click:")
        sub.prop(inputs, "mouse_double_click_time", text="Speed")

        sub.separator(factor=1)

        sub.prop(inputs, "use_emulate_numpad")

        sub.separator(factor=1)

        sub.label(text="Orbit Style:")
        sub.row().prop(inputs, "view_rotate_method", expand=True)

        sub.separator(factor=1)

        sub.label(text="Zoom Style:")
        sub.row().prop(inputs, "view_zoom_method", text="")
        if inputs.view_zoom_method in {'DOLLY', 'CONTINUE'}:
            sub.row().prop(inputs, "view_zoom_axis", expand=True)
            sub.prop(inputs, "invert_mouse_zoom", text="Invert Mouse Zoom Direction")

        #sub.prop(inputs, "use_mouse_mmb_paste")

        # col.separator(factor=1)

        sub = col.column()
        sub.prop(inputs, "invert_zoom_wheel", text="Invert Wheel Zoom Direction")
        #sub.prop(view, "wheel_scroll_lines", text="Scroll Lines")

        if sys.platform == "darwin":
            sub = col.column()
            sub.prop(inputs, "use_trackpad_natural", text="Natural Trackpad Direction")

        col.separator(factor=1)
        sub = col.column()
        sub.label(text="View Navigation:")
        sub.row().prop(inputs, "navigation_mode", expand=True)

        sub.label(text="Walk Navigation:")

        walk = inputs.walk_navigation

        sub.prop(walk, "use_mouse_reverse")
        sub.prop(walk, "mouse_speed")
        sub.prop(walk, "teleport_time")

        sub = col.column(align=True)
        sub.prop(walk, "walk_speed")
        sub.prop(walk, "walk_speed_factor")

        sub.separator(factor=1)
        sub.prop(walk, "use_gravity")
        sub = col.column(align=True)
        sub.active = walk.use_gravity
        sub.prop(walk, "view_height")
        sub.prop(walk, "jump_height")

        if inputs.use_ndof:
            col.separator(factor=1)
            col.label(text="NDOF Device:")
            sub = col.column(align=True)
            sub.prop(inputs, "ndof_sensitivity", text="Pan Sensitivity")
            sub.prop(inputs, "ndof_orbit_sensitivity", text="Orbit Sensitivity")
            sub.prop(inputs, "ndof_deadzone", text="Deadzone")

            sub.separator(factor=1)
            col.label(text="Navigation Style:")
            sub = col.column(align=True)
            sub.row().prop(inputs, "ndof_view_navigate_method", expand=True)

            sub.separator(factor=1)
            col.label(text="Rotation Style:")
            sub = col.column(align=True)
            sub.row().prop(inputs, "ndof_view_rotate_method", expand=True)

        row.separator(factor=1)

    def draw(self, context):
        from rna_keymap_ui import draw_keymaps

        layout = self.layout

        #import time

        #start = time.time()

        userpref = context.user_preferences

        inputs = userpref.inputs

        split = layout.split(factor=0.25)

        # Input settings
        self.draw_input_prefs(inputs, split)

        # Keymap Settings
        draw_keymaps(context, split.box())

        #print("runtime", time.time() - start)

class USERPREF_MT_input_system_presets(Menu):
    bl_label = "Presets"
    preset_subdir = "inputsystem"
    preset_operator = "script.execute_preset"
    draw = Menu.draw_preset

class USERPREF_PT_input_system(Panel):
    bl_space_type = 'USER_PREFERENCES'
    bl_label = "Input System"
    bl_region_type = 'WINDOW'
    bl_options = {'HIDE_HEADER'}
    
    # Dyn alloc in Class. CPython does not free memory from this variable in the class because there are windowmanager attr references
    input_bind_enums_dyn_alloc = [] 
    
    # For Vector Processors
    replicate_times = {"INVERTVALUES": 1, "INVERTVALUES2D": 2, "INVERTVALUES3D" : 3,
                       "SCALEVALUES": 1, "SCALEVALUES2D": 2, "SCALEVALUES3D" : 3,
                       
                       "LERPVALUES": 1, "DEADZONE" : 2
    }
    # "BOOL", ("FLOAT", min, max)
    processor_type = {"INVERTVALUES": "BOOL", "INVERTVALUES2D": "BOOL", "INVERTVALUES3D" : "BOOL",
                       "SCALEVALUES": ("FLOAT", -10.0, 10.0), "SCALEVALUES2D": ("FLOAT", -10.0, 10.0), "SCALEVALUES3D" : ("FLOAT", -10.0, 10.0),
                       
                       "LERPVALUES": ("FLOAT", 0.0, 1.0), "DEADZONE" : ("FLOAT", 0.0, 1.0) 
    }
    orderVector = ["X", "Y", "Z"]
    
    @classmethod
    def poll(cls, context):
        userpref = context.user_preferences
        return (userpref.active_section == 'INPUTSYSTEM')
        
    def generate_dynamic_enum(self, wm, name, default_value):
        prop_name = f"dynamic_enum_{name}"

        prop = EnumProperty(
            name="Type",
            description=f"Dynamic enum property {name}",
            items=[
            ("KEYBOARD", "Keyboard", "Capture keyboard events"),
            ("MOUSE", "Mouse", "Capture mouse events"),
            ("JOYSTICK", "Joystick", "Capture joystick events")
            ]
        )
        setattr(bpy.types.WindowManager, prop_name, prop)
        setattr(wm, prop_name, default_value)

        # Add Dyn Allocated Enum Name.
        self.input_bind_enums_dyn_alloc.append(prop_name)
        
    def generate_joystick_index_enum(self, wm, name, default_value):
        prop_name = f"dynamic_enum_joystick_index_{name}"
        prop = EnumProperty(
            name="Joystick Index",
            description="Specifies which control should get the inputs from, e.g: 0 = first control",
            items=[
                ("0", "0", ""),
                ("1", "1", ""),
                ("2", "2", ""),
                ("3", "3", ""),
                ("4", "4", ""),
                ("5", "5", ""),
                ("6", "6", ""),
                ("7", "7", ""),
                ],
            default = "0"
        )
        
        setattr(bpy.types.WindowManager, prop_name, prop)
        setattr(wm, prop_name, str(default_value))

        # Add Dyn Allocated Enum Name.
        self.input_bind_enums_dyn_alloc.append(prop_name)
        
    def generate_joystick_enum(self, wm, name, default_value):
        prop_name = f"dynamic_enum_joystick_{name}"
        prop = EnumProperty(
            name="Joystick Table",
            description="",
            items=[
                ("0", "NONE", ""),
                ("1", "A", ""),
                ("2", "B", ""),
                ("3", "X", ""),
                ("4", "Y", ""),
                ("5", "BACK", ""),
                ("6", "GUIDE", ""),
                ("7", "START", ""),
                ("8", "LEFTSTICK", ""),
                ("9", "RIGHTSTICK", ""),
                ("10", "LEFTSHOULDER", ""),
                ("11", "RIGHTSHOULDER", ""),
                ("12", "PAD UP", ""),
                ("13", "PAD DOWN", ""),
                ("14", "PAD LEFT", ""),
                ("15", "PAD RIGHT", ""),
                
                # Special for the input system, with the exception of KX_PythonJoystick::JOYSTICK_EnumInputs
                ("100", "LEFT_JOY X", ""),
                ("101", "LEFT_JOY Y", ""),
                ("102", "RIGHT_JOY X", ""),
                ("103", "RIGHT_JOY Y", ""),
                
                ("104", "TRIGGER_LEFT", ""),
                ("105", "TRIGGER_RIGHT", ""),
                ],
            default = "0"
        )
        
        setattr(bpy.types.WindowManager, prop_name, prop)
        # We don't know if the value is for KEYBOARD OR MOUSE, it's easier not to use the value if it doesn't work
        try:
            setattr(wm, prop_name, default_value)
        except:
            ...

        # Add Dyn Allocated Enum Name.
        self.input_bind_enums_dyn_alloc.append(prop_name)
        
    def generate_bind_capture_key(self, wm, name, default_value):
        wm["InputSystem_Keymap_Capture"][name] = wm.GetGameEngineKeyInverted.get(default_value)
        
    def generate_sensitivity_float(self, wm, name, default_value):
        prop_name = f"dynamic_float_sensitivity_{name}"
        
        prop = FloatProperty(
            name="Value",
            description=f"Input Sensitivity {name}",
            min = 0.0,
            max = 1000.0
        )
        
        setattr(bpy.types.WindowManager, prop_name, prop)
        setattr(wm, prop_name, default_value)

        # Add Dyn Allocated Enum Name.
        self.input_bind_enums_dyn_alloc.append(prop_name)
        
    def generate_string_custom_key(self, wm, name):
        prop_name = f"dynamic_string_custom_key_{name}"
        
        prop = StringProperty(
            name="Value",
            description="Custom Key, some keys that capture key cannot catch: CAPS_LOCK, SEMI_COLON = ; or : ..."
        )
        
        setattr(bpy.types.WindowManager, prop_name, prop)
        #setattr(wm, prop_name, "" if default_value ! else False)

        # Add Dyn Allocated Enum Name.
        self.input_bind_enums_dyn_alloc.append(prop_name)
        
    def generate_process_float(self, wm, name, min_value, max_value, default_value):
        prop_name = f"dynamic_float_{name}"
        
        prop = FloatProperty(
            name="Value",
            description=f"Dynamic float property {name}",
            min = min_value,
            max = max_value
        )
        
        setattr(bpy.types.WindowManager, prop_name, prop)
        setattr(wm, prop_name, default_value)

        # Add Dyn Allocated Enum Name.
        self.input_bind_enums_dyn_alloc.append(prop_name)
        
    def generate_process_bool(self, wm, name, default_value, custom_description=""):
        prop_name = f"dynamic_bool_{name}"
        
        prop = BoolProperty(
            name="Value",
            description=f"Dynamic bool property {name}" if custom_description == "" else custom_description
        )
        
        setattr(bpy.types.WindowManager, prop_name, prop)
        setattr(wm, prop_name, True if default_value == 1 else False)

        # Add Dyn Allocated Enum Name.
        self.input_bind_enums_dyn_alloc.append(prop_name)
        

    def draw(self, context):
        userpref = context.user_preferences
        wm = context.window_manager
        inputs = userpref.inputs
        
        layout = self.layout
        
        # General settings
        row = layout.row()
        col = row.column()
        
        if not bpy.data.is_saved:
            col = col.box()
            col.label("Save the .range first to use Input System!", icon="ERROR")
            col.label("It is recommended to create a folder for the project, Input System can create files, avoid saving projects in folder that need administrative access.", icon="QUESTION")
            return

        subInputs = col.row(align=True)
        subInputs.label(text="Input Maps:")

        sub = col.row()
        
        # General Variables
        path = bpy.path.abspath("//KeyMapping/")
        
        ############### Input Maps Section ###############
        
        if "input_maps_list" not in wm:
            wm["input_maps_list"] = []

        # Input Map Index Changed ? Update
        if wm.last_input_map_index != wm.input_map_index: 
            # Called by Force Update
            if wm.input_map_index == -1: 
                wm.input_map_index = 0
                
            wm.last_input_map_index = wm.input_map_index # Update Input Map Index
            
             # Load Input Maps
            input_maps = wm.input_map_list

            #print("InputMapList: Update!!!!!!!!!")
            if os.path.exists(path):
                files = os.listdir(path)
                
                input_maps_list = [file for file in files if file.endswith(".json")]
                wm["input_maps_list"] = input_maps_list # Store in windowmanager. Warning: IDPROP
                input_maps.clear()
                for input_map in input_maps_list:
                    item = input_maps.add()
                    item.name = input_map[:-5]
            else:
                input_maps.clear()
                
            # Reset Lists Values / Fix Values
            if wm.input_map_index > len(wm["input_maps_list"]) - 1: wm.input_map_index = 0 # In some cases we can delete the item from the list and the index will remain the same
            wm["input_table_dict"] = None
            wm.input_map_selected = ""
            wm.input_table_index = -1 # Force Update Input Table
                
        sub = sub.split(factor=0.36)
           
        sub.template_list("INPUTMAPS_UL_list", "", wm, "input_map_list", wm, "input_map_index", rows=21)
        subInputs.operator("wm.input_map_copy", text="", icon='COPYDOWN')
        subInputs.operator("wm.input_map_save", text="", icon='ZOOMIN')
        subInputs.operator("wm.input_map_remove", text="", icon='ZOOMOUT').remove_active = wm["input_maps_list"][wm.input_map_index] if wm["input_maps_list"] else ""
        
        ############### Input Table Section ###############
        subInputs.separator(factor=1)
        subInputs.label(text="Inputs Table:")
        
        sub = sub.split(factor=0.55)

        # Has input_maps_list and Input Table Index Changed ? Update
        if wm["input_maps_list"] and wm.last_input_table_index != wm.input_table_index:
            # Called by Force Update
            if wm.input_table_index == -1: 
                wm.input_table_index = 0
        
            wm.last_input_table_index = wm.input_table_index # Update Input Table Index
            wm.update_binding_properties = True
            
            wm.input_map_selected = wm["input_maps_list"][wm.input_map_index] if wm["input_maps_list"] else ""
            if wm.input_map_selected:
                input_tables_list = wm.input_table_list
                
                filepath = os.path.join(path, wm.input_map_selected)
                with open(filepath, 'r') as file: 
                    input_table_file = json.load(file)
                
                # Update Input List
                input_tables_list.clear()
                for table in input_table_file:
                    item = input_tables_list.add()
                    item.name = table
                    
        
        if wm.input_table_index > len(wm.input_table_list) - 1: wm.input_table_index = 0 # In some cases we can delete the item from the list and the index will remain the same
        wm.input_table_selected_name = wm.input_table_list[wm.input_table_index].name if wm.input_table_list else ""
        
        sub.template_list("INPUTTABLE_UL_list", "", wm, "input_table_list", wm, "input_table_index", rows=21)
        
        subInputs.operator("wm.input_map_table", text="", icon='COPYDOWN')
        addButton = subInputs.operator("wm.input_table_save", text="", icon='ZOOMIN')
        addButton.input_map_name = wm.input_map_selected
        
        removeButton = subInputs.operator("wm.input_table_remove", text="", icon='ZOOMOUT')
        removeButton.input_map_name = wm.input_map_selected
        removeButton.remove_active = wm.input_table_selected_name
        
        ############### Binding Properties Section ###############
        subInputs.label(text="Binding Properties:")
        
        sub = sub.box()
        if not wm.input_table_list:
            sub.label("Select an input table to edit", icon="ERROR")
            return
        
        # Input Table Changed ? Update
        if wm.update_binding_properties:
            wm.update_binding_properties = False # Updating.. Reset
        
            # load input table and save in windowManager
            path = bpy.path.abspath("//KeyMapping/")
            filepath = os.path.join(path, wm.input_map_selected)
            
            #print("InputTableList: Update!!!!!!!!!")
            input_table_list = ""
            with open(filepath, 'r') as file: 
                input_table_list = json.load(file)
                wm["input_table_dict"] = json.dumps(input_table_list) # Save in windowmanager in json format because if not it converts the values into IDProps 
                
            wm.binding_type_enum = input_table_list[wm.input_table_selected_name]["Type"] # Set Type
            wm.binding_control_type_enum = input_table_list[wm.input_table_selected_name]["ControlType"] # Set Control Type
            
            # Store Bindings Expanded Values
            values_dict = {}
            for bind in input_table_list[wm.input_table_selected_name]["Bindings"]:
                values_dict[bind] = False
            
            for process in input_table_list[wm.input_table_selected_name]["Processors"]:
                values_dict[process] = False
            wm["input_bindings_expanded_values"] = values_dict
            
            # Free/Add InputSystem_Keymap_Capture
            wm["InputSystem_Keymap_Capture"] = {}
            wm["InputSystem_Keymap_Sensitivity"] = {}
            
            # Delete all previously bind table enums
            if self.input_bind_enums_dyn_alloc:
                for prop_name in self.input_bind_enums_dyn_alloc:
                    if hasattr(wm, prop_name):
                        delattr(bpy.types.WindowManager, prop_name)
                self.input_bind_enums_dyn_alloc.clear()
            
            # Store Bind Table Enum Dynamic
            binding_dict = input_table_list[wm.input_table_selected_name]["Bindings"]
            
            for bind in binding_dict:
                binds = binding_dict[bind]
                
                # Generate Enum of Type of peripheral
                peripheralType = binding_dict[bind]["PERIPHERALTYPE"]["TYPE"]
                peripheralIndex = binding_dict[bind]["PERIPHERALTYPE"]["INDEX"]
                sensitivity = binding_dict[bind]["PERIPHERALTYPE"]["SENSITIVITY"]
                self.generate_dynamic_enum(wm, bind, peripheralType)
                self.generate_joystick_index_enum(wm, bind, peripheralIndex)
                self.generate_sensitivity_float(wm, bind, sensitivity)
                
                for i, bindType in enumerate(binds):
                    prop_name = bind
                    
                    if bindType == "BINDING":
                        bind_value = binding_dict[bind][bindType]["BUTTON"]
                        self.generate_bind_capture_key(wm, prop_name, bind_value)
                        self.generate_joystick_enum(wm, prop_name, bind_value)
                        
                        self.generate_string_custom_key(wm, prop_name) # For Custom key
                        self.generate_process_bool(wm, prop_name, False, "Custom key, write the desired key is not being captured by the capture key operator") # For Custom key
                        
                    elif bindType == "COMPOSITEPADS" or bindType == "COMPOSITEPADS3D":
                        # generate to COMPOSITEPADS or COMPOSITEPADS3D
                        for index in range(4 if bindType == "COMPOSITEPADS" else 6):
                            order = ["UP", "DOWN", "LEFT", "RIGHT", "FORWARD", "BACKWARD"]
                            bind_value = binding_dict[bind][bindType][order[index]]
                            prop_name = bind + str(index)
                            
                            self.generate_bind_capture_key(wm, prop_name, bind_value) # Generate Enum with json stored value by default
                            self.generate_joystick_enum(wm, prop_name, bind_value)
                            
                            self.generate_string_custom_key(wm, prop_name) # For Custom key
                            self.generate_process_bool(wm, prop_name, False, "Custom key, write the desired key is not being captured by the capture key operator") # For Custom key
                            
            # Store Processor Enum Dynamic
            processors_dict = input_table_list[wm.input_table_selected_name]["Processors"]
            
            # Generates values based on times a value is repeated, ex: vector(X,Y,Z) = 3 times ... same for the drawing
            for process in processors_dict:
                for index in range(self.replicate_times[process]):
                    bind_value = processors_dict[process][self.orderVector[index]]
                    process_name = process + str(index)
                    
                    process_type = self.processor_type[process]
                    if process_type == "BOOL":
                        self.generate_process_bool(wm, process_name, bind_value) # Generate Bool with json stored value by default
                    elif process_type[0] == "FLOAT":
                        min = process_type[1]
                        max = process_type[2]
                        self.generate_process_float(wm, process_name, min, max, bind_value) # Generate Float with json stored value by default
                            

        row = sub.split(factor=0.5)
        row.label(text="Return Type:", icon="NODETREE")
        row.prop(wm, "binding_type_enum", text="")
        binding_type_value = wm.binding_type_enum
        
        col = sub.column()
        if binding_type_value == "VALUE":
            box = col.box()
            row = box.row()
            row.label(text="Control Type", icon="ANIM")
            row.prop(wm, "binding_control_type_enum", text="")
            
        col.separator(factor=1)
        col.label(text="Bindings:", icon="OUTLINER_OB_LATTICE")
        
        binding_properties_dict = json.loads(wm["input_table_dict"])[wm.input_table_selected_name] if wm["input_table_dict"] != None else [] # For Draw Bindings and Store Dynamic Enums
        binding_dict = binding_properties_dict["Bindings"] if binding_properties_dict else []
        
        if not binding_dict:
            box = col.box()
            box.label("Nothing", icon="ERROR")
        
        # Draw Bindings
        for bind in binding_dict:
            box = col.box()
            row = box.row()
            expanded = wm["input_bindings_expanded_values"][bind]
            
            row.operator("wm.input_toggle_expand", text="", icon="TRIA_DOWN" if expanded else "TRIA_RIGHT", emboss=False).value = bind
            row.label(text=bind, icon="LOGIC")
            
            row = row.row(align=True)
            renameButton = row.operator("wm.input_binding_rename", text="", icon="GREASEPENCIL", emboss=False)
            renameButton.input_map_name = wm.input_map_selected
            renameButton.input_table_name = wm.input_table_selected_name
            renameButton.input_binding_name = bind
            
            removeBindButton = row.operator("wm.input_sys_remove_binding", text="", icon="ZOOMOUT", emboss=False)
            removeBindButton.input_table_name = wm.input_table_selected_name
            removeBindButton.input_name = bind
            removeBindButton.input_section_type = "Bindings"
            
            if (not expanded): continue
            
            # Draw PeripheralType
            row = box.column(align=True)
            
            row.prop(wm, f"dynamic_enum_{bind}", text="")
            
            peripheralType = getattr(wm, f"dynamic_enum_{bind}") # Get the peripheralType in realtime
            is_mouse = (peripheralType == "MOUSE")
            
            if peripheralType == "JOYSTICK":
                row.prop(wm, f"dynamic_enum_joystick_index_{bind}", text="Index")
                
            if peripheralType in ("JOYSTICK", "MOUSE"):
                row.prop(wm, f"dynamic_float_sensitivity_{bind}", text="Sensitivity")
            
            # Draw Binding Type
            binds = binding_dict[bind]
            for i, bindType in enumerate(binds):
                row = row.row()
                
                if bindType == "BINDING":
                    row = box.row()
                    row.label(text=" - Button:")
                    
                    # Custom Key
                    row.prop(wm, f"dynamic_bool_{bind}", text="")
                    useCustomKey = getattr(wm, f"dynamic_bool_{bind}")
                    
                    if not useCustomKey:
                        if peripheralType == "JOYSTICK":
                            keyName = bind
                            row.prop(wm, f"dynamic_enum_joystick_{keyName}", text="")
                        else:
                            keyValue = wm["InputSystem_Keymap_Capture"][bind]
                            getKeyButton = row.operator("wm.input_capture_key", text=keyValue)
                            getKeyButton.key = bind
                            getKeyButton.is_mouse = is_mouse
                    else:
                        row.prop(wm, f"dynamic_string_custom_key_{bind}", text="")
                    
                elif bindType == "COMPOSITEPADS" or bindType == "COMPOSITEPADS3D":
                    # Draw COMPOSITEPADS or COMPOSITEPADS3D
                    row = box.row()
                    
                    order = [" - Up Button:", " - Down Button:", " - Left Button:", " - Right Button:", " - Forward Button:", " - Backward Button:"]
                    
                    blockInputs = [] # 0-6
                    if peripheralType in ("JOYSTICK", "MOUSE"):
                        for index in range(4 if bindType == "COMPOSITEPADS" else 6):
                            keyName = bind+str(index)
                            if peripheralType == "JOYSTICK":
                                input = getattr(wm, f"dynamic_enum_joystick_{keyName}")
                            else:
                                input = wm["InputSystem_Keymap_Capture"][keyName]
                            if input in ("100", "101", "102", "103", "MOUSEX", "MOUSEY"): # This is using inputs that use two hatch values OR mouse values (movement), so let's remove the option
                                i = 1 if index in (0, 2, 4) else -1
                                blockInputs.append(index + i)
                    
                    for index in range(4 if bindType == "COMPOSITEPADS" else 6):
                        keyName = bind+str(index)
                        row.label(text=order[index])
                        
                        if not peripheralType == "JOYSTICK" and not peripheralType == "MOUSE":
                            # Custom Key
                            row.prop(wm, f"dynamic_bool_{keyName}", text="")
                            useCustomKey = getattr(wm, f"dynamic_bool_{keyName}")
                            
                            if not useCustomKey:
                                keyValue = wm["InputSystem_Keymap_Capture"][keyName]
                                getKeyButton = row.operator("wm.input_capture_key", text=keyValue)
                                getKeyButton.key = keyName
                                getKeyButton.is_mouse = is_mouse
                            else:
                                row.prop(wm, f"dynamic_string_custom_key_{keyName}", text="")
                        else:
                            if not index in blockInputs:
                                if peripheralType == "JOYSTICK":
                                    row.prop(wm, f"dynamic_enum_joystick_{keyName}", text="")
                                else:
                                    # Draw input_capture_key instread
                                    keyValue = wm["InputSystem_Keymap_Capture"][keyName]
                                    getKeyButton = row.operator("wm.input_capture_key", text=keyValue)
                                    getKeyButton.key = keyName
                                    getKeyButton.is_mouse = is_mouse
                            else:
                                # Blocked inputs
                                row.label(text="Input in Use!", icon="SAVE_COPY")
                                if peripheralType == "JOYSTICK":
                                    value = getattr(wm, f"dynamic_enum_joystick_{keyName}")
                                    
                                    if value != "0": # set to NONE
                                        setattr(wm, f"dynamic_enum_joystick_{keyName}", "0")
                                else:
                                    # Get mouse value
                                    value = wm["InputSystem_Keymap_Capture"][keyName]
                                    
                                    if value != "0": # set to NONE
                                        wm["InputSystem_Keymap_Capture"][keyName] = "NOKEY"
                                
                        
                        row = box.row()
                    
                    
        # Draw Processors
        col.separator(factor=1)
        row = col.row()
        row.label(text="Processors:", icon="SCRIPTWIN")
        AddProcessorButton = row.operator("wm.input_add_processor", text="", icon='ZOOMIN', emboss=False)
        AddProcessorButton.input_map_name = wm.input_map_selected
        AddProcessorButton.input_table_name = wm.input_table_selected_name
        
        processors_dict = binding_properties_dict["Processors"] if binding_properties_dict else []
        
        if not processors_dict:
            box = col.box()
            box.label("Nothing", icon="ERROR")
        
        for process in processors_dict:
            box = col.box()
            row = box.row(align=1)
            expanded = wm["input_bindings_expanded_values"][process]
            
            row.operator("wm.input_toggle_expand", text="", icon="TRIA_DOWN" if expanded else "TRIA_RIGHT", emboss=False).value = process
            row.label(text=process.lower())
            
            # ToDO
            removeBindButton = row.operator("wm.input_sys_remove_binding", text="", icon="ZOOMOUT", emboss=False)
            removeBindButton.input_table_name = wm.input_table_selected_name
            removeBindButton.input_name = process
            removeBindButton.input_section_type = "Processors"
            
            if (not expanded): continue
            
            # Draw Processor
            for index in range(self.replicate_times[process]):
                row = box.row(align=1)
                row.label(text=f"{self.orderVector[index]}")
                
                process_type = self.processor_type[process]
                propertyType = None
                
                if process_type == "BOOL":
                    propertyType = "dynamic_bool"
                elif process_type[0] == "FLOAT":
                    propertyType = "dynamic_float"
                
                row.prop(wm, f"{propertyType}_{process + str(index)}", text="")
                    
            
        # Save Binding Button
        save_config_button = col.operator("wm.input_sys_save_binding", text="Save Binding Configuration", icon='SAVE_AS')
        save_config_button.input_map_name = wm.input_map_selected
        save_config_button.input_table_name = wm.input_table_selected_name
        
        save_config_button.replicate_times = str(self.replicate_times)
        save_config_button.processor_type = str(self.processor_type)
        save_config_button.orderVector = str(self.orderVector)
        
        if (wm.force_save_bindings):
            wm.force_save_bindings = False # reset
        
            bpy.ops.wm.input_sys_save_binding('INVOKE_DEFAULT', input_map_name=save_config_button.input_map_name, 
                input_table_name=save_config_button.input_table_name, replicate_times=save_config_button.replicate_times, 
                processor_type=save_config_button.processor_type, orderVector=save_config_button.orderVector)

class USERPREF_MT_addons_online_resources(Menu):
    bl_label = "Online Resources"

    # menu to open web-pages with addons development guides
    def draw(self, context):
        layout = self.layout

        layout.operator(
            "wm.url_open", text="Add-ons Catalog", icon='URL',
        ).url = "http://wiki.blender.org/index.php/Extensions:2.6/Py/Scripts"

        layout.separator(factor=1)

        layout.operator(
            "wm.url_open", text="How to share your add-on", icon='URL',
        ).url = "http://wiki.blender.org/index.php/Dev:Py/Sharing"
        layout.operator(
            "wm.url_open", text="Add-on Guidelines", icon='URL',
        ).url = "http://wiki.blender.org/index.php/Dev:2.5/Py/Scripts/Guidelines/Addons"
        layout.operator(
            "wm.url_open", text="API Concepts", icon='URL',
        ).url = bpy.types.WM_OT_doc_view._prefix + "/info_quickstart.html"
        layout.operator(
            "wm.url_open", text="Add-on Tutorial", icon='URL',
        ).url = bpy.types.WM_OT_doc_view._prefix + "/info_tutorial_addon.html"


class USERPREF_PT_addons(Panel):
    bl_space_type = 'USER_PREFERENCES'
    bl_label = "Add-ons"
    bl_region_type = 'WINDOW'
    bl_options = {'HIDE_HEADER'}

    _support_icon_mapping = {
        'OFFICIAL': 'FILE_BLEND',
        'COMMUNITY': 'POSE_DATA',
        'TESTING': 'MOD_EXPLODE',
    }

    @classmethod
    def poll(cls, context):
        userpref = context.user_preferences
        return (userpref.active_section == 'ADDONS')

    @staticmethod
    def is_user_addon(mod, user_addon_paths):
        import os

        if not user_addon_paths:
            for path in (
                    bpy.utils.script_path_user(),
                    bpy.utils.script_path_pref(),
            ):
                if path is not None:
                    user_addon_paths.append(os.path.join(path, "addons"))

        for path in user_addon_paths:
            if bpy.path.is_subdir(mod.__file__, path):
                return True
        return False

    @staticmethod
    def draw_error(layout, message):
        lines = message.split("\n")
        box = layout.box()
        sub = box.row()
        sub.label(lines[0])
        sub.label(icon='ERROR')
        for l in lines[1:]:
            box.label(l)

    def draw(self, context):
        import os
        import addon_utils

        layout = self.layout

        wm = context.window_manager
        prefs = context.user_preferences
        used_ext = {ext.module for ext in prefs.addons}

        addon_user_dirs = tuple(
            p for p in (
                os.path.join(prefs.filepaths.script_directory, "addons"),
                bpy.utils.user_resource('SCRIPTS', "addons"),
            )
            if p
        )

        # collect the categories that can be filtered on
        addons = [
            (mod, addon_utils.module_bl_info(mod))
            for mod in addon_utils.modules(refresh=False)
        ]

        split = layout.split(factor=0.2)
        col = split.column()
        col.prop(wm, "addon_search", text="", icon='VIEWZOOM')

        col.label(text="Supported Level")
        col.prop(wm, "addon_support", expand=True)

        col.label(text="Categories")
        col.prop(wm, "addon_filter", expand=True)

        col = split.column()

        # set in addon_utils.modules_refresh()
        if addon_utils.error_duplicates:
            box = col.box()
            row = box.row()
            row.label("Multiple add-ons with the same name found!")
            row.label(icon='ERROR')
            box.label("Please delete one of each pair:")
            for (addon_name, addon_file, addon_path) in addon_utils.error_duplicates:
                box.separator(factor=1)
                sub_col = box.column(align=True)
                sub_col.label(addon_name + ":")
                sub_col.label("    " + addon_file)
                sub_col.label("    " + addon_path)

        if addon_utils.error_encoding:
            self.draw_error(
                col,
                "One or more addons do not have UTF-8 encoding\n"
                "(see console for details)",
            )

        filter = wm.addon_filter
        search = wm.addon_search.lower()
        support = wm.addon_support

        # initialized on demand
        user_addon_paths = []

        for mod, info in addons:
            module_name = mod.__name__

            is_enabled = module_name in used_ext

            if info["support"] not in support:
                continue

            # check if addon should be visible with current filters
            if (
                    (filter == "All") or
                    (filter == info["category"]) or
                    (filter == "Enabled" and is_enabled) or
                    (filter == "Disabled" and not is_enabled) or
                    (filter == "User" and (mod.__file__.startswith(addon_user_dirs)))
            ):
                if search and search not in info["name"].lower():
                    if info["author"]:
                        if search not in info["author"].lower():
                            continue
                    else:
                        continue

                # Addon UI Code
                col_box = col.column()
                box = col_box.box()
                colsub = box.column()
                row = colsub.row(align=True)

                row.operator(
                    "wm.addon_expand",
                    icon='TRIA_DOWN' if info["show_expanded"] else 'TRIA_RIGHT',
                    emboss=False,
                ).module = module_name

                row.operator(
                    "wm.addon_disable" if is_enabled else "wm.addon_enable",
                    icon='CHECKBOX_HLT' if is_enabled else 'CHECKBOX_DEHLT', text="",
                    emboss=False,
                ).module = module_name

                sub = row.row()
                sub.active = is_enabled
                sub.label(text="%s: %s" % (info["category"], info["name"]))
                if info["warning"]:
                    sub.label(icon='ERROR')

                # icon showing support level.
                sub.label(icon=self._support_icon_mapping.get(info["support"], 'QUESTION'))

                # Expanded UI (only if additional info is available)
                if info["show_expanded"]:
                    if info["description"]:
                        split = colsub.row().split(factor=0.15)
                        split.label(text="Description:")
                        split.label(text=info["description"])
                    if info["location"]:
                        split = colsub.row().split(factor=0.15)
                        split.label(text="Location:")
                        split.label(text=info["location"])
                    if mod:
                        split = colsub.row().split(factor=0.15)
                        split.label(text="File:")
                        split.label(text=mod.__file__, translate=False)
                    if info["author"]:
                        split = colsub.row().split(factor=0.15)
                        split.label(text="Author:")
                        split.label(text=info["author"], translate=False)
                    if info["version"]:
                        split = colsub.row().split(factor=0.15)
                        split.label(text="Version:")
                        split.label(text=".".join(str(x) for x in info["version"]), translate=False)
                    if info["warning"]:
                        split = colsub.row().split(factor=0.15)
                        split.label(text="Warning:")
                        split.label(text="  " + info["warning"], icon='ERROR')

                    user_addon = USERPREF_PT_addons.is_user_addon(mod, user_addon_paths)
                    tot_row = bool(info["wiki_url"]) + bool(user_addon)

                    if tot_row:
                        split = colsub.row().split(factor=0.15)
                        split.label(text="Internet:")
                        if info["wiki_url"]:
                            split.operator(
                                "wm.url_open", text="Documentation", icon='HELP',
                            ).url = info["wiki_url"]
                        # Only add "Report a Bug" button if tracker_url is set
                        # or the add-on is bundled (use official tracker then).
                        if info.get("tracker_url") or not user_addon:
                            split.operator(
                                "wm.url_open", text="Report a Bug", icon='URL',
                            ).url = info.get(
                                "tracker_url",
                                "https://developer.blender.org/maniphest/task/edit/form/2",
                            )
                        if user_addon:
                            split.operator(
                                "wm.addon_remove", text="Remove", icon='CANCEL',
                            ).module = mod.__name__

                        for i in range(4 - tot_row):
                            split.separator(factor=1)

                    # Show addon user preferences
                    if is_enabled:
                        addon_preferences = prefs.addons[module_name].preferences
                        if addon_preferences is not None:
                            draw = getattr(addon_preferences, "draw", None)
                            if draw is not None:
                                addon_preferences_class = type(addon_preferences)
                                box_prefs = col_box.box()
                                box_prefs.label("Preferences:")
                                addon_preferences_class.layout = box_prefs
                                try:
                                    draw(context)
                                except:
                                    import traceback
                                    traceback.print_exc()
                                    box_prefs.label(text="Error (see console)", icon='ERROR')
                                del addon_preferences_class.layout

        # Append missing scripts
        # First collect scripts that are used but have no script file.
        module_names = {mod.__name__ for mod, info in addons}
        missing_modules = {ext for ext in used_ext if ext not in module_names}

        if missing_modules and filter in {"All", "Enabled"}:
            col.column().separator(factor=1)
            col.column().label(text="Missing script files")

            module_names = {mod.__name__ for mod, info in addons}
            for module_name in sorted(missing_modules):
                is_enabled = module_name in used_ext
                # Addon UI Code
                box = col.column().box()
                colsub = box.column()
                row = colsub.row(align=True)

                row.label(text="", icon='ERROR')

                if is_enabled:
                    row.operator(
                        "wm.addon_disable", icon='CHECKBOX_HLT', text="", emboss=False,
                    ).module = module_name

                row.label(text=module_name, translate=False)


classes = (
    USERPREF_HT_header,
    USERPREF_PT_navigation,
    USERPREF_MT_interaction_presets,
    USERPREF_MT_app_templates,
    USERPREF_MT_appconfigs,
    USERPREF_PT_interface,
    USERPREF_PT_edit,
    USERPREF_PT_system_general,
    USERPREF_MT_interface_theme_presets,
    USERPREF_PT_theme,
    USERPREF_PT_file,
    USERPREF_MT_ndof_settings,
    USERPREF_MT_keyconfigs,
    USERPREF_PT_input,
    USERPREF_MT_input_system_presets,
    USERPREF_PT_input_system,
    USERPREF_MT_addons_online_resources,
    USERPREF_PT_addons,
)

if __name__ == "__main__":  # only for live edit.
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)
