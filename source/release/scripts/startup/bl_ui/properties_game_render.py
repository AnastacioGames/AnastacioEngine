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

# Game: Render tab (resolution, cooking, shading, SSGI, baked lighting, post-process, system).
# Split out of properties_game.py, which still registers every class in order.

class RenderButtonsPanel:
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "render"

    @classmethod
    def poll(cls, context):
        rd = context.scene.render
        category = getattr(cls, "ae_category", None)
        return (rd.engine in cls.COMPAT_ENGINES and
                (rd.engine != 'BLENDER_GAME' or category is None or
                 context.window_manager.ae_render_panel_category == category))


class RENDER_OT_set_game_resolution(Operator):
    bl_idname = "render.set_game_resolution"
    bl_label = "Set Resolution"
    bl_options = {'REGISTER', 'UNDO'}

    x: IntProperty()
    y: IntProperty()
    target: StringProperty()

    def execute(self, context):
        if self.target == 'EMBEDDED':
            context.scene.render.resolution_x = self.x
            context.scene.render.resolution_y = self.y
        elif self.target == 'PLAYER':
            context.scene.game_settings.resolution_x = self.x
            context.scene.game_settings.resolution_y = self.y
        return {'FINISHED'}


class RENDER_OT_game_vr_setup(Operator):
    """Set the scene up for mobile VR (Cardboard): side-by-side stereo, """ \
        """head tracking and lens distortion"""
    bl_idname = "render.game_vr_setup"
    bl_label = "Prepare VR Scene"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        gs = context.scene.game_settings
        gs.stereo = 'STEREO'
        gs.stereo_mode = 'SIDEBYSIDE'
        gs.stereo_eye_separation = 0.064
        gs.vr_head_tracking = True
        gs.vr_lens_distortion = True
        gs.vr_lens_strength = 30
        gs.vr_head_smoothing = 40
        gs.vr_vignette = 50
        gs.vr_recenter_time = 2000
        return {'FINISHED'}


class RENDER_MT_game_res_embedded(Menu):
    bl_label = "Resolution Presets"
    bl_idname = "RENDER_MT_game_res_embedded"

    def draw(self, context):
        layout = self.layout
        resolutions = [
            ("VGA", 800, 600), ("HD", 1280, 720), ("WXGA", 1366, 768),
            ("HD+", 1600, 900), ("FHD", 1920, 1080), ("QHD", 2560, 1440), ("4K UHD", 3840, 2160)
        ]
        for name, x, y in resolutions:
            op = layout.operator("render.set_game_resolution", text="{} ({}x{})".format(name, x, y))
            op.x = x; op.y = y; op.target = 'EMBEDDED'

        layout.separator()
        layout.label(text="Custom Resolution:")
        col = layout.column(align=True)
        col.prop(context.scene.render, "resolution_x", text="X")
        col.prop(context.scene.render, "resolution_y", text="Y")


class RENDER_MT_game_res_player(Menu):
    bl_label = "Resolution Presets"
    bl_idname = "RENDER_MT_game_res_player"

    def draw(self, context):
        layout = self.layout
        resolutions = [
            ("VGA", 800, 600), ("HD", 1280, 720), ("WXGA", 1366, 768),
            ("HD+", 1600, 900), ("FHD", 1920, 1080), ("QHD", 2560, 1440), ("4K UHD", 3840, 2160)
        ]
        for name, x, y in resolutions:
            op = layout.operator("render.set_game_resolution", text="{} ({}x{})".format(name, x, y))
            op.x = x; op.y = y; op.target = 'PLAYER'

        layout.separator()
        layout.label(text="Custom Resolution:")
        col = layout.column(align=True)
        col.prop(context.scene.game_settings, "resolution_x", text="X")
        col.prop(context.scene.game_settings, "resolution_y", text="Y")


class RENDER_MT_game_target_fps(Menu):
    bl_label = "Target FPS Presets"
    bl_idname = "RENDER_MT_game_target_fps"

    def draw(self, context):
        layout = self.layout
        for value in (30, 60, 75, 90, 120, 144):
            op = layout.operator("wm.context_set_int", text=str(value))
            op.data_path = "scene.game_settings.dynamic_resolution_target_fps"
            op.value = value
        layout.separator()
        layout.label(text="Custom Target FPS:")
        layout.prop(context.scene.game_settings, "dynamic_resolution_target_fps", text="Value")


