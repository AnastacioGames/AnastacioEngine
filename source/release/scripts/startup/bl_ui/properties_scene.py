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
from math import cos, radians, sin
from mathutils import Vector
from bpy.types import (
    Menu,
    Operator,
    Panel,
    UIList,
)

from rna_prop_ui import PropertyPanel

from .properties_physics_common import (
    point_cache_ui,
    effector_weights_ui,
)


# This marker is stored on the generated Object so it persists in .blend files
# and lets the runtime distinguish it from a manually selected World Sun.
AUTO_WORLD_SUN_MARKER = "_range_auto_world_sun"
AUTO_WORLD_SUN_HOUR_PROPERTY = "sun_hour"
AUTO_WORLD_SUN_DIRECTION_PROPERTY = "sun_direction"
AUTO_WORLD_SUN_CAMERA_INITIAL_HEIGHT = "_range_auto_world_sun_camera_initial_height"


def _get_auto_sun_property(scene, name=AUTO_WORLD_SUN_HOUR_PROPERTY):
    """Return a World World Property reserved for the automatic sun."""
    world = scene.world
    if not world:
        return None

    for prop in world.properties:
        if prop.name == name:
            return prop
    return None


def _get_auto_sun_hour_property(scene):
    return _get_auto_sun_property(scene, AUTO_WORLD_SUN_HOUR_PROPERTY)


def _ensure_auto_sun_property(scene, name, default):
    prop = _get_auto_sun_property(scene, name)
    if prop:
        return prop

    # The World operator is the public Blender 2.79 API for inserting a
    # persistent Game/World Property. It is intentionally created only when
    # Automatic Sun is enabled, never merely by drawing the panel.
    if scene.world and bpy.context.scene == scene:
        bpy.ops.world.game_property_new(type='FLOAT', name=name)
        prop = _get_auto_sun_property(scene, name)
        if prop:
            prop.value = default
    return prop


def _ensure_auto_sun_hour_property(scene):
    return _ensure_auto_sun_property(scene, AUTO_WORLD_SUN_HOUR_PROPERTY, 12.0)


def _auto_sun_ground_reference(scene, sun):
    """Ground point 5 m ahead, using initial camera height as the floor offset."""
    camera = scene.camera
    if not camera:
        return Vector((0.0, 0.0, 0.0))

    camera_position = camera.matrix_world.to_translation()
    if AUTO_WORLD_SUN_CAMERA_INITIAL_HEIGHT not in sun:
        sun[AUTO_WORLD_SUN_CAMERA_INITIAL_HEIGHT] = camera_position.z

    forward = camera.matrix_world.to_quaternion() * Vector((0.0, 0.0, -1.0))
    forward.z = 0.0
    if forward.length_squared == 0.0:
        forward = Vector((0.0, 1.0, 0.0))
    else:
        forward.normalize()
    return camera_position + forward * 5.0 - Vector((0.0, 0.0, sun[AUTO_WORLD_SUN_CAMERA_INITIAL_HEIGHT]))


def _set_auto_sun_transform(scene, sun, hour):
    ground_reference = _auto_sun_ground_reference(scene, sun)
    angle = radians((hour - 12.0) * 15.0)
    # Direction turns the orbit plane around world Z (same math as KX_Scene).
    direction = radians(_get_auto_world_sun_direction(scene))
    horizontal = sin(angle) * 10.0
    sun.location = ground_reference + Vector((horizontal * sin(direction), -horizontal * cos(direction), cos(angle) * 10.0))
    # Sun lamps emit along local -Z. Track the ground reference rather than
    # spinning locally, so light always falls across the player area.
    sun.rotation_euler = (ground_reference - sun.location).to_track_quat('-Z', 'Y').to_euler()


def _get_auto_world_sun_hour(scene):
    prop = _get_auto_sun_hour_property(scene)
    return prop.value if prop else 12.0


