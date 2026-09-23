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
from bpy.types import Panel, Menu
from rna_prop_ui import PropertyPanel


class CameraButtonsPanel:
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"

    @classmethod
    def poll(cls, context):
        engine = context.scene.render.engine
        return context.camera and (engine in cls.COMPAT_ENGINES)


class CAMERA_MT_presets(Menu):
    bl_label = "Camera Presets"
    preset_subdir = "camera"
    preset_operator = "script.execute_preset"
    COMPAT_ENGINES = {'BLENDER_RENDER', 'BLENDER_GAME'}
    draw = Menu.draw_preset


class SAFE_AREAS_MT_presets(Menu):
    bl_label = "Camera Presets"
    preset_subdir = "safe_areas"
    preset_operator = "script.execute_preset"
    COMPAT_ENGINES = {'BLENDER_RENDER', 'BLENDER_GAME'}
    draw = Menu.draw_preset


class DATA_PT_context_camera(CameraButtonsPanel, Panel):
    bl_label = ""
    bl_options = {'HIDE_HEADER'}
    COMPAT_ENGINES = {'BLENDER_RENDER', 'BLENDER_GAME'}

    def draw(self, context):
        layout = self.layout

        ob = context.object
        cam = context.camera
        space = context.space_data

        split = layout.split(factor=0.65)
        if ob:
            split.template_ID(ob, "data")
            split.separator(factor=1)
        elif cam:
            split.template_ID(space, "pin_id")
            split.separator(factor=1)