class RENDER_MT_game_animation_fps(Menu):
    bl_label = "Animation Frame Rate Presets"
    bl_idname = "RENDER_MT_game_animation_fps"

    def draw(self, context):
        layout = self.layout
        for value in (24, 25, 30, 60, 120):
            op = layout.operator("wm.context_set_int", text=str(value))
            op.data_path = "scene.render.fps"
            op.value = value
        layout.separator()
        layout.label(text="Custom Animation Frame Rate:")
        layout.prop(context.scene.render, "fps", text="Value")


class RENDER_MT_game_bit_depth(Menu):
    bl_label = "Bit Depth Presets"
    bl_idname = "RENDER_MT_game_bit_depth"

    def draw(self, context):
        layout = self.layout
        for value in (16, 24, 32):
            op = layout.operator("wm.context_set_int", text=str(value))
            op.data_path = "scene.game_settings.depth"
            op.value = value
        layout.separator()
        layout.label(text="Custom Bit Depth:")
        layout.prop(context.scene.game_settings, "depth", text="Value")


class RENDER_MT_game_refresh_rate(Menu):
    bl_label = "Refresh Rate Presets"
    bl_idname = "RENDER_MT_game_refresh_rate"

    def draw(self, context):
        layout = self.layout
        for value in (30, 50, 60, 75, 90, 120, 144, 240):
            op = layout.operator("wm.context_set_int", text=str(value))
            op.data_path = "scene.game_settings.frequency"
            op.value = value
        layout.separator()
        layout.label(text="Custom Refresh Rate:")
        layout.prop(context.scene.game_settings, "frequency", text="Value")


class RENDER_PT_game_cook(RenderButtonsPanel, Panel):
    # Second panel, right after the engine selector: loading speed matters for every game.
    bl_label = "Cook"
    COMPAT_ENGINES = {'BLENDER_GAME'}
    ae_category = 'SYSTEM'

    def draw(self, context):
        import os
        from bl_operators.anastacio_cook import cooked_path
        layout = self.layout

        row = layout.row(align=True)
        row.scale_y = 1.3
        row.operator("game.cook", icon='COOK')
        row.operator("game.cook_clear", text="", icon='X')

        path = cooked_path()
        if not path:
            layout.label(text="Save the .blend to cook", icon='INFO')
        elif os.path.isfile(path):
            layout.label(text="%s: %.1f MB" % (os.path.basename(path), os.path.getsize(path) / 1048576.0),
                         icon='FILE_TICK')
        else:
            layout.label(text="Not cooked: shapes and shaders are computed while loading", icon='INFO')


class RENDER_PT_embedded(RenderButtonsPanel, Panel):
    # Embedded and Standalone players side by side, one column each.
    bl_label = "Player"
    COMPAT_ENGINES = {'BLENDER_GAME'}
    ae_category = 'SYSTEM'

    def draw(self, context):
        import sys
        layout = self.layout
        not_osx = sys.platform != "darwin"

        rd = context.scene.render
        gs = context.scene.game_settings

        # Borderless hides Fullscreen and Desktop; Desktop only shows with Fullscreen.
        show_fullscreen = not gs.borderless_window
        show_desktop = not_osx and show_fullscreen and gs.show_fullscreen
        option_rows = 1 + show_fullscreen + show_desktop

        split = layout.split(factor=0.5)

        box = split.box()
        box.label(text="Embedded Player:", icon="VIEW3D")
        row = box.row(align=True)
        row.operator("view3d.game_start", text="Start")
        row.prop(gs, "use_live_ui", text="", icon='UNLOCKED' if gs.use_live_ui else 'LOCKED')
        row.prop(gs, "show_console", text="", icon='CONSOLE')
        row = box.row()
        row.label(text="Resolution:", icon="SCENE")
        row = box.row(align=True)
        row.menu("RENDER_MT_game_res_embedded", text="{} x {}".format(rd.resolution_x, rd.resolution_y))
        # Blank rows so both boxes keep the same height. They sit in a column,
        # like the checkboxes, so the row spacing matches.
        col = box.column()
        for _ in range(option_rows):
            col.label(text="")

        box = split.box()
        box.label(text="Standalone Player:", icon="WORLD")
        row = box.row(align=True)
        row.operator("wm.blenderplayer_start", text="Start")
        row.prop(gs, "show_console", text="", icon='CONSOLE')
        row = box.row()
        row.label(text="Resolution:", icon="SCENE")
        row = box.row(align=True)
        row.active = not_osx or not gs.show_fullscreen
        row.menu("RENDER_MT_game_res_player", text="{} x {}".format(gs.resolution_x, gs.resolution_y))
        col = box.column()
        if show_fullscreen:
            col.prop(gs, "show_fullscreen")
        col.prop(gs, "borderless_window")
        if show_desktop:
            col.prop(gs, "use_desktop")


