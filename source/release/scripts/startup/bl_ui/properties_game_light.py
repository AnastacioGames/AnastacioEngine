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
import os
import math
from array import array
from bpy.types import Panel, Menu, UIList, Operator, AnimationEventTrigger
from bpy.props import IntProperty, StringProperty, EnumProperty
from mathutils import Vector
from bpy.app.translations import pgettext_iface as iface_

# Game: Light data tab (shadows, CSM, light culling).
# Split out of properties_game.py, which still registers every class in order.

class DataButtonsPanel:
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"


class DATA_PT_shadow_game(DataButtonsPanel, Panel):
    bl_label = "Use Shadow"
    COMPAT_ENGINES = {'BLENDER_GAME'}

    @classmethod
    def poll(cls, context):
        COMPAT_LIGHTS = {'SPOT', 'SUN', 'POINT'}
        lamp = context.lamp
        engine = context.scene.render.engine
        return (lamp and lamp.type in COMPAT_LIGHTS) and (engine in cls.COMPAT_ENGINES)

    def draw_header(self, context):
        lamp = context.lamp

        self.layout.prop(lamp, "use_shadow", text="")

    def draw(self, context):
        layout = self.layout

        lamp = context.lamp

        # A Point has no single shadow direction, so the engine re-renders the casters once per
        # cube face: 6 passes per frame against 1 for Spot/Sun. Warn before the panel is greyed
        # out by layout.active, so it stays readable with the shadow off.
        if lamp.type == 'POINT':
            layout.label("Point shadow costs 6 render passes per frame", icon='ERROR')

        layout.active = lamp.use_shadow

        # A Point renders its shadow as a 6-face cube atlas: no shadow box, no static cache
        # and no VSM/CSM/filter variants (see gpu_lamp_create_point_shadow_buffer).
        is_point = lamp.type == 'POINT'
        is_sun = lamp.type == 'SUN'

        main_box = layout.box()

        # --- General ---
        row = main_box.row()
        row.label("Color:")
        row.prop(lamp, "shadow_color", text="")

        split = main_box.split()
        col = split.column()
        # Point draws its shadow range as a sphere instead of a box
        # (draw_transp_point_shadow_volume).
        col.prop(lamp, "show_shadow_box", text="Show Shadow Sphere" if is_point else "Show Shadow Box")
        if not is_point:
            col.prop(lamp, "static_shadow")
        if lamp.type in {'SPOT', 'POINT'}:
            col.prop(lamp, "use_auto_shadow_update", text="Auto Update")

        col = split.column()
        col.prop(lamp, "use_shadow_layer", text="This Layer Only")
        col.prop(lamp, "use_only_shadow")

        if is_sun:
            main_box.prop(lamp, "shadow_blend", text="Shadow Fade", slider=True)

        # --- Range ---
        col = main_box.column(align=True)
        row = col.row(align=True)
        row.prop(lamp, "shadow_buffer_clip_start", text="Clip Start")
        row.prop(lamp, "shadow_buffer_clip_end", text="Clip End")
        if is_sun:
            col.prop(lamp, "shadow_frustum_size", text="Frustum Size")

        # --- Sections: expand arrow inside the shadow box ---
        box = main_box.box()
        if _shadow_section_header(box, lamp, "show_expanded_lamp_shadow_buffer",
                                  "Buffer & Quality"):
            _draw_shadow_buffer(box.column(), lamp)


class DATA_PT_shadow_csm_game(DataButtonsPanel, Panel):
    bl_label = "Cascaded Shadow Mapping"
    COMPAT_ENGINES = {'BLENDER_GAME'}

    @classmethod
    def poll(cls, context):
        lamp = context.lamp
        return (lamp and lamp.type == 'SUN') and (context.scene.render.engine in cls.COMPAT_ENGINES)

    def draw_header(self, context):
        self.layout.prop(context.lamp, "use_csm_shadow", text="")

    def draw(self, context):
        lamp = context.lamp
        layout = self.layout
        layout.active = lamp.use_shadow
        _draw_shadow_csm(layout.box(), lamp)


def _shadow_section_header(box, lamp, open_prop, title):
    """Header row of a Use Shadow section; returns whether it is open."""
    is_open = getattr(lamp, open_prop)
    row = box.row(align=True)
    row.prop(lamp, open_prop, text="", emboss=False,
             icon='TRIA_DOWN' if is_open else 'TRIA_RIGHT')
    row.label(text=title)
    return is_open


def _shadow_flags(lamp):
    """Shared state of the Use Shadow panel sections."""
    is_point = lamp.type == 'POINT'
    is_simple = is_point or lamp.ge_shadow_buffer_type == "SIMPLE"
    use_csm = lamp.type == 'SUN' and lamp.use_csm_shadow
    # Auto Bias: CSM only; works for both Simple (depth+slope) and Variance (variance floor).
    auto_bias = use_csm and lamp.use_csm_auto_bias
    return is_point, is_simple, use_csm, auto_bias