def _set_auto_world_sun_hour(scene, hour):
    prop = _ensure_auto_sun_hour_property(scene)
    if prop:
        prop.value = hour

    world_sun = scene.world_sun_set
    if world_sun and world_sun.get(AUTO_WORLD_SUN_MARKER, False):
        _set_auto_sun_transform(scene, world_sun, hour)


def _get_auto_world_sun_direction(scene):
    prop = _get_auto_sun_property(scene, AUTO_WORLD_SUN_DIRECTION_PROPERTY)
    return prop.value if prop else 0.0


def _set_auto_world_sun_direction(scene, direction):
    prop = _ensure_auto_sun_property(scene, AUTO_WORLD_SUN_DIRECTION_PROPERTY, 0.0)
    if prop:
        prop.value = direction

    world_sun = scene.world_sun_set
    if world_sun and world_sun.get(AUTO_WORLD_SUN_MARKER, False):
        _set_auto_sun_transform(scene, world_sun, _get_auto_world_sun_hour(scene))


def _get_use_auto_world_sun(scene):
    world_sun = scene.world_sun_set
    return bool(world_sun and world_sun.get(AUTO_WORLD_SUN_MARKER, False))


def _set_use_auto_world_sun(scene, enabled):
    world_sun = scene.world_sun_set

    if enabled:
        if world_sun and world_sun.get(AUTO_WORLD_SUN_MARKER, False):
            return

        lamp = bpy.data.lamps.new(name="Auto World Sun", type='SUN')
        sun = bpy.data.objects.new(name="Auto World Sun", object_data=lamp)
        scene.objects.link(sun)
        sun[AUTO_WORLD_SUN_MARKER] = True

        hour = _get_auto_world_sun_hour(scene)
        _set_auto_sun_transform(scene, sun, hour)
        _ensure_auto_sun_hour_property(scene)

        scene.world_sun_set = sun
        # Rendering (lens flare, sky, light scatter) always reads Scene.world_sun.
        # The Lens Flare panel's "Sun Object" field is a separate, purely cosmetic
        # UI pointer (World.weather_settings.sun_object_name) that isn't consumed
        # by any render code, so keep it in sync here too or the panel would show
        # a stale/empty sun.
        if scene.world:
            scene.world.weather_settings.sun_object_name = sun.name
    elif world_sun and world_sun.get(AUTO_WORLD_SUN_MARKER, False):
        # This object belongs to the checkbox, so disabling it removes both
        # the World Sun assignment and the generated lamp datablock.
        if scene.world and scene.world.weather_settings.sun_object_name == world_sun.name:
            scene.world.weather_settings.sun_object_name = ""
        scene.world_sun_set = None
        scene.objects.unlink(world_sun)
        bpy.data.objects.remove(world_sun)


bpy.types.Scene.use_auto_world_sun = bpy.props.BoolProperty(
    name="Automatic Sun",
    description="Create a World Sun that orbits the ground reference 5 meters in front of the active camera in the game runtime",
    get=_get_use_auto_world_sun,
    set=_set_use_auto_world_sun,
)

bpy.types.Scene.auto_world_sun_hour = bpy.props.FloatProperty(
    name="Sun Hour",
    description="Time used by the automatic sun (also stored in World World Property 'sun_hour')",
    min=0.0,
    max=24.0,
    soft_min=0.0,
    soft_max=24.0,
    get=_get_auto_world_sun_hour,
    set=_set_auto_world_sun_hour,
)

bpy.types.Scene.auto_world_sun_direction = bpy.props.FloatProperty(
    name="Sun Direction",
    description="Heading in degrees around Z of the automatic sun path; noon stays overhead (also stored in World World Property 'sun_direction')",
    min=-360.0,
    max=360.0,
    soft_min=-180.0,
    soft_max=180.0,
    get=_get_auto_world_sun_direction,
    set=_set_auto_world_sun_direction,
)