class RENDER_PT_game_shading(RenderButtonsPanel, Panel):
    bl_label = "Shading"
    COMPAT_ENGINES = {'BLENDER_GAME'}
    ae_category = 'GRAPHICS'

    def draw(self, context):
        layout = self.layout

        gs = context.scene.game_settings

        box = layout.box()
        box.label(text="Shading:", icon="MATERIAL")
        split = box.split()

        col = split.column()
        col.prop(gs, "use_glsl_lights", text="Lights", icon="LAMP_SPOT")
        col.prop(gs, "use_glsl_shaders", text="Shaders", icon="LAMP_AREA")
        col.prop(gs, "use_glsl_shadows", text="Shadows", icon="SNAP_FACE")
        col.prop(gs, "use_glsl_environment_lighting", text="Environment Lighting", icon="SNAP_VOLUME")
        col = split.column()
        col.prop(gs, "use_glsl_ramps", text="Ramps", icon="IPO_BEZIER")
        col.prop(gs, "use_glsl_nodes", text="Nodes", icon="NODETREE")
        col.prop(gs, "use_glsl_extra_textures", text="Extra Textures", icon="ASSET_MANAGER")
        col.prop(gs, "use_shading_nodes", text="PBR Shading Nodes", icon="MATERIAL_NODES" if gs.use_shading_nodes else "MATERIAL_DATA")

        box = layout.box()
        box.label(text="Shader Compilation:", icon="SCRIPT")
        box.prop(gs, "use_fast_shader_loading")
        show = getattr(context.scene, "ae_fast_shader_show_help", True)
        if gs.use_fast_shader_loading and hasattr(context.scene, "ae_fast_shader_show_help"):
            box.prop(context.scene, "ae_fast_shader_show_help", text="Gain & Loss",
                     icon='TRIA_DOWN' if show else 'TRIA_RIGHT', emboss=False)
        if gs.use_fast_shader_loading and show:
            col = box.column(align=True)
            col.label(text="Gain: materials differing only in colors/values share one shader,", icon="TIME")
            col.label(text="      so the game loads much faster (800 materials: 64 s to 5 s).")
            col.label(text="Loss: every pixel computes the full material per light, so heavy", icon="ERROR")
            col.label(text="      scenes can lose up to half the FPS (18 lights: 60 to 31 fps).")
            col.label(text="Use for many materials and few lights. Game only, not the viewport.", icon="INFO")


