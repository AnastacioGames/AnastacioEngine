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
from bpy.types import Menu, Panel
from rna_prop_ui import PropertyPanel


class LAMP_MT_sunsky_presets(Menu):
    bl_label = "Sun & Sky Presets"
    preset_subdir = "sunsky"
    preset_operator = "script.execute_preset"
    COMPAT_ENGINES = {'BLENDER_RENDER', 'BLENDER_GAME'}
    draw = Menu.draw_preset


class DataButtonsPanel:
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"

    @classmethod
    def poll(cls, context):
        engine = context.scene.render.engine
        return context.lamp and (engine in cls.COMPAT_ENGINES)


class DATA_PT_context_lamp(DataButtonsPanel, Panel):
    bl_label = ""
    bl_options = {'HIDE_HEADER'}
    COMPAT_ENGINES = {'BLENDER_RENDER', 'BLENDER_GAME'}

    def draw(self, context):
        layout = self.layout

        ob = context.object
        lamp = context.lamp
        space = context.space_data

        split = layout.split(factor=0.65)

        texture_count = len(lamp.texture_slots.keys())

        if ob:
            split.template_ID(ob, "data")
        elif lamp:
            split.template_ID(space, "pin_id")

        if texture_count != 0:
            split.label(text=str(texture_count), icon='TEXTURE')


class DATA_PT_preview(DataButtonsPanel, Panel):
    bl_label = "Preview"
    COMPAT_ENGINES = {'BLENDER_RENDER', 'BLENDER_GAME'}

    def draw(self, context):
        self.layout.template_preview(context.lamp)