class SCENE_MT_units_length_presets(Menu):
    """Unit of measure for properties that use length values"""
    bl_label = "Unit Presets"
    preset_subdir = "units_length"
    preset_operator = "script.execute_preset"
    draw = Menu.draw_preset


class SCENE_UL_keying_set_paths(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        # assert(isinstance(item, bpy.types.KeyingSetPath)
        kspath = item
        icon = layout.enum_item_icon(kspath, "id_type", kspath.id_type)
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            # Do not make this one editable in uiList for now...
            layout.label(text=kspath.data_path, translate=False, icon_value=icon)
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text="", icon_value=icon)


class SceneButtonsPanel:
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "scene"

    @classmethod
    def poll(cls, context):
        rd = context.scene.render
        return context.scene and (rd.engine in cls.COMPAT_ENGINES)


class SCENE_PT_scene(SceneButtonsPanel, Panel):
    bl_label = "Scene"
    COMPAT_ENGINES = {'BLENDER_RENDER', 'BLENDER_GAME'}

    def draw(self, context):
        layout = self.layout

        scene = context.scene

        box = layout.box()
        box.label(text="Scene:", icon="SCENE_DATA")
        box.prop(scene, "camera")
        box.prop(scene, "background_set", text="Background")
        if context.scene.render.engine != 'BLENDER_GAME':
            box.prop(scene, "active_clip", text="Active Clip")


class SCENE_PT_localization(SceneButtonsPanel, Panel):
    """Range.locale: translation table and language fonts of the game"""
    bl_label = "Game Languages"
    COMPAT_ENGINES = {'BLENDER_GAME'}

    def draw(self, context):
        from .properties_data_curve import draw_locale_project
        box = self.layout.box()
        draw_locale_project(box)


class SCENE_PT_unit(SceneButtonsPanel, Panel):
    bl_label = "Units"
    COMPAT_ENGINES = {'BLENDER_RENDER', 'BLENDER_GAME'}

    def draw(self, context):
        layout = self.layout

        unit = context.scene.unit_settings

        panel = layout.box()
        box = panel.box()
        box.label(text="Presets:", icon="BOOKMARKS")
        row = box.row(align=True)
        row.menu("SCENE_MT_units_length_presets", text=SCENE_MT_units_length_presets.bl_label)
        row.operator("scene.units_length_preset_add", text="", icon='ZOOMIN')
        row.operator("scene.units_length_preset_add", text="", icon='ZOOMOUT').remove_active = True

        box = panel.box()
        box.label(text="Units:", icon="UI")
        split = box.split(factor=0.35)
        split.label("Unit System:")
        split.prop(unit, "system", text="")
        split = box.split(factor=0.35)
        split.label("Angle:")
        split.prop(unit, "system_rotation", text="")

        col = box.column()
        col.enabled = unit.system != 'NONE'
        split = col.split(factor=0.35)
        split.label("Unit Scale:")
        split.prop(unit, "scale_length", text="")
        split = col.split(factor=0.35)
        split.row()
        split.prop(unit, "use_separate")

        # Units only change how the editor shows values; the game engine never reads them.
        if context.scene.render.engine == 'BLENDER_GAME':
            if unit.system != 'NONE' and unit.scale_length != 1.0:
                box.label(text="The game ignores Unit Scale, physics always uses 1 unit = 1 m", icon='ERROR')
            else:
                box.label(text="Editor display only, the game always uses 1 unit = 1 m", icon='INFO')