class RENDER_PT_game_ssgi(RenderButtonsPanel, Panel):
    bl_label = "Native SSGI (Experimental)"
    COMPAT_ENGINES = {'BLENDER_GAME'}
    ae_category = 'GRAPHICS'

    @classmethod
    def poll(cls, context):
        return (super().poll(context) and hasattr(context.scene, "ae_ssgi_use"))

    def draw(self, context):
        # The operator/properties are registered from bl_operators at startup;
        # keeping this panel here makes it part of the standard Game UI.
        from bl_operators.anastacio_ssgi import QUALITY_PRESETS

        layout = self.layout
        scene = context.scene

        settings_box = layout.box()
        settings_box.prop(scene, "ae_ssgi_use", text="Use in Game")

        # Only problems that actually block the effect are shown, each with its fix.
        if scene.ae_ssgi_use:
            if not scene.game_settings.use_shading_nodes:
                row = settings_box.row()
                row.label(text="PBR Shading Nodes is off", icon='ERROR')
                row.operator("scene.anastacio_ssgi_enable_nodes", text="Enable")
            slots = list(scene.game_settings.attachment_slots)
            busy = [str(i + 1) for i, slot in enumerate(slots) if slot is not None and i >= 3]
            if busy:
                settings_box.label(text="Free attachment slot(s) %s in Attachments" % ", ".join(busy),
                                   icon='ERROR')

            settings_box.prop(scene, "ae_ssgi_approximate")
            from bl_operators import anastacio_ssgi
            row = settings_box.row()
            row.operator("scene.anastacio_ssgi_check", icon='VIEWZOOM')
            result = anastacio_ssgi.check_result
            if result is not None:
                full, partial, excluded, issues = result
                row.label(text="%d full · %d approx. · %d excluded" % (full, partial, excluded))
                col = settings_box.column(align=True)
                col.scale_y = 0.8
                for name, reason, is_excluded in issues[:12]:
                    col.label(text="%s: %s" % (name, reason), icon='ERROR' if is_excluded else 'DOT')
                if len(issues) > 12:
                    col.label(text="... %d more" % (len(issues) - 12))

        settings_box.prop(scene, "ae_ssgi_show_help", text="Limits",
                          icon='TRIA_DOWN' if scene.ae_ssgi_show_help else 'TRIA_RIGHT',
                          emboss=False)
        if scene.ae_ssgi_show_help:
            col = settings_box.column(align=True)
            col.scale_y = 0.8
            col.label(text="•  Screen-space: only what is on screen bounces light")
            col.label(text="•  Desktop only; Web/Android keep baked lighting")

        quality_box = layout.box()
        quality_box.label(text="Quality:", icon='PREFERENCES')
        quality_box.active = scene.ae_ssgi_use
        row = quality_box.row(align=True)
        for quality in ('LOW', 'MEDIUM', 'HIGH', 'ULTRA'):
            preset = QUALITY_PRESETS[quality]
            op = row.operator("scene.anastacio_ssgi_quality", text=preset['label'],
                              depress=(scene.ae_ssgi_quality == quality))
            op.quality = quality
        if scene.ae_ssgi_quality == 'CUSTOM':
            quality_box.label(text="Custom settings", icon='SETTINGS')

        advanced_box = layout.box()
        advanced_box.label(text="Advanced:", icon='SETTINGS')
        advanced_box.active = scene.ae_ssgi_use
        split = advanced_box.split()
        left = split.column(align=True)
        right = split.column(align=True)
        left.prop(scene, "ae_ssgi_radius")
        right.prop(scene, "ae_ssgi_strength")
        left.prop(scene, "ae_ssgi_rays")
        right.prop(scene, "ae_ssgi_steps")
        left.prop(scene, "ae_ssgi_divisor")
        right.prop(scene, "ae_ssgi_thickness")
        advanced_box.prop(scene, "ae_ssgi_denoise")


class RENDER_PT_game_baked_lighting(RenderButtonsPanel, Panel):
    bl_label = "Baked Lighting"
    COMPAT_ENGINES = {'BLENDER_GAME'}
    ae_category = 'GRAPHICS'

    @classmethod
    def poll(cls, context):
        return (super().poll(context) and
                hasattr(context.scene, "ae_lightmap_settings"))

    def draw(self, context):
        from bl_operators.anastacio_lightmap import (REASON_EXCLUDED, lightmap_objects,
                                                      lightmap_excluded_counts, lightmap_exclusion_reason)
        layout = self.layout
        scene = context.scene
        settings = scene.ae_lightmap_settings
        is_ao = settings.mode == 'AO'
        is_static = settings.mode == 'STATIC'

        if not scene.game_settings.use_shading_nodes:
            layout.label(text="Requires PBR shading nodes (Shading panel)", icon='INFO')

        if scene.ae_lightmap:
            current_names = {
                'INDIRECT': "Indirect + Dynamic Shadows",
                'AO': "Ambient Occlusion",
                'STATIC': "Static Lighting + Shadows",
            }
            row = layout.row()
            row.label(text=iface_("Current: %s") % iface_(current_names.get(scene.ae_lightmap_mode,
                                                                         "Indirect + Dynamic Shadows")),
                      icon='FILE_TICK')
            row.prop(scene, "ae_lightmap_use", text="Use in Game")

        layout.prop(settings, "mode", text="Mode")
        if is_static:
            layout.label(text="Sun and static shadows are baked", icon='INFO')
            layout.label(text="Moving a light or object requires a new bake")

        box = layout.box()
        box.label(text="Bake Receivers", icon='OBJECT_DATA')
        included = lightmap_objects(scene)
        excluded = lightmap_excluded_counts(scene)
        box.label(text="Next bake: %d receivers, %d excluded" %
                  (len(included), sum(excluded.values())))
        for reason, count in sorted(excluded.items()):
            box.label(text="%d: %s" % (count, iface_(reason)), icon='INFO')
        ob = context.object
        if ob and ob.type == 'MESH':
            box.prop(ob, "ae_lightmap_include", text=iface_("Bake Lighting on %s") % ob.name)
            reason = lightmap_exclusion_reason(scene, ob)
            if reason and reason != REASON_EXCLUDED:
                box.label(text=iface_("Active: %s") % iface_(reason), icon='ERROR')

        box = layout.box()
        box.label(text="Lightmap", icon="IMAGE_DATA")
        split = box.split()
        col = split.column(align=True)
        col.prop(settings, "resolution")
        col.prop(settings, "samples")
        col = split.column()
        col.prop(settings, "use_gpu")
        col.prop(settings, "use_denoise")
        if is_ao:
            box.prop(settings, "ao_distance")
            box.prop(settings, "ao_strength")
        else:
            box.prop(settings, "use_world")
        if scene.ae_lightmap:
            box.label(text="Image: " + scene.ae_lightmap, icon='FILE_IMAGE')
            if scene.ae_lightmap_atlas_coverage >= 0.0:
                box.label(text="Atlas coverage: %.1f%% of pixels baked" %
                          scene.ae_lightmap_atlas_coverage)

        if not is_ao:
            box = layout.box()
            row = box.row()
            row.label(text="Moving Objects", icon="SNAP_VOLUME")
            row.prop(settings, "use_volume", text="Bake Light Volume")
            if settings.use_volume:
                box.prop(settings, "volume_spacing")
            if scene.ae_lightvol:
                box.prop(scene, "ae_lightvol_use", text="Use in Game")

        box = layout.box()
        box.label(text="Advanced", icon='PREFERENCES')
        box.prop(settings, "margin")
        if ob and ob.type == 'MESH' and hasattr(ob, "ae_lightmap_scale"):
            box.prop(ob, "ae_lightmap_scale", text=iface_("Scale (%s)") % ob.name)

        row = layout.row()
        row.scale_y = 1.3
        row.operator("scene.ae_lightmap_bake", icon='RENDER_STILL')
        row = layout.row()
        row.enabled = bool(scene.ae_lightmap)
        row.operator("scene.ae_lightmap_clear", text="Clear Baked Lighting", icon='X')