class DATA_PT_camera(CameraButtonsPanel, Panel):
    bl_label = "Camera"
    COMPAT_ENGINES = {'BLENDER_RENDER', 'BLENDER_GAME'}

    def draw(self, context):
        layout = self.layout

        cam = context.camera
        scene = context.scene
        render = scene.render
        engine = render.engine

        main_box = layout.box()
        main_box.label(text="Camera:", icon="CAMERA_DATA")

        # --- Lens ---
        row = main_box.row(align=True)
        row.prop(cam, "show_expanded_cam_lens", text="Lens",
                 icon='TRIA_DOWN' if cam.show_expanded_cam_lens else 'TRIA_RIGHT', emboss=True)

        if cam.show_expanded_cam_lens:
            box = main_box.box()
            box.label(text="Type:", icon="CAMERA_DATA")
            box.row().prop(cam, "type", expand=True)

            split = box.split()

            col = split.column()
            if cam.type == 'PERSP':
                row = col.row()
                if cam.lens_unit == 'MILLIMETERS':
                    row.prop(cam, "lens")
                elif cam.lens_unit == 'FOV':
                    row.prop(cam, "angle")
                row.prop(cam, "lens_unit", text="")

            elif cam.type == 'ORTHO':
                col.prop(cam, "ortho_scale")

            elif cam.type == 'PANO':
                if engine == 'CYCLES':
                    ccam = cam.cycles
                    col.prop(ccam, "panorama_type", text="Type")
                    if ccam.panorama_type == 'FISHEYE_EQUIDISTANT':
                        col.prop(ccam, "fisheye_fov")
                    elif ccam.panorama_type == 'FISHEYE_EQUISOLID':
                        row = box.row()
                        row.prop(ccam, "fisheye_lens", text="Lens")
                        row.prop(ccam, "fisheye_fov")
                    elif ccam.panorama_type == 'EQUIRECTANGULAR':
                        row = box.row()
                        sub = row.column(align=True)
                        sub.prop(ccam, "latitude_min")
                        sub.prop(ccam, "latitude_max")
                        sub = row.column(align=True)
                        sub.prop(ccam, "longitude_min")
                        sub.prop(ccam, "longitude_max")
                elif engine == 'BLENDER_RENDER':
                    row = col.row()
                    if cam.lens_unit == 'MILLIMETERS':
                        row.prop(cam, "lens")
                    elif cam.lens_unit == 'FOV':
                        row.prop(cam, "angle")
                    row.prop(cam, "lens_unit", text="")

            box = main_box.box()
            box.label(text="Shift & Clipping:", icon="SETTINGS")
            split = box.split()

            col = split.column(align=True)
            col.label(text="Shift:")
            col.prop(cam, "shift_x", text="X")
            col.prop(cam, "shift_y", text="Y")

            col = split.column(align=True)
            col.label(text="Clipping:")
            col.prop(cam, "clip_start", text="Start")
            col.prop(cam, "clip_end", text="End")

        # --- Sensor ---
        row = main_box.row(align=True)
        row.prop(cam, "show_expanded_cam_sensor", text="Sensor",
                 icon='TRIA_DOWN' if cam.show_expanded_cam_sensor else 'TRIA_RIGHT', emboss=True)

        if cam.show_expanded_cam_sensor:
            box = main_box.box()

            row = box.row(align=True)
            row.menu("CAMERA_MT_presets", text=bpy.types.CAMERA_MT_presets.bl_label)
            row.operator("camera.preset_add", text="", icon='ZOOMIN')
            row.operator("camera.preset_add", text="", icon='ZOOMOUT').remove_active = True

            box.label(text="Sensor:", icon="CAMERA_DATA")

            split = box.split()

            col = split.column(align=True)
            if cam.sensor_fit == 'AUTO':
                col.prop(cam, "sensor_width", text="Size")
            else:
                sub = col.column(align=True)
                sub.active = cam.sensor_fit == 'HORIZONTAL'
                sub.prop(cam, "sensor_width", text="Width")
                sub = col.column(align=True)
                sub.active = cam.sensor_fit == 'VERTICAL'
                sub.prop(cam, "sensor_height", text="Height")

            col = split.column(align=True)
            col.prop(cam, "sensor_fit", text="")

        # --- Depth of Field ---
        row = main_box.row(align=True)
        row.prop(cam, "show_expanded_cam_dof", text="Depth of Field",
                 icon='TRIA_DOWN' if cam.show_expanded_cam_dof else 'TRIA_RIGHT', emboss=True)

        if cam.show_expanded_cam_dof:
            dof_options = cam.gpu_dof

            box = main_box.box()
            box.label(text="Depth of Field:", icon="CAMERA_DATA")
            split = box.split()

            col = split.column()
            col.label(text="Focus:")
            col.prop(cam, "dof_object", text="")
            sub = col.column()
            sub.active = (cam.dof_object is None)
            sub.prop(cam, "dof_distance", text="Distance")

            hq_support = dof_options.is_hq_supported
            col = split.column(align=True)
            col.label("Viewport:")
            sub = col.column()
            sub.active = hq_support
            sub.prop(dof_options, "use_high_quality")
            col.prop(dof_options, "fstop")
            if dof_options.use_high_quality and hq_support:
                col.prop(dof_options, "blades")

        # --- Display ---
        row = main_box.row(align=True)
        row.prop(cam, "show_expanded_cam_display", text="Display",
                 icon='TRIA_DOWN' if cam.show_expanded_cam_display else 'TRIA_RIGHT', emboss=True)

        if cam.show_expanded_cam_display:
            box = main_box.box()
            box.label(text="Display:", icon="RESTRICT_VIEW_OFF")
            split = box.split()

            col = split.column()
            col.prop(cam, "show_limits", text="Limits")
            col.prop(cam, "show_mist", text="Mist")

            col.prop(cam, "show_sensor", text="Sensor")
            col.prop(cam, "show_name", text="Name")

            col = split.column()
            col.prop_menu_enum(cam, "show_guide")
            col.separator(factor=1)
            col.prop(cam, "draw_size", text="Size")
            col.separator(factor=1)
            col.prop(cam, "show_passepartout", text="Passepartout")
            sub = col.column()
            sub.active = cam.show_passepartout
            sub.prop(cam, "passepartout_alpha", text="Alpha", slider=True)

        # --- Safe Areas ---
        row = main_box.row(align=True)
        row.prop(cam, "show_expanded_cam_safe_areas", text="Safe Areas",
                 icon='TRIA_DOWN' if cam.show_expanded_cam_safe_areas else 'TRIA_RIGHT', emboss=True)
        row.prop(cam, "show_safe_areas", text="")

        if cam.show_expanded_cam_safe_areas:
            safe_data = scene.safe_areas

            box = main_box.box()
            box.label(text="Safe Areas:", icon="RESTRICT_VIEW_OFF")
            draw_display_safe_settings(box, safe_data, cam)

        # --- Levels of Detail (game only) ---
        if engine == 'BLENDER_GAME':
            row = main_box.row(align=True)
            row.prop(cam, "show_expanded_cam_lod", text="Levels of Detail",
                     icon='TRIA_DOWN' if cam.show_expanded_cam_lod else 'TRIA_RIGHT', emboss=True)

            if cam.show_expanded_cam_lod:
                box = main_box.box()
                box.label(text="Levels of Detail:", icon="MOD_SUBSURF")
                col = box.column()
                col.prop(cam, "lod_factor", text="Distance Factor")

            box = main_box.box()
            box.label(text="Optimization Reference:", icon="CAMERA_DATA")
            if context.object == scene.camera:
                box.label(text="This active camera supplies the runtime distance reference.")
            else:
                box.label(text="The active Scene camera supplies the runtime distance reference.")
            box.label(text="Foliage and Grass use it when Foliage Optimization is enabled.")

        # --- Culling (game only) ---
        if engine == 'BLENDER_GAME':
            row = main_box.row(align=True)
            row.prop(cam, "show_expanded_cam_culling", text="Culling",
                     icon='TRIA_DOWN' if cam.show_expanded_cam_culling else 'TRIA_RIGHT', emboss=True)

            if cam.show_expanded_cam_culling:
                box = main_box.box()
                box.label(text="Culling:", icon="GHOST_ENABLED")
                split = box.split()

                col = split.column()
                col.label(text="Frustum Culling:")
                col.prop(cam, "show_frustum")
                col.prop(cam, "show_culling_box")
                col.prop(cam, "override_culling")

                col = split.column()
                col.label(text="Object Activity:")
                col.prop(cam, "use_object_activity_culling")

                box = main_box.box()
                box.label(text="Shadow Cascade Cache:", icon="TIME")
                box.prop(cam, "csm_cache_max_stale_frames", text="Tolerance", slider=True)

        # --- Custom Viewport (game only) ---
        if engine == 'BLENDER_GAME':
            row = main_box.row(align=True)
            row.prop(cam, "show_expanded_cam_viewport", text="Custom Viewport",
                     icon='TRIA_DOWN' if cam.show_expanded_cam_viewport else 'TRIA_RIGHT', emboss=True)
            row.prop(cam, "use_viewport", text="")

            if cam.show_expanded_cam_viewport:
                viewport = cam.viewport

                box = main_box.box()
                box.label(text="Viewport Ratios:", icon="SETTINGS")
                split = box.split()
                split.active = cam.use_viewport

                col = split.column()
                col.prop(viewport, "left_ratio")
                col.prop(viewport, "right_ratio")

                col = split.column()
                col.prop(viewport, "bottom_ratio")
                col.prop(viewport, "top_ratio")

        # --- Stereoscopy (render only, multiview stereo3d) ---
        if (engine == 'BLENDER_RENDER' and render.use_multiview and
                render.views_format == 'STEREO_3D'):
            row = main_box.row(align=True)
            row.prop(cam, "show_expanded_cam_stereoscopy", text="Stereoscopy",
                     icon='TRIA_DOWN' if cam.show_expanded_cam_stereoscopy else 'TRIA_RIGHT', emboss=True)

            if cam.show_expanded_cam_stereoscopy:
                st = cam.stereo

                is_spherical_stereo = cam.type != 'ORTHO' and render.use_spherical_stereo
                use_spherical_stereo = is_spherical_stereo and st.use_spherical_stereo

                box = main_box.box()
                box.label(text="Convergence:", icon="CAMERA_STEREO")
                col = box.column()
                col.row().prop(st, "convergence_mode", expand=True)

                sub = col.column()
                sub.active = st.convergence_mode != 'PARALLEL'
                sub.prop(st, "convergence_distance")

                col.prop(st, "interocular_distance")

                if is_spherical_stereo:
                    box = main_box.box()
                    box.label(text="Spherical Stereo:", icon="WORLD")
                    col = box.column()
                    col.separator(factor=1)
                    row = col.row()
                    row.prop(st, "use_spherical_stereo")
                    sub = row.row()
                    sub.active = st.use_spherical_stereo
                    sub.prop(st, "use_pole_merge")
                    row = col.row(align=True)
                    row.active = st.use_pole_merge
                    row.prop(st, "pole_merge_angle_from")
                    row.prop(st, "pole_merge_angle_to")

                box = main_box.box()
                box.label(text="Pivot:", icon="ROTATE")
                row = box.row()
                row.active = not use_spherical_stereo
                row.prop(st, "pivot", expand=True)


