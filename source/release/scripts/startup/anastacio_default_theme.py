"""Applies the AnastacioGames defaults on the user's first launch."""

import os

import bpy

_MARKER_NAME = "anastacio_default_theme_applied"
_PRESET_XML_MAP = (
    ("user_preferences.themes[0]", "Theme"),
    ("user_preferences.ui_styles[0]", "ThemeStyle"),
)


def _marker_path():
    return os.path.join(bpy.utils.user_resource('CONFIG'), _MARKER_NAME)


def _apply_default_preferences():
    """Match the initial Interface and Editing settings shipped by Range."""
    prefs = bpy.context.user_preferences
    view = prefs.view
    edit = prefs.edit

    view.ui_scale = 1.0
    view.ui_line_width = 'AUTO'
    view.header_size = 26
    view.show_tooltips = True
    view.show_tooltips_python = True
    view.show_developer_ui = True
    view.show_object_info = True
    view.show_large_cursors = False
    view.show_view_name = True
    view.show_playback_fps = True
    view.use_global_scene = True
    view.object_origin_size = 6
    view.use_mouse_depth_cursor = True
    view.use_cursor_lock_adjust = True
    view.use_mouse_depth_navigate = False
    view.use_zoom_to_mouse = False
    view.use_rotate_around_active = False
    view.use_global_pivot = False
    view.use_camera_lock_parent = True
    view.use_auto_perspective = False
    view.smooth_view = 0
    view.rotation_angle = 15.0
    view.view2d_grid_spacing_min = 35
    view.timecode_style = 'MINIMAL'
    view.view_frame_type = 'KEEP_RANGE'
    view.show_manipulator = True
    view.manipulator_size = 100
    view.manipulator_handle_size = 21
    view.manipulator_hotspot = 4
    view.show_mini_axis = True
    view.mini_axis_size = 21
    view.mini_axis_brightness = 8
    view.use_mouse_over_open = True
    view.open_toplevel_delay = 5
    view.open_sublevel_delay = 2
    view.pie_animation_timeout = 6
    view.pie_initial_timeout = 0
    view.pie_menu_radius = 100
    view.pie_menu_threshold = 12
    view.pie_menu_confirm = 0
    view.show_splash = True
    view.show_layout_ui = True
    view.show_view3d_cursor = True
    view.use_quit_dialog = True

    edit.material_link = 'OBDATA'
    edit.use_enter_edit_mode = False
    edit.object_align = 'WORLD'
    edit.use_global_undo = True
    edit.undo_steps = 32
    edit.undo_memory_limit = 0
    edit.use_auto_keying = False
    edit.use_auto_keying_warning = True
    edit.use_keyframe_insert_available = False
    edit.use_keyframe_insert_needed = False
    edit.use_visual_keying = False
    edit.use_insertkey_xyz_to_rgb = False
    edit.keyframe_new_interpolation_type = 'BEZIER'
    edit.keyframe_new_handle_type = 'AUTO_CLAMPED'
    edit.use_drag_immediately = False
    edit.use_negative_frames = True
    edit.fcurve_unselected_alpha = 0.25
    edit.grease_pencil_eraser_radius = 1
    edit.grease_pencil_manhattan_distance = 1
    edit.grease_pencil_euclidean_distance = 2
    edit.grease_pencil_default_color = (0.0, 0.0, 0.0, 1.0)
    edit.use_grease_pencil_simplify_stroke = False
    edit.sculpt_paint_overlay_color = (0.0, 0.0, 0.0)
    edit.use_duplicate_mesh = False
    edit.use_duplicate_surface = False
    edit.use_duplicate_curve = False
    edit.use_duplicate_text = False
    edit.use_duplicate_metaball = False
    edit.use_duplicate_armature = True
    edit.use_duplicate_lamp = False
    edit.use_duplicate_material = False
    edit.use_duplicate_texture = False
    edit.use_duplicate_fcurve = False
    edit.use_duplicate_action = False
    edit.use_duplicate_particle = False
    edit.node_margin = 80


def _apply_default_theme(dummy1=None, dummy2=None):
    marker = _marker_path()
    if os.path.exists(marker):
        return

    for path in bpy.utils.preset_paths("interface_theme"):
        filepath = os.path.join(path, "anastaciogames.xml")
        if os.path.exists(filepath):
            try:
                import rna_xml
                rna_xml.xml_file_run(bpy.context, filepath, _PRESET_XML_MAP, verbose=False)
                _apply_default_preferences()
            except Exception:
                return

            try:
                result = bpy.ops.wm.save_userpref()
            except RuntimeError:
                result = {'CANCELLED'}

            if 'FINISHED' in result:
                try:
                    os.makedirs(os.path.dirname(marker), exist_ok=True)
                    with open(marker, "w") as f:
                        f.write("1")
                except OSError:
                    pass
            return


def register():
    bpy.app.handlers.load_post.append(_apply_default_theme)
    try:
        _apply_default_theme()
    except AttributeError:
        pass


def unregister():
    if _apply_default_theme in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_apply_default_theme)