class RENDER_PT_game_post_process_shaders(RenderButtonsPanel, Panel):
    bl_label = "Post Processing Shaders"
    COMPAT_ENGINES = {'BLENDER_GAME'}
    ae_category = 'GRAPHICS'

    def draw(self, context):
        layout = self.layout
        
        scene = context.scene
        scenefx_settings = scene.scenefx_settings

        layout = layout.box()
        layout.label(text="Post Processing Shaders:", icon="RENDER_STILL")
        layout.prop(scenefx_settings, "quality_preset")

        row = layout.row(align=True)
        row.prop(scenefx_settings, "show_expanded_ssao", text="Ambient Occlusion", emboss=True)
        row.prop(scenefx_settings, "render_editor_ssao", text="", icon="RESTRICT_RENDER_OFF", emboss=True)
        row.prop(scenefx_settings, "use_ssao", text="")
        
        if (scenefx_settings.show_expanded_ssao and scenefx_settings.ssao):
            ssao_settings = scenefx_settings.ssao
            subcol = layout.column(align=True)
            subcol.active = scenefx_settings.use_ssao
            subcol.prop(ssao_settings, "factor")
            subcol.prop(ssao_settings, "distance_max")
            subcol.prop(ssao_settings, "attenuation")
            subcol.prop(ssao_settings, "samples")

        row = layout.row(align=True)
        row.prop(scenefx_settings, "show_expanded_bloom", text="Bloom", emboss=True)
        row.prop(scenefx_settings, "render_editor_bloom", text="", icon="RESTRICT_RENDER_OFF", emboss=True)
        row.prop(scenefx_settings, "use_bloom", text="")
            
        if (scenefx_settings.show_expanded_bloom and scenefx_settings.bloom):
            bloom_settings = scenefx_settings.bloom
            subcol = layout.column(align=True)
            subcol.active = scenefx_settings.use_bloom
            subcol.prop(bloom_settings, "intensity")
            subcol.prop(bloom_settings, "threshold")
            subcol.prop(bloom_settings, "quality")
            
        row = layout.row(align=True)
        row.prop(scenefx_settings, "show_expanded_tonemap", text="Tonemap", emboss=True)
        row.prop(scenefx_settings, "render_editor_tonemap", text="", icon="RESTRICT_RENDER_OFF", emboss=True)
        row.prop(scenefx_settings, "use_tonemap", text="")
            
        if (scenefx_settings.show_expanded_tonemap and scenefx_settings.tonemap):
            tonemap_settings = scenefx_settings.tonemap
            subcol = layout.column(align=True)
            subcol.active = scenefx_settings.use_tonemap
            subcol.prop(tonemap_settings, "shadertype")
            subcol.prop(tonemap_settings, "exposure")
            subcol.prop(tonemap_settings, "gamma")
            
        row = layout.row(align=True)
        row.prop(scenefx_settings, "show_expanded_lightscatter", text="Light Scattering", emboss=True)
        row.prop(scenefx_settings, "render_editor_lightscatter", text="", icon="RESTRICT_RENDER_OFF", emboss=True)
        row.prop(scenefx_settings, "use_lightscatter", text="")
        
        if (scenefx_settings.show_expanded_lightscatter and scenefx_settings.scatter):
            scatter_settings = scenefx_settings.scatter
            subcol = layout.column(align=True)
            subcol.active = scenefx_settings.use_lightscatter
            subcol.prop(scenefx_settings, "scatter_lod", text="Lod")
            subcol.prop(scatter_settings, "intensity")
            subcol.prop(scatter_settings, "threshold")
            subcol.prop(scatter_settings, "stepsize")
            subcol.prop(scatter_settings, "stepmax")
            
        row = layout.row(align=True)
        row.prop(scenefx_settings, "show_expanded_ssr", text="Screen Space Reflections", emboss=True)
        row.prop(scenefx_settings, "render_editor_ssr", text="", icon="RESTRICT_RENDER_OFF", emboss=True)
        row.prop(scenefx_settings, "use_ssr", text="")
        
        if (scenefx_settings.show_expanded_ssr and scenefx_settings.ssr):
            ssr_settings = scenefx_settings.ssr
            subcol = layout.column(align=True)
            subcol.active = scenefx_settings.use_ssr
            subcol.prop(scenefx_settings, "ssr_lod", text="Lod")
            subcol.prop(ssr_settings, "step_max")
            subcol.prop(ssr_settings, "roughness")
            subcol.prop(ssr_settings, "bias")
            subcol.prop(ssr_settings, "max_distance")
            
        row = layout.row(align=True)
        row.prop(scenefx_settings, "show_expanded_fxaa", text="FXAA", emboss=True)
        row.prop(scenefx_settings, "render_editor_fxaa", text="", icon="RESTRICT_RENDER_OFF", emboss=True)
        row.prop(scenefx_settings, "use_fxaa", text="")

        # FXAA values live on scenefx_settings itself, so there is no settings pointer to check.
        if scenefx_settings.show_expanded_fxaa:
            subcol = layout.column(align=True)
            subcol.active = scenefx_settings.use_fxaa
            subcol.prop(scenefx_settings, "fxaa_edge_threshold")
            subcol.prop(scenefx_settings, "fxaa_edge_threshold_min")
            subcol.prop(scenefx_settings, "fxaa_subpix")
            subcol.prop(scenefx_settings, "fxaa_search_steps")

        row = layout.row(align=True)
        row.prop(scenefx_settings, "show_expanded_grain", text="Film Grain", emboss=True)
        row.prop(scenefx_settings, "render_editor_grain", text="", icon="RESTRICT_RENDER_OFF", emboss=True)
        row.prop(scenefx_settings, "use_grain", text="")

        if scenefx_settings.show_expanded_grain:
            subcol = layout.column(align=True)
            subcol.active = scenefx_settings.use_grain
            subcol.prop(scenefx_settings, "grain_strength", text="Strength")