bpy.types.Camera.show_expanded_cam_lens = bpy.props.BoolProperty(name="Expanded", default=False)
bpy.types.Camera.show_expanded_cam_sensor = bpy.props.BoolProperty(name="Expanded", default=False)
bpy.types.Camera.show_expanded_cam_dof = bpy.props.BoolProperty(name="Expanded", default=False)
bpy.types.Camera.show_expanded_cam_display = bpy.props.BoolProperty(name="Expanded", default=False)
bpy.types.Camera.show_expanded_cam_safe_areas = bpy.props.BoolProperty(name="Expanded", default=False)
bpy.types.Camera.show_expanded_cam_lod = bpy.props.BoolProperty(name="Expanded", default=False)
bpy.types.Camera.show_expanded_cam_culling = bpy.props.BoolProperty(name="Expanded", default=False)
bpy.types.Camera.show_expanded_cam_viewport = bpy.props.BoolProperty(name="Expanded", default=False)
bpy.types.Camera.show_expanded_cam_stereoscopy = bpy.props.BoolProperty(name="Expanded", default=False)


class DATA_PT_custom_props_camera(CameraButtonsPanel, PropertyPanel, Panel):
    COMPAT_ENGINES = {'BLENDER_RENDER', 'BLENDER_GAME'}
    _context_path = "object.data"
    _property_type = bpy.types.Camera