class SceneKeyingSetsPanel:

    @staticmethod
    def draw_keyframing_settings(context, layout, ks, ksp):
        SceneKeyingSetsPanel._draw_keyframing_setting(
            context, layout, ks, ksp, "Needed",
            "use_insertkey_override_needed", "use_insertkey_needed",
            userpref_fallback="use_keyframe_insert_needed",
        )
        SceneKeyingSetsPanel._draw_keyframing_setting(
            context, layout, ks, ksp, "Visual",
            "use_insertkey_override_visual", "use_insertkey_visual",
            userpref_fallback="use_visual_keying",
        )
        SceneKeyingSetsPanel._draw_keyframing_setting(
            context, layout, ks, ksp, "XYZ to RGB",
            "use_insertkey_override_xyz_to_rgb", "use_insertkey_xyz_to_rgb",
        )

    @staticmethod
    def _draw_keyframing_setting(context, layout, ks, ksp, label, toggle_prop, prop, userpref_fallback=None):
        if ksp:
            item = ksp

            if getattr(ks, toggle_prop):
                owner = ks
                propname = prop
            else:
                owner = context.user_preferences.edit
                if userpref_fallback:
                    propname = userpref_fallback
                else:
                    propname = prop
        else:
            item = ks

            owner = context.user_preferences.edit
            if userpref_fallback:
                propname = userpref_fallback
            else:
                propname = prop

        row = layout.row(align=True)
        row.prop(item, toggle_prop, text="", icon='STYLUS_PRESSURE', toggle=True)  # XXX: needs dedicated icon

        subrow = row.row()
        subrow.active = getattr(item, toggle_prop)
        if subrow.active:
            subrow.prop(item, prop, text=label)
        else:
            subrow.prop(owner, propname, text=label)


class SCENE_PT_keying_sets(SceneButtonsPanel, SceneKeyingSetsPanel, Panel):
    bl_label = "Keying Sets"
    COMPAT_ENGINES = {'BLENDER_RENDER'}

    def draw(self, context):
        layout = self.layout

        scene = context.scene

        box = layout.box()
        box.label(text="Keying Sets:", icon="KEYINGSET")
        row = box.row()

        col = row.column()
        col.template_list("UI_UL_list", "keying_sets", scene, "keying_sets", scene.keying_sets, "active_index", rows=1)

        col = row.column(align=True)
        col.operator("anim.keying_set_add", icon='ZOOMIN', text="")
        col.operator("anim.keying_set_remove", icon='ZOOMOUT', text="")

        ks = scene.keying_sets.active
        if ks and ks.is_path_absolute:
            box = layout.box()
            box.label(text="Active Keying Set:", icon="KEY_HLT")
            row = box.row()

            col = row.column()
            col.prop(ks, "bl_description")

            subcol = col.column()
            subcol.operator_context = 'INVOKE_DEFAULT'
            subcol.operator("anim.keying_set_export", text="Export to File").filepath = "keyingset.py"

            col = row.column()
            col.label(text="Keyframing Settings:")
            self.draw_keyframing_settings(context, col, ks, None)


class SCENE_PT_keying_set_paths(SceneButtonsPanel, SceneKeyingSetsPanel, Panel):
    bl_label = "Active Keying Set"
    COMPAT_ENGINES = {'BLENDER_RENDER'}

    @classmethod
    def poll(cls, context):
        ks = context.scene.keying_sets.active
        return (ks and ks.is_path_absolute)

    def draw(self, context):
        layout = self.layout

        scene = context.scene
        ks = scene.keying_sets.active

        box = layout.box()
        box.label(text="Paths:", icon="DRIVER")
        row = box.row()

        col = row.column()
        col.template_list("SCENE_UL_keying_set_paths", "", ks, "paths", ks.paths, "active_index", rows=1)

        col = row.column(align=True)
        col.operator("anim.keying_set_path_add", icon='ZOOMIN', text="")
        col.operator("anim.keying_set_path_remove", icon='ZOOMOUT', text="")

        ksp = ks.paths.active
        if ksp:
            box = layout.box()
            box.label(text="Target:", icon="EMPTY_DATA")
            col = box.column()
            col.template_any_ID(ksp, "id", "id_type")
            col.template_path_builder(ksp, "data_path", ksp.id)

            row = col.row(align=True)
            row.label(text="Array Target:")
            row.prop(ksp, "use_entire_array", text="All Items")
            if ksp.use_entire_array:
                row.label(text=" ")  # padding
            else:
                row.prop(ksp, "array_index", text="Index")

            box = layout.box()
            row = box.row()
            col = row.column()
            col.label(text="F-Curve Grouping:")
            col.prop(ksp, "group_method", text="")
            if ksp.group_method == 'NAMED':
                col.prop(ksp, "group")

            col = row.column()
            col.label(text="Keyframing Settings:")
            self.draw_keyframing_settings(context, col, ks, ksp)