class RENDER_PT_game_system(RenderButtonsPanel, Panel):
    bl_label = "System"
    COMPAT_ENGINES = {'BLENDER_GAME'}
    ae_category = 'SYSTEM'

    def draw(self, context):
        layout = self.layout

        gs = context.scene.game_settings

        # Outer group containing the System subpanels.
        system_group = layout.box()

        # System and Game Exit Key side by side; both have a title plus two rows.
        split = system_group.split(factor=0.5)

        box = split.box()
        box.label(text="System:", icon="SETTINGS")
        col = box.column()
        col.prop(gs, "use_frame_rate")
        col.prop(gs, "use_deprecation_warnings")

        box = split.box()
        box.label(text="Game Exit Key:", icon="QUIT")
        col = box.column()
        sub = col.column()
        sub.active = not gs.ignore_exit_key
        sub.prop(gs, "exit_key", text="", event=True)
        col.prop(gs, "ignore_exit_key")

        # Full width, the message is too long for half a column.
        if gs.ignore_exit_key:
            warn_box = system_group.box()
            warn_box.label("It will not be possible to close the game by exit key, exitGame() event only!", icon="ERROR")

        cursor_box = system_group.box()
        cursor_box.label(text="Mouse Cursor:", icon="RESTRICT_SELECT_OFF")
        cursor_box.prop(gs, "show_mouse", text="Mouse Cursor")

        expanded = context.scene.show_expanded_game_cursor
        row = cursor_box.row(align=True)
        row.prop(context.scene, "show_expanded_game_cursor", text="Custom Mouse Cursor",
                 icon='TRIA_DOWN' if expanded else 'TRIA_RIGHT', emboss=True)

        if expanded:
            col = cursor_box.column()
            col.active = gs.show_mouse
            row = col.row()
            row.prop(gs, "cursor_filepath", text="")
            row.prop(gs, "cursor_mipmap")

            row = col.row()
            for prop, label in (("cursor_offset_x", "Cursor Offset X:"),
                                ("cursor_offset_y", "Cursor Offset Y:"),
                                ("cursor_size", "Cursor Size:")):
                sub = row.column(align=True)
                sub.label(text=label)
                sub.prop(gs, prop, text="")