def draw_display_safe_settings(layout, safe_data, settings):
    show_safe_areas = settings.show_safe_areas
    show_safe_center = settings.show_safe_center

    split = layout.split()

    col = split.column()
    row = col.row(align=True)
    row.menu("SAFE_AREAS_MT_presets", text=bpy.types.SAFE_AREAS_MT_presets.bl_label)
    row.operator("safe_areas.preset_add", text="", icon='ZOOMIN')
    row.operator("safe_areas.preset_add", text="", icon='ZOOMOUT').remove_active = True

    col = split.column()
    col.prop(settings, "show_safe_center", text="Center-Cut Safe Areas")

    split = layout.split()
    col = split.column()
    col.active = show_safe_areas
    col.prop(safe_data, "title", slider=True)
    col.prop(safe_data, "action", slider=True)

    col = split.column()
    col.active = show_safe_areas and show_safe_center
    col.prop(safe_data, "title_center", slider=True)
    col.prop(safe_data, "action_center", slider=True)


classes = (
    CAMERA_MT_presets,
    SAFE_AREAS_MT_presets,
    DATA_PT_context_camera,
    DATA_PT_camera,
    # DATA_PT_custom_props_camera,  # disabled: Custom Properties panel unused
)

if __name__ == "__main__":  # only for live edit.
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)