class SCENE_PT_color_management(SceneButtonsPanel, Panel):
    bl_label = "Color Management"
    bl_options = {'DEFAULT_CLOSED'}
    COMPAT_ENGINES = {'BLENDER_RENDER'}

    def draw(self, context):
        layout = self.layout

        scene = context.scene

        box = layout.box()
        box.label(text="Display:", icon="RESTRICT_VIEW_OFF")
        box.prop(scene.display_settings, "display_device")

        box = layout.box()
        box.label(text="Render:", icon="RENDER_STILL")
        box.template_colormanaged_view_settings(scene, "view_settings")

        box = layout.box()
        box.label(text="Sequencer:", icon="SEQUENCE")
        box.prop(scene.sequencer_colorspace_settings, "name")


class SCENE_PT_audio(SceneButtonsPanel, Panel):
    bl_label = "Audio"
    bl_options = {'DEFAULT_CLOSED'}
    COMPAT_ENGINES = {'BLENDER_RENDER'}

    def draw(self, context):
        layout = self.layout

        scene = context.scene
        rd = context.scene.render
        ffmpeg = rd.ffmpeg

        box = layout.box()
        box.label(text="Audio:", icon="SPEAKER")
        box.prop(scene, "audio_volume")
        box.operator("sound.bake_animation")

        box = layout.box()
        split = box.split()

        col = split.column()
        col.label("Distance Model:")
        col.prop(scene, "audio_distance_model", text="")
        sub = col.column(align=True)
        sub.prop(scene, "audio_doppler_speed", text="Speed")
        sub.prop(scene, "audio_doppler_factor", text="Doppler")

        col = split.column()
        col.label("Format:")
        col.prop(ffmpeg, "audio_channels", text="")
        col.prop(ffmpeg, "audio_mixrate", text="Rate")


class SCENE_PT_physics(SceneButtonsPanel, Panel):
    bl_label = "Gravity"
    COMPAT_ENGINES = {'BLENDER_RENDER'}

    def draw_header(self, context):
        self.layout.prop(context.scene, "use_gravity", text="")

    def draw(self, context):
        layout = self.layout

        scene = context.scene

        layout.active = scene.use_gravity

        box = layout.box()
        box.label(text="Gravity:", icon="FORCE_FORCE")
        box.prop(scene, "gravity", text="")


class SCENE_PT_rigid_body_world(SceneButtonsPanel, Panel):
    bl_label = "Rigid Body World"
    COMPAT_ENGINES = {'BLENDER_RENDER'}

    @classmethod
    def poll(cls, context):
        scene = context.scene
        rd = scene.render
        return scene and (rd.engine in cls.COMPAT_ENGINES)

    def draw_header(self, context):
        scene = context.scene
        rbw = scene.rigidbody_world
        if rbw is not None:
            self.layout.prop(rbw, "enabled", text="")

    def draw(self, context):
        layout = self.layout

        scene = context.scene

        rbw = scene.rigidbody_world

        if rbw is None:
            layout.operator("rigidbody.world_add")
        else:
            box = layout.box()
            box.label(text="Rigid Body World:", icon="PHYSICS")
            box.operator("rigidbody.world_remove")

            col = box.column()
            col.active = rbw.enabled

            col = col.column()
            col.prop(rbw, "group")
            col.prop(rbw, "constraints")

            split = col.split()

            col = split.column()
            col.prop(rbw, "time_scale", text="Speed")
            col.prop(rbw, "use_split_impulse")

            col = split.column()
            col.prop(rbw, "steps_per_second", text="Steps Per Second")
            col.prop(rbw, "solver_iterations", text="Solver Iterations")


