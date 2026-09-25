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
        engine = context.scene.render.engine

        # --- Lens ---
        box = layout.box()
        box.label(text="Lens:", icon="CAMERA_DATA")
        if engine == 'BLENDER_GAME':
            # The game only has perspective and orthographic projections.
            row = box.row()
            row.prop_enum(cam, "type", 'PERSP')
            row.prop_enum(cam, "type", 'ORTHO')
            if cam.type == 'PANO':
                box.label(text="Panoramic is not supported in the game, it renders as Orthographic", icon='ERROR')
        else:
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

        # --- Shift & Clipping ---
        box = layout.box()
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
        box = layout.box()
        box.label(text="Sensor:", icon="CAMERA_DATA")

        # Real-camera presets only matter for rendering; Size and Fit still drive the game FOV.
        if engine != 'BLENDER_GAME':
            row = box.row(align=True)
            row.menu("CAMERA_MT_presets", text=bpy.types.CAMERA_MT_presets.bl_label)
            row.operator("camera.preset_add", text="", icon='ZOOMIN')
            row.operator("camera.preset_add", text="", icon='ZOOMOUT').remove_active = True

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

        # --- Stereo ---
        # The Depth of Field panel is hidden in the game, but its distance is the stereo focal length.
        if engine == 'BLENDER_GAME' and context.scene.game_settings.stereo == 'STEREO':
            box = layout.box()
            box.label(text="Stereo:", icon="CAMERA_STEREO")
            box.prop(cam, "dof_distance", text="Focal Distance")
            if cam.dof_distance == 0.0:
                box.label(text="0 = automatic (30 × Eye Separation)", icon='INFO')


class DATA_PT_camera_dof(CameraButtonsPanel, Panel):
    bl_label = "Depth of Field"
    bl_options = {'DEFAULT_CLOSED'}
    # Viewport-only effect: the game engine never applies it, so it's hidden there.
    COMPAT_ENGINES = {'BLENDER_RENDER'}

    def draw(self, context):
        layout = self.layout

        cam = context.camera
        dof_options = cam.gpu_dof

        box = layout.box()
        box.label(text="Focus:", icon="CAMERA_DATA")
        box.prop(cam, "dof_object", text="")
        sub = box.column()
        sub.active = (cam.dof_object is None)
        sub.prop(cam, "dof_distance", text="Distance")

        hq_support = dof_options.is_hq_supported
        box = layout.box()
        box.label(text="Viewport:", icon="RESTRICT_VIEW_OFF")
        col = box.column(align=True)
        sub = col.column()
        sub.active = hq_support
        sub.prop(dof_options, "use_high_quality")
        col.prop(dof_options, "fstop")
        if dof_options.use_high_quality and hq_support:
            col.prop(dof_options, "blades")


class DATA_PT_camera_display(CameraButtonsPanel, Panel):
    bl_label = "Display"
    bl_options = {'DEFAULT_CLOSED'}
    COMPAT_ENGINES = {'BLENDER_RENDER', 'BLENDER_GAME'}

    def draw(self, context):
        layout = self.layout

        cam = context.camera

        box = layout.box()
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


class DATA_PT_camera_safe_areas(CameraButtonsPanel, Panel):
    bl_label = "Safe Areas"
    bl_options = {'DEFAULT_CLOSED'}
    COMPAT_ENGINES = {'BLENDER_RENDER', 'BLENDER_GAME'}

    def draw(self, context):
        layout = self.layout

        cam = context.camera

        layout.prop(cam, "show_safe_areas", text="Enabled")

        box = layout.box()
        box.label(text="Safe Areas:", icon="RESTRICT_VIEW_OFF")
        draw_display_safe_settings(box, context.scene.safe_areas, cam)


class DATA_PT_camera_game_culling(CameraButtonsPanel, Panel):
    bl_label = "Culling & LOD"
    bl_options = {'DEFAULT_CLOSED'}
    COMPAT_ENGINES = {'BLENDER_GAME'}

    def draw(self, context):
        layout = self.layout

        cam = context.camera
        scene = context.scene

        box = layout.box()
        box.label(text="Levels of Detail:", icon="MOD_SUBSURF")
        box.prop(cam, "lod_factor", text="Distance Factor")

        box = layout.box()
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

        box = layout.box()
        box.label(text="Shadow Cascade Cache:", icon="TIME")
        box.prop(cam, "csm_cache_max_stale_frames", text="Tolerance", slider=True)

        box = layout.box()
        box.label(text="Optimization Reference:", icon="CAMERA_DATA")
        if context.object == scene.camera:
            box.label(text="This active camera supplies the runtime distance reference.")
        else:
            box.label(text="The active Scene camera supplies the runtime distance reference.")
        box.label(text="Foliage and Grass use it when Foliage Optimization is enabled.")