class RENDER_UL_attachments(UIList):
    # The 7 slots are fixed; an empty slot has no item, so it is drawn as a dimmed placeholder.
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if item is not None:
            row = layout.row()
            row.label(text=iface_("Slot %d") % index, translate=False, icon="TEXTURE")
            row.prop(item, "name", text="", emboss=False)
            row.label(text=item.bl_rna.properties["type"].enum_items[item.type].name)
        else:
            row = layout.row()
            row.enabled = False
            row.label(text=iface_("Slot %d") % index, translate=False, icon="DOT")
            row.label(text="Empty")


class RENDER_PT_game_attachments(RenderButtonsPanel, Panel):
    # Extra color outputs written by materials, read back by 2D filters as bgl_DataTextures[n].
    bl_label = "Attachments"
    COMPAT_ENGINES = {'BLENDER_GAME'}
    ae_category = 'GRAPHICS'

    def draw(self, context):
        layout = self.layout

        scene = context.scene
        gs = scene.game_settings
        slots = list(gs.attachment_slots)

        box = layout.box()
        box.label(text="Render Attachments:", icon="TEXTURE")
        box.label(text="Extra outputs read by 2D filters as bgl_DataTextures[n]", icon="INFO")

        row = box.row()
        row.template_list("RENDER_UL_attachments", "", gs, "attachment_slots", gs, "active_attachment_index", rows=3)
        col = row.column(align=True)
        col.operator("scene.render_attachment_new", icon='ZOOMIN', text="")
        col.operator("scene.render_attachment_remove", icon='ZOOMOUT', text="")

        index = gs.active_attachment_index
        attachment = gs.active_attachment

        if attachment is None:
            box.label(text=iface_("Slot %d is empty, press + to create an attachment") % index, translate=False)
            return

        # The engine skips empty slots when it builds the framebuffer, so the data texture
        # index is the count of used slots before this one.
        data_index = sum(1 for a in slots[:index] if a is not None)

        sub = box.box()
        sub.prop(attachment, "name")
        split = sub.split(factor=0.5)
        col = split.column()
        col.label(text="Type:")
        col.prop(attachment, "type", text="")
        col = split.column()
        col.label(text="Precision:")
        col.row().prop(attachment, "hdr", expand=True)
        if attachment.type == "CUSTOM":
            sub.prop(attachment, "size", text="Channels")
        sub.label(text=iface_("2D filter access: bgl_DataTextures[%d]") % data_index, translate=False)

        if data_index != index:
            warn = box.box()
            warn.label(text="Empty slots before this one, material outputs will not match.", icon="ERROR")
            warn.label(text="Fill the slots in order, starting at Slot 0.")

        if index == 0 and scene.scenefx_settings.use_ssr:
            box.label(text="SSR uses Slot 0 as G-Buffer (Gbuff0, Half)", icon="LOCKED")