class SCENE_PT_rigid_body_cache(SceneButtonsPanel, Panel):
    bl_label = "Rigid Body Cache"
    bl_options = {'DEFAULT_CLOSED'}
    COMPAT_ENGINES = {'BLENDER_RENDER'}

    @classmethod
    def poll(cls, context):
        rd = context.scene.render
        scene = context.scene
        return scene and scene.rigidbody_world and (rd.engine in cls.COMPAT_ENGINES)

    def draw(self, context):
        scene = context.scene
        rbw = scene.rigidbody_world

        point_cache_ui(self, context, rbw.point_cache, rbw.point_cache.is_baked is False and rbw.enabled, 'RIGID_BODY')


class SCENE_PT_rigid_body_field_weights(SceneButtonsPanel, Panel):
    bl_label = "Rigid Body Field Weights"
    bl_options = {'DEFAULT_CLOSED'}
    COMPAT_ENGINES = {'BLENDER_RENDER'}

    @classmethod
    def poll(cls, context):
        rd = context.scene.render
        scene = context.scene
        return scene and scene.rigidbody_world and (rd.engine in cls.COMPAT_ENGINES)

    def draw(self, context):
        scene = context.scene
        rbw = scene.rigidbody_world

        effector_weights_ui(self, context, rbw.effector_weights, 'RIGID_BODY')


class SCENE_PT_simplify(SceneButtonsPanel, Panel):
    bl_label = "Simplify"
    COMPAT_ENGINES = {'BLENDER_RENDER'}

    def draw_header(self, context):
        rd = context.scene.render
        self.layout.prop(rd, "use_simplify", text="")

    def draw(self, context):
        layout = self.layout

        rd = context.scene.render

        layout.active = rd.use_simplify

        box = layout.box()
        box.label(text="Simplify:", icon="MOD_DECIM")
        split = box.split()

        col = split.column()
        col.label(text="Viewport:")
        col.prop(rd, "simplify_subdivision", text="Subdivision")
        col.prop(rd, "simplify_child_particles", text="Child Particles")

        col = split.column()
        col.label(text="Render:")
        col.prop(rd, "simplify_subdivision_render", text="Subdivision")
        col.prop(rd, "simplify_child_particles_render", text="Child Particles")
        col.prop(rd, "simplify_shadow_samples", text="Shadow Samples")
        col.prop(rd, "simplify_ao_sss", text="AO and SSS")
        col.prop(rd, "use_simplify_triangulate")


class SCENE_PT_custom_props(SceneButtonsPanel, PropertyPanel, Panel):
    COMPAT_ENGINES = {'BLENDER_RENDER', 'BLENDER_GAME'}
    _context_path = "scene"
    _property_type = bpy.types.Scene


class RangeArmorExportSettings(bpy.types.PropertyGroup):
    """Project-level export preferences written to launcher/config.json before RangeArmor Panel opens."""

    cook_before_export: bpy.props.BoolProperty(
        name="Cook before export",
        description="Prepare a fresh cooked cache for one-click export; disable to package without cooked files",
        default=True,
    )

    export_windows64: bpy.props.BoolProperty(
        name="Windows 64-bit",
        description="Include a Windows 64-bit build when exporting with RangeArmor Panel",
        default=True,
    )
    export_linux64: bpy.props.BoolProperty(
        name="Linux 64-bit",
        description="Include a Linux 64-bit build when exporting with RangeArmor Panel",
        default=True,
    )
    product_name: bpy.props.StringProperty(
        name="Product Name",
        description="Name shown to players and used for the exported executable/package",
        default="",
    )
    product_version: bpy.props.StringProperty(
        name="Version",
        description="Version string embedded in the exported package",
        default="1.0.0",
    )
    company_name: bpy.props.StringProperty(
        name="Company Name",
        description="Publisher/company name embedded in the exported package",
        default="",
    )
    icon_path: bpy.props.StringProperty(
        name="Icon",
        description="Icon file used for the exported game (leave empty to keep RangeArmor Panel's default)",
        default="",
        subtype='FILE_PATH',
    )
    keep_debug_overlays: bpy.props.BoolProperty(
        name="Keep debug overlays",
        description="Keeps the framerate/profile and debug properties overlays in the exported game "
                    "as saved in the scene. Off: the published game never shows them",
        default=False,
    )