def _draw_shadow_buffer(layout, lamp):
    is_point, is_simple, use_csm, auto_bias = _shadow_flags(lamp)

    if not is_point:
        split = layout.split(factor=0.3)
        split.label("Type:")
        split.row().prop(lamp, "ge_shadow_buffer_type", expand=True)
        if is_simple:
            # Quick choice for beginners; the full list stays below it.
            split = layout.split(factor=0.3)
            split.label("Look:")
            row = split.row(align=True)
            row.prop_enum(lamp, "shadow_filter", "NONE", text="Hard")
            row.prop_enum(lamp, "shadow_filter", "PCF", text="Soft")
            row.prop_enum(lamp, "shadow_filter", "PCF_PENUMBRA", text="Realistic")
            split = layout.split(factor=0.3)
            split.label("Filter:")
            split.prop(lamp, "shadow_filter", text="")
            if lamp.shadow_filter == "PCF_PENUMBRA":
                layout.label("Realistic turns Hard on Low/Very Low quality", icon='INFO')

    pcf = lamp.shadow_filter in ("PCF", "PCF_BAIL", "PCF_JITTER", "PCF_PENUMBRA")
    if use_csm:
        # Cascades read one tap per pixel (except PCSS); per-cascade sizes live in the cascade table.
        if is_simple and lamp.shadow_filter == "PCF_PENUMBRA":
            col = layout.column(align=True)
            col.prop(lamp, "shadow_buffer_samples", text="Samples")
            col.prop(lamp, "shadow_buffer_soft", text="Soft")
        elif is_simple and pcf:
            layout.label("PCF filters are not used with cascades", icon='INFO')
    else:
        col = layout.column(align=True)
        col.prop(lamp, "shadow_buffer_size", text="Size")
        if is_point:
            # The atlas is Size*3 x Size*2 texels, so the engine caps Size at 2048.
            col.label("Size above 2048 is clamped (cube atlas)", icon='INFO')
        elif not is_simple:
            col.prop(lamp, "shadow_buffer_sharp", text="Sharpness")
        elif pcf:
            col.prop(lamp, "shadow_buffer_samples", text="Samples")
            col.prop(lamp, "shadow_buffer_soft", text="Soft")

    layout.separator()
    row = layout.row()
    row.label("Bias:")
    if use_csm:
        row.prop(lamp, "use_csm_auto_bias", text="Auto")
    row = layout.row(align=True)
    if auto_bias:
        row.prop(lamp, "shadow_buffer_bias", text="Strength")
        layout.label("Follows each cascade's texel size", icon='INFO')
        if not is_simple:
            row = layout.row(align=True)
            row.prop(lamp, "shadow_buffer_bleed_bias", text="Bleed Bias")
    elif use_csm:
        # Per-cascade Bias is in the cascade table; Slope/Bleed bias is lamp-wide.
        if is_simple:
            row.prop(lamp, "shadow_buffer_slope_bias", text="Slope Bias")
        else:
            row.prop(lamp, "shadow_buffer_bleed_bias", text="Bleed Bias")
    else:
        row.prop(lamp, "shadow_buffer_bias", text="Bias")
        if not is_simple:
            row.prop(lamp, "shadow_buffer_bleed_bias", text="Bleed Bias")
        else:
            row.prop(lamp, "shadow_buffer_slope_bias", text="Slope Bias")


def _draw_shadow_csm(layout, lamp):
    layout.active = lamp.use_csm_shadow
    is_point, is_simple, use_csm, auto_bias = _shadow_flags(lamp)
    two_cascades = lamp.csm_cascade_count == 2

    split = layout.split(factor=0.3)
    split.label("Reference:")
    split.row().prop(lamp, "csm_reference", expand=True)
    split = layout.split(factor=0.3)
    split.label("Cascades:")
    split.prop(lamp, "csm_cascade_count", text="")

    light_ref = lamp.csm_reference == 'LIGHT'
    col = layout.column(align=True)
    col.prop(lamp, "cascaded_proportion_two",
             text="Near Size" if light_ref else "Near Range", slider=True)
    if not two_cascades:
        col.prop(lamp, "cascaded_proportion_three",
                 text="Medium Expansion" if light_ref else "Medium Range", slider=True)
    last = "Medium" if two_cascades else "Low"
    layout.label(("%s reaches Frustum Size" if light_ref else "%s reaches Clip End") % last,
                 icon='INFO')

    # One row per cascade: buffer size, plus its bias when Auto Bias is off.
    rows = [("Near", "shadow_buffer_size", "shadow_buffer_bias"),
            ("Medium", "shadow_csm_two_buffer_size", "shadow_buffer_bias_two")]
    if not two_cascades:
        rows.append(("Low", "shadow_csm_three_buffer_size", "shadow_buffer_bias_three"))
    show_bias = not auto_bias
    col = layout.column(align=True)
    split = col.split(factor=0.3)
    split.label("")
    sub = split.row(align=True)
    sub.label("Size")
    if show_bias:
        sub.label("Bias")
    for name, size_prop, bias_prop in rows:
        split = col.split(factor=0.3)
        split.label(name)
        sub = split.row(align=True)
        sub.prop(lamp, size_prop, text="")
        if show_bias:
            sub.prop(lamp, bias_prop, text="")

    layout.prop(lamp, "use_csm_debug", text="Show Cascades (Debug)")



bpy.types.Lamp.show_expanded_lamp_shadow_buffer = bpy.props.BoolProperty(name="Expanded", default=False)


class DATA_PT_light_culling_game(DataButtonsPanel, Panel):
    bl_label = "Distance Culling"
    COMPAT_ENGINES = {'BLENDER_GAME'}

    @classmethod
    def poll(cls, context):
        lamp = context.lamp
        engine = context.scene.render.engine
        return (lamp and lamp.type != 'SUN') and (engine in cls.COMPAT_ENGINES)

    def draw_header(self, context):
        lamp = context.lamp

        self.layout.prop(lamp, "use_cull_distance", text="")

    def draw(self, context):
        layout = self.layout
        lamp = context.lamp

        layout.active = lamp.use_cull_distance

        row = layout.row()
        row.prop(lamp, "cull_distance", text="Cull Distance")

        row = layout.row()
        row.prop(lamp, "glow_scale", text="Glow Scale")