class RENDER_PT_game_animations(RenderButtonsPanel, Panel):
    bl_label = "Animations"
    COMPAT_ENGINES = {'BLENDER_GAME'}
    ae_category = 'SYSTEM'

    def draw(self, context):
        layout = self.layout

        scene = context.scene
        gs = scene.game_settings

        box = layout.box()
        box.label(text="Animations:", icon="ACTION")

        split = box.split(factor=0.5)
        col = split.column()
        col.label(text="Animation Frame Rate:")
        col.menu("RENDER_MT_game_animation_fps", text="%g fps" % (scene.render.fps / scene.render.fps_base))
        col = split.column()
        col.label(text="Logic Rate:")
        col.prop(gs, "fps", text="Ticks")

        col = box.column()
        col.prop(gs, "use_restrict_animation_updates")
        if gs.use_restrict_animation_updates:
            col.label(text="Actions update at the animation rate only (faster, less smooth)", icon="INFO")
        else:
            col.label(text="Actions update every frame (smoother playback)", icon="INFO")


class RENDER_PT_game_display(RenderButtonsPanel, Panel):
    # Dynamic Resolution and Display side by side, one column each.
    # Field names sit on their own label above the field, so fields show only the value.
    bl_label = "Display"
    COMPAT_ENGINES = {"BLENDER_GAME"}
    ae_category = 'SYSTEM'

    def draw(self, context):
        layout = self.layout

        gs = context.scene.game_settings

        display_group = layout.box()
        split = display_group.split(factor=0.5)

        # Both columns have a title plus ten rows, so the boxes keep the same height.
        box = split.box()
        box.label(text="Dynamic Resolution:", icon="SCENE")
        col = box.column(align=True)
        col.label(text="Scales the render to hold the FPS.")
        col.prop(gs, "use_dynamic_resolution", text="Enable")
        settings = col.column(align=True)
        settings.active = gs.use_dynamic_resolution
        settings.label(text="Target FPS:")
        settings.menu("RENDER_MT_game_target_fps", text=str(gs.dynamic_resolution_target_fps))
        settings.label(text="Minimum Scale:")
        settings.prop(gs, "dynamic_resolution_min_scale", text="")
        settings.label(text="Maximum Scale:")
        settings.prop(gs, "dynamic_resolution_max_scale", text="")
        settings.label(text="Scale Step:")
        settings.prop(gs, "dynamic_resolution_step", text="")

        box = split.box()
        box.label(text="Display:", icon="RENDER_STILL")
        col = box.column(align=True)
        col.label(text="Vsync:")
        col.prop(gs, "vsync", text="", icon="RENDER_STILL")
        col.label(text="AA Samples:")
        col.prop(gs, "samples", text="", icon="RENDER_STILL")
        col.label(text="HDR:")
        col.prop(gs, "hdr", text="", icon="RENDER_STILL")
        col.label(text="Bit Depth (bits per pixel):")
        col.menu("RENDER_MT_game_bit_depth", text=str(gs.depth))
        col.label(text="Fullscreen Refresh Rate (Hz):")
        col.menu("RENDER_MT_game_refresh_rate", text=str(gs.frequency))

        # How the image fits the window when the aspect ratio differs.
        framing_box = display_group.box()
        framing_box.label(text="Framing:", icon="IMAGE_COL")
        col = framing_box.column()
        col.row().prop(gs, "frame_type", expand=True)
        col.prop(gs, "frame_color", text="")

        stereo_box = display_group.box()
        stereo_box.label(text="Stereo:", icon="CAMERA_STEREO")
        stereo_box.row().prop(gs, "stereo", expand=True)
        if gs.stereo == 'STEREO':
            stereo_box.prop(gs, "stereo_mode")


class RENDER_PT_game_vr(RenderButtonsPanel, Panel):
    # Mobile VR settings in one place: the setup button first, then the
    # head tracking, lens and comfort fields (used with Stereo = Stereo).
    bl_label = "VR"
    COMPAT_ENGINES = {"BLENDER_GAME"}
    ae_category = 'SYSTEM'

    def draw(self, context):
        layout = self.layout

        gs = context.scene.game_settings

        layout.operator("render.game_vr_setup", icon="CAMERA_STEREO")

        vr_box = layout.box()
        vr_box.active = (gs.stereo == 'STEREO')
        col = vr_box.column()
        col.prop(gs, "stereo_eye_separation")
        col.prop(gs, "vr_head_tracking")
        col.prop(gs, "vr_lens_distortion")
        if gs.vr_lens_distortion:
            col.prop(gs, "vr_lens_strength")
        if gs.vr_head_tracking:
            col.prop(gs, "vr_head_smoothing")
            col.prop(gs, "vr_vignette")
            col.prop(gs, "vr_recenter_time")