class SCENE_PT_rangearmor_export(SceneButtonsPanel, Panel):
    bl_label = "Export (RangeArmor)"
    bl_context = "export"
    COMPAT_ENGINES = {'BLENDER_RENDER', 'BLENDER_GAME'}

    @classmethod
    def poll(cls, context):
        rd = context.scene.render
        return (context.scene and rd.engine in cls.COMPAT_ENGINES and
                context.window_manager.ae_export_panel_category == 'RANGEARMOR')

    def draw_header(self, context):
        self.layout.label(text="", icon='DESKTOP')

    def draw(self, context):
        layout = self.layout

        export = context.scene.rangearmor_export

        box = layout.box()
        box.label(text="Platforms:", icon="EXPORT")
        row = box.row(align=True)
        row.prop(export, "export_windows64", toggle=True)
        row.prop(export, "export_linux64", toggle=True)
        box.label(text="Desktop builds", icon='INFO')

        box = layout.box()
        box.label(text="Package Info:", icon="FILE_TEXT")
        box.prop(export, "product_name")
        box.prop(export, "product_version")
        box.prop(export, "company_name")
        box.prop(export, "icon_path")
        box.label(text="Empty fields keep the RangeArmor Panel defaults", icon='INFO')

        box = layout.box()
        box.label(text="Export:", icon="EXPORT")
        box.prop(export, "cook_before_export")
        box.prop(export, "keep_debug_overlays")
        box.operator("wm.one_click_export_rangearmor", text="Export Game (1 Click)", icon='EXPORT')
        box.operator("wm.export_with_rangearmor", text="Open RangeArmor Panel", icon='RANGEARMOR')
        box.label(text="The file must be saved in the project's data/ folder", icon='INFO')


# ---------------------------------------------------------------------------
# Scene Overview: which object uses which script, component, animation or
# particle emitter. Read-only list; clicking a name selects the object.

def _overview_entries(ob):
    """Returns a list of (kind, icon, text) describing what the object uses."""
    out = []
    game = ob.game
    for comp in game.components:
        out.append(('COMPONENTS', 'SCRIPTWIN', "%s.%s" % (comp.module, comp.name)))
    for cont in game.controllers:
        if cont.type != 'PYTHON':
            continue
        if cont.mode == 'MODULE':
            if cont.module:
                out.append(('SCRIPTS', 'SCRIPT', cont.module))
        elif cont.text:
            out.append(('SCRIPTS', 'TEXT', cont.text.name))
    ad = ob.animation_data
    if ad and ad.action:
        out.append(('ANIMATION', 'ACTION', ad.action.name))
    for act in game.actuators:
        if act.type == 'ACTION' and act.action:
            out.append(('ANIMATION', 'ACTION', "%s (actuator)" % act.action.name))
    if getattr(ob, "use_gpu_particles", False):
        out.append(('PARTICLES', 'PARTICLES', "GPU Particles"))
        if getattr(ob, "use_gpu_particles_mix", False):
            out.append(('PARTICLES', 'PARTICLES', "GPU Particles (2nd)"))
    for psys in ob.particle_systems:
        out.append(('PARTICLES', 'PARTICLES', psys.name))
    return out