class DATA_PT_camera_game_viewport(CameraButtonsPanel, Panel):
    bl_label = "Custom Viewport"
    bl_options = {'DEFAULT_CLOSED'}
    COMPAT_ENGINES = {'BLENDER_GAME'}

    def draw(self, context):
        layout = self.layout

        cam = context.camera
        viewport = cam.viewport

        layout.prop(cam, "use_viewport", text="Enabled")

        layout = layout.column()
        layout.active = cam.use_viewport

        box = layout.box()
        box.label(text="Presets:", icon="SCREEN_BACK")
        self.draw_presets(box.column(align=True), (
            (('FULL', "Full Screen"), ('PICTURE_IN_PICTURE', "Picture-in-Picture")),
            (('LEFT', "Left"), ('RIGHT', "Right"), ('TOP', "Top"), ('BOTTOM', "Bottom")),
            (('TOP_LEFT', "Top Left"), ('TOP_RIGHT', "Top Right")),
            (('BOTTOM_LEFT', "Bottom Left"), ('BOTTOM_RIGHT', "Bottom Right")),
        ))

        box = layout.box()
        box.label(text="Viewport Ratios:", icon="SETTINGS")
        split = box.split(factor=0.3)
        split.label(text="Horizontal:")
        row = split.row(align=True)
        row.prop(viewport, "left_ratio", text="Left")
        row.prop(viewport, "right_ratio", text="Right")

        split = box.split(factor=0.3)
        split.label(text="Vertical:")
        row = split.row(align=True)
        row.prop(viewport, "bottom_ratio", text="Bottom")
        row.prop(viewport, "top_ratio", text="Top")

        # Same check as the converter, which disables the viewport at game start.
        if viewport.left_ratio >= viewport.right_ratio or viewport.bottom_ratio >= viewport.top_ratio:
            box.label(text="Left/Bottom must be lower than Right/Top", icon='ERROR')
        else:
            # Same rounding as KX_Camera::UpdateViewport, against the game resolution.
            gs = context.scene.game_settings
            maxx = gs.resolution_x - 1
            maxy = gs.resolution_y - 1
            width = int(maxx * viewport.right_ratio) - int(maxx * viewport.left_ratio) + 1
            height = int(maxy * viewport.top_ratio) - int(maxy * viewport.bottom_ratio) + 1
            row = box.row()
            row.label(text="Result:")
            row.label(text="%d × %d px  (%d × %d)" % (width, height, gs.resolution_x, gs.resolution_y),
                      translate=False)

    @staticmethod
    def draw_presets(col, rows):
        for items in rows:
            row = col.row(align=True)
            for preset, text in items:
                row.operator("camera.game_viewport_preset", text=text).preset = preset


class DATA_PT_camera_stereoscopy(CameraButtonsPanel, Panel):
    bl_label = "Stereoscopy"
    bl_options = {'DEFAULT_CLOSED'}
    COMPAT_ENGINES = {'BLENDER_RENDER'}

    @classmethod
    def poll(cls, context):
        render = context.scene.render
        return (CameraButtonsPanel.poll.__func__(cls, context) and
                render.use_multiview and render.views_format == 'STEREO_3D')

    def draw(self, context):
        layout = self.layout

        render = context.scene.render
        cam = context.camera
        st = cam.stereo

        is_spherical_stereo = cam.type != 'ORTHO' and render.use_spherical_stereo
        use_spherical_stereo = is_spherical_stereo and st.use_spherical_stereo

        box = layout.box()
        box.label(text="Convergence:", icon="CAMERA_STEREO")
        col = box.column()
        col.row().prop(st, "convergence_mode", expand=True)

        sub = col.column()
        sub.active = st.convergence_mode != 'PARALLEL'
        sub.prop(st, "convergence_distance")

        col.prop(st, "interocular_distance")

        if is_spherical_stereo:
            box = layout.box()
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

        box = layout.box()
        box.label(text="Pivot:", icon="ROTATE")
        row = box.row()
        row.active = not use_spherical_stereo
        row.prop(st, "pivot", expand=True)


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
    DATA_PT_camera_dof,
    DATA_PT_camera_display,
    DATA_PT_camera_safe_areas,
    DATA_PT_camera_game_culling,
    DATA_PT_camera_game_viewport,
    DATA_PT_camera_stereoscopy,
    # DATA_PT_custom_props_camera,  # disabled: Custom Properties panel unused
)

if __name__ == "__main__":  # only for live edit.
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)