class DATA_PT_lamp(DataButtonsPanel, Panel):
    bl_label = "Lamp"
    COMPAT_ENGINES = {'BLENDER_RENDER', 'BLENDER_GAME'}

    def draw(self, context):
        layout = self.layout

        lamp = context.lamp
        engine = context.scene.render.engine

        main_box = layout.box()
        main_box.label(text="Lamp:", icon="LAMP_DATA")

        # --- Type & Color ---
        box = main_box.box()
        box.label(text="Type:", icon="LAMP_DATA")
        row = box.row()
        row.prop(lamp, "type", expand=True)

        box = main_box.box()
        box.label(text="Color & Falloff:", icon="COLOR")
        split = box.split()

        col = split.column()
        sub = col.column()
        sub.prop(lamp, "color", text="")

        if lamp.type == 'HEMI':
            sub.prop(lamp, "second_color", text="")

        sub.prop(lamp, "energy")

        if lamp.type in {'POINT', 'SPOT'}:
            sub.label(text="Falloff:")
            sub.prop(lamp, "falloff_type", text="")
            sub.prop(lamp, "distance")

            if lamp.falloff_type == 'LINEAR_QUADRATIC_WEIGHTED':
                col.label(text="Attenuation Factors:")
                sub = col.column(align=True)
                sub.prop(lamp, "linear_attenuation", slider=True, text="Linear")
                sub.prop(lamp, "quadratic_attenuation", slider=True, text="Quadratic")

            elif lamp.falloff_type == 'INVERSE_COEFFICIENTS':
                col.label(text="Inverse Coefficients:")
                sub = col.column(align=True)
                sub.prop(lamp, "constant_coefficient", text="Constant")
                sub.prop(lamp, "linear_coefficient", text="Linear")
                sub.prop(lamp, "quadratic_coefficient", text="Quadratic")

            elif lamp.falloff_type == 'INVSQUARE_CUTOFF':
                col.label(text="Inverse Square Cutoff:")
                sub = col.column(align=True)
                sub.prop(lamp, "radius", text="Radius")
                sub.prop(lamp, "cutoff_threshold", text="CutOff")

            col.prop(lamp, "use_sphere")

        if lamp.type == 'AREA':
            col.prop(lamp, "distance")
            col.prop(lamp, "gamma")

        if lamp.type == 'HEMI':
            col.prop(lamp, "use_sphere")
            col.prop(lamp, "distance")
            col.prop(lamp, "hemi_cutoff", text="Attenuation")

        col = split.column()
        col.prop(lamp, "use_negative")
        col.prop(lamp, "use_own_layer", text="This Layer Only")
        col.prop(lamp, "use_specular")
        col.prop(lamp, "use_diffuse")

        # --- Sky & Atmosphere (Sun, render only) ---
        if engine == 'BLENDER_RENDER' and lamp.type == 'SUN':
            row = main_box.row(align=True)
            row.prop(lamp, "show_expanded_lamp_sunsky", text="Sky & Atmosphere",
                     icon='TRIA_DOWN' if lamp.show_expanded_lamp_sunsky else 'TRIA_RIGHT', emboss=True)
            if lamp.show_expanded_lamp_sunsky:
                sky = lamp.sky

                box = main_box.box()
                box.label(text="Sky:", icon="WORLD")
                row = box.row(align=True)
                row.prop(sky, "use_sky")
                row.menu("LAMP_MT_sunsky_presets", text=bpy.types.LAMP_MT_sunsky_presets.bl_label)
                row.operator("lamp.sunsky_preset_add", text="", icon='ZOOMIN')
                row.operator("lamp.sunsky_preset_add", text="", icon='ZOOMOUT').remove_active = True

                row = box.row()
                row.active = sky.use_sky or sky.use_atmosphere
                row.prop(sky, "atmosphere_turbidity", text="Turbidity")

                split = box.split()

                col = split.column()
                col.active = sky.use_sky
                col.label(text="Blending:")
                sub = col.column()
                sub.prop(sky, "sky_blend_type", text="")
                sub.prop(sky, "sky_blend", text="Factor")

                col.label(text="Color Space:")
                sub = col.column()
                sub.row().prop(sky, "sky_color_space", expand=True)
                sub.prop(sky, "sky_exposure", text="Exposure")

                col = split.column()
                col.active = sky.use_sky
                col.label(text="Horizon:")
                sub = col.column()
                sub.prop(sky, "horizon_brightness", text="Brightness")
                sub.prop(sky, "spread", text="Spread")

                col.label(text="Sun:")
                sub = col.column()
                sub.prop(sky, "sun_brightness", text="Brightness")
                sub.prop(sky, "sun_size", text="Size")
                sub.prop(sky, "backscattered_light", slider=True, text="Back Light")

                box2 = main_box.box()
                box2.label(text="Atmosphere:", icon="MOD_FLUIDSIM")
                box2.prop(sky, "use_atmosphere")

                split = box2.split()

                col = split.column()
                col.active = sky.use_atmosphere
                col.label(text="Intensity:")
                col.prop(sky, "sun_intensity", text="Sun")
                col.prop(sky, "atmosphere_distance_factor", text="Distance")

                col = split.column()
                col.active = sky.use_atmosphere
                col.label(text="Scattering:")
                sub = col.column(align=True)
                sub.prop(sky, "atmosphere_inscattering", slider=True, text="Inscattering")
                sub.prop(sky, "atmosphere_extinction", slider=True, text="Extinction")

        # --- Shadow (render only) ---
        if engine == 'BLENDER_RENDER' and lamp.type in {'POINT', 'SUN', 'SPOT', 'AREA'}:
            row = main_box.row(align=True)
            row.prop(lamp, "show_expanded_lamp_shadow", text="Shadow",
                     icon='TRIA_DOWN' if lamp.show_expanded_lamp_shadow else 'TRIA_RIGHT', emboss=True)
            if lamp.show_expanded_lamp_shadow:
                box = main_box.box()
                box.label(text="Shadow:", icon="MATCUBE")
                box.row().prop(lamp, "shadow_method", expand=True)

                if lamp.shadow_method == 'NOSHADOW' and lamp.type == 'AREA':
                    split = box.split()

                    col = split.column()
                    col.label(text="Form Factor Sampling:")

                    sub = col.row(align=True)

                    if lamp.shape == 'SQUARE':
                        sub.prop(lamp, "shadow_ray_samples_x", text="Samples")
                    elif lamp.shape == 'RECTANGLE':
                        sub.prop(lamp, "shadow_ray_samples_x", text="Samples X")
                        sub.prop(lamp, "shadow_ray_samples_y", text="Samples Y")

                if lamp.shadow_method != 'NOSHADOW':
                    split = box.split()

                    col = split.column()
                    col.prop(lamp, "shadow_color", text="")

                    col = split.column()
                    col.prop(lamp, "use_shadow_layer", text="This Layer Only")
                    col.prop(lamp, "use_only_shadow")

                if lamp.shadow_method == 'RAY_SHADOW':
                    split = box.split()

                    col = split.column()
                    col.label(text="Sampling:")

                    if lamp.type in {'POINT', 'SUN', 'SPOT'}:
                        sub = col.row()

                        sub.prop(lamp, "shadow_ray_samples", text="Samples")
                        sub.prop(lamp, "shadow_soft_size", text="Soft Size")

                    elif lamp.type == 'AREA':
                        sub = col.row(align=True)

                        if lamp.shape == 'SQUARE':
                            sub.prop(lamp, "shadow_ray_samples_x", text="Samples")
                        elif lamp.shape == 'RECTANGLE':
                            sub.prop(lamp, "shadow_ray_samples_x", text="Samples X")
                            sub.prop(lamp, "shadow_ray_samples_y", text="Samples Y")

                    col.row().prop(lamp, "shadow_ray_sample_method", expand=True)

                    if lamp.shadow_ray_sample_method == 'ADAPTIVE_QMC':
                        box.prop(lamp, "shadow_adaptive_threshold", text="Threshold")

                    if lamp.type == 'AREA' and lamp.shadow_ray_sample_method == 'CONSTANT_JITTERED':
                        row = box.row()
                        row.prop(lamp, "use_umbra")
                        row.prop(lamp, "use_dither")
                        row.prop(lamp, "use_jitter")

                elif lamp.shadow_method == 'BUFFER_SHADOW':
                    col = box.column()
                    col.label(text="Buffer Type:")
                    col.row().prop(lamp, "shadow_buffer_type", expand=True)

                    if lamp.shadow_buffer_type in {'REGULAR', 'HALFWAY', 'DEEP'}:
                        split = box.split()

                        col = split.column()
                        col.label(text="Filter Type:")
                        col.prop(lamp, "shadow_filter_type", text="")
                        sub = col.column(align=True)
                        sub.prop(lamp, "shadow_buffer_soft", text="Soft")
                        sub.prop(lamp, "shadow_buffer_bias", text="Bias")

                        col = split.column()
                        col.label(text="Sample Buffers:")
                        col.prop(lamp, "shadow_sample_buffers", text="")
                        sub = col.column(align=True)
                        sub.prop(lamp, "shadow_buffer_size", text="Size")
                        sub.prop(lamp, "shadow_buffer_samples", text="Samples")
                        if lamp.shadow_buffer_type == 'DEEP':
                            col.prop(lamp, "compression_threshold")

                    elif lamp.shadow_buffer_type == 'IRREGULAR':
                        box.prop(lamp, "shadow_buffer_bias", text="Bias")

                    split = box.split()

                    col = split.column()
                    col.prop(lamp, "use_auto_clip_start", text="Autoclip Start")
                    sub = col.column()
                    sub.active = not lamp.use_auto_clip_start
                    sub.prop(lamp, "shadow_buffer_clip_start", text="Clip Start")

                    col = split.column()
                    col.prop(lamp, "use_auto_clip_end", text="Autoclip End")
                    sub = col.column()
                    sub.active = not lamp.use_auto_clip_end
                    sub.prop(lamp, "shadow_buffer_clip_end", text=" Clip End")

        # --- Area Shape ---
        if lamp.type == 'AREA':
            row = main_box.row(align=True)
            row.prop(lamp, "show_expanded_lamp_area", text="Area Shape",
                     icon='TRIA_DOWN' if lamp.show_expanded_lamp_area else 'TRIA_RIGHT', emboss=True)
            if lamp.show_expanded_lamp_area:
                box = main_box.box()
                box.label(text="Area Shape:", icon="MESH_PLANE")
                col = box.column()
                col.row().prop(lamp, "shape", expand=True)
                sub = col.row(align=True)

                if lamp.shape == 'SQUARE':
                    sub.prop(lamp, "size")
                elif lamp.shape == 'RECTANGLE':
                    sub.prop(lamp, "size", text="Size X")
                    sub.prop(lamp, "size_y", text="Size Y")

        # --- Spot Shape ---
        if lamp.type == 'SPOT':
            row = main_box.row(align=True)
            row.prop(lamp, "show_expanded_lamp_spot", text="Spot Shape",
                     icon='TRIA_DOWN' if lamp.show_expanded_lamp_spot else 'TRIA_RIGHT', emboss=True)
            if lamp.show_expanded_lamp_spot:
                box = main_box.box()
                box.label(text="Spot Shape:", icon="LAMP_SPOT")
                split = box.split()

                col = split.column()
                sub = col.column()
                sub.prop(lamp, "spot_size", text="Size")
                sub.prop(lamp, "spot_blend", text="Blend", slider=True)
                col.prop(lamp, "use_square")
                col.prop(lamp, "show_cone")

                col = split.column()

                col.active = (lamp.shadow_method != 'BUFFER_SHADOW' or lamp.shadow_buffer_type != 'DEEP')
                col.prop(lamp, "use_halo")
                sub = col.column(align=True)
                sub.active = lamp.use_halo
                sub.prop(lamp, "halo_intensity", text="Intensity")
                if lamp.shadow_method == 'BUFFER_SHADOW':
                    sub.prop(lamp, "halo_step", text="Step")

        # --- Falloff Curve ---
        if lamp.type in {'POINT', 'SPOT'} and lamp.falloff_type == 'CUSTOM_CURVE':
            row = main_box.row(align=True)
            row.prop(lamp, "show_expanded_lamp_falloff_curve", text="Falloff Curve",
                     icon='TRIA_DOWN' if lamp.show_expanded_lamp_falloff_curve else 'TRIA_RIGHT', emboss=True)
            if lamp.show_expanded_lamp_falloff_curve:
                box = main_box.box()
                box.label(text="Falloff Curve:", icon="SMOOTHCURVE")
                box.template_curve_mapping(lamp, "falloff_curve", use_negative_slope=True)


bpy.types.Lamp.show_expanded_lamp_sunsky = bpy.props.BoolProperty(name="Expanded", default=False)
bpy.types.Lamp.show_expanded_lamp_shadow = bpy.props.BoolProperty(name="Expanded", default=False)
bpy.types.Lamp.show_expanded_lamp_area = bpy.props.BoolProperty(name="Expanded", default=False)
bpy.types.Lamp.show_expanded_lamp_spot = bpy.props.BoolProperty(name="Expanded", default=False)
bpy.types.Lamp.show_expanded_lamp_falloff_curve = bpy.props.BoolProperty(name="Expanded", default=False)


class DATA_PT_custom_props_lamp(DataButtonsPanel, PropertyPanel, Panel):
    COMPAT_ENGINES = {'BLENDER_RENDER', 'BLENDER_GAME'}
    _context_path = "object.data"
    _property_type = bpy.types.Lamp


classes = (
    LAMP_MT_sunsky_presets,
    DATA_PT_context_lamp,
    DATA_PT_preview,
    DATA_PT_lamp,
    # DATA_PT_custom_props_lamp,  # disabled: Custom Properties panel unused
)

if __name__ == "__main__":  # only for live edit.
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)