class SCENE_OT_overview_select(Operator):
    """Select this object and make it active"""
    bl_idname = "scene.overview_select"
    bl_label = "Select Object"
    bl_options = {'REGISTER', 'UNDO'}

    name = bpy.props.StringProperty()

    def execute(self, context):
        ob = context.scene.objects.get(self.name)
        if ob is None:
            return {'CANCELLED'}
        if ob.hide_select:
            # Nao retira o bloqueio sozinho; mantem a selecao atual e avisa.
            self.report({'WARNING'}, "'%s' has selection disabled (Restrict Select)" % ob.name)
            return {'CANCELLED'}
        for o in context.selected_objects:
            o.select = False
        ob.select = True
        context.scene.objects.active = ob
        return {'FINISHED'}


class SCENE_PT_overview(SceneButtonsPanel, Panel):
    """Overview of the objects that use scripts, components, animation or particles"""
    bl_label = "Scene Overview"
    bl_context = "render_layer"
    bl_options = {'DEFAULT_CLOSED'}
    COMPAT_ENGINES = {'BLENDER_GAME'}

    MAX_ROWS = 300

    def draw(self, context):
        layout = self.layout
        wm = context.window_manager

        row = layout.row(align=True)
        row.prop(wm, "scene_overview_filter", expand=True)
        layout.prop(wm, "scene_overview_search", text="", icon='VIEWZOOM')

        kinds = wm.scene_overview_filter
        search = wm.scene_overview_search.lower()
        active = context.active_object

        shown = 0
        total = 0
        col = layout.column(align=True)
        for ob in sorted(context.scene.objects, key=lambda o: o.name):
            entries = [e for e in _overview_entries(ob) if e[0] in kinds]
            if not entries:
                continue
            if search and search not in ob.name.lower() and                     not any(search in e[2].lower() for e in entries):
                continue
            total += 1
            if shown >= self.MAX_ROWS:
                continue
            shown += 1
            box = col.box()
            r = box.row()
            op = r.operator("scene.overview_select", text=ob.name,
                            icon='OBJECT_DATA', emboss=(ob == active))
            op.name = ob.name
            for _kind, icon, text in entries:
                sub = box.row()
                sub.label(text="    " + text, icon=icon, translate=False)

        if total == 0:
            layout.label(text="No objects found", icon='INFO')
        else:
            txt = "%d object(s)" % total
            if total > shown:
                txt += " - showing %d, use the search" % shown
            layout.label(text=txt)


def _register_overview_props():
    wm = bpy.types.WindowManager
    wm.scene_overview_filter = bpy.props.EnumProperty(
        name="Show",
        options={'ENUM_FLAG'},
        items=(
            ('SCRIPTS', "Scripts", "Python controllers (script and module)"),
            ('COMPONENTS', "Components", "Python components"),
            ('ANIMATION', "Animation", "Actions on the object or in Action actuators"),
            ('PARTICLES', "Particles", "GPU particles and particle systems"),
        ),
        default={'SCRIPTS', 'COMPONENTS', 'ANIMATION', 'PARTICLES'},
    )
    wm.scene_overview_search = bpy.props.StringProperty(
        name="Search", description="Filter by object, script, component or action name")


_register_overview_props()


classes = (
    SCENE_MT_units_length_presets,
    SCENE_UL_keying_set_paths,
    SCENE_PT_scene,
    SCENE_PT_localization,
    SCENE_PT_unit,
    SCENE_PT_keying_sets,
    SCENE_PT_keying_set_paths,
    SCENE_PT_color_management,
    SCENE_PT_audio,
    SCENE_PT_physics,
    SCENE_PT_rigid_body_world,
    SCENE_PT_rigid_body_cache,
    SCENE_PT_rigid_body_field_weights,
    SCENE_PT_simplify,
    SCENE_OT_overview_select,
    SCENE_PT_overview,
    # SCENE_PT_custom_props,  # disabled: Custom Properties panel unused
    RangeArmorExportSettings,
    SCENE_PT_rangearmor_export,
)

if __name__ == "__main__":  # only for live edit.
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)
