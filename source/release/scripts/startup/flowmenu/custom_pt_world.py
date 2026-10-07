import bpy
from bpy.types import Panel, Operator
from bpy.props import StringProperty, EnumProperty, BoolProperty, IntProperty
from bpy.app.translations import pgettext_iface as iface_


def not_live_layout(layout):
    """Sub-layout para campos que não mudam com a UI liberada no Play (só valem no próximo Play)."""
    sub = layout.row(align=True)
    sub.enabled = not getattr(bpy.app, "is_game_live_ui", False)
    return sub

# ==============================================================================
# CLASSE BASE PARA A ABA WORLD
# ==============================================================================
class CustomWorldButtonsPanel:
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "world"


# ==============================================================================
# SELETOR DE MUNDO (TOPO DA ABA)
# ==============================================================================
class CUSTOM_PT_game_context_world(CustomWorldButtonsPanel, Panel):
    bl_label = ""
    bl_options = {'HIDE_HEADER'}
    bl_idname = "WORLD_PT_game_context_world_custom"
    COMPAT_ENGINES = {'BLENDER_GAME'}

    @classmethod
    def poll(cls, context):
        rd = context.scene.render
        return (context.scene) and (rd.engine in cls.COMPAT_ENGINES)

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        world = context.world
        space = context.space_data

        split = layout.split(factor=0.65)
        if scene:
            split.template_ID(scene, "world", new="world.new")
        elif world:
            split.template_ID(space, "pin_id")


# ==============================================================================
# CÉU (SKY)
# ==============================================================================
ATMOSPHERE_EARTH = {
    "atmosphere_intensity": 20.0,
    "atmosphere_rayleigh_color": (5.5 / 22.4, 13.0 / 22.4, 1.0),
    "atmosphere_rayleigh_density": 1.0,
    "atmosphere_mie_density": 1.0,
    "atmosphere_mie_direction": 0.758,
    "atmosphere_altitude": 1000.0,
}


class WORLD_OT_atmosphere_reset(bpy.types.Operator):
    """Set the atmospheric sky back to Earth air"""
    bl_idname = "world.atmosphere_reset"
    bl_label = "Reset to Earth"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.world is not None

    def execute(self, context):
        for name, value in ATMOSPHERE_EARTH.items():
            setattr(context.world, name, value)
        return {'FINISHED'}


def _world_nodes_active(context):
    world = context.world
    return context.scene.game_settings.use_shading_nodes and world.use_nodes and world.node_tree


class CUSTOM_PT_game_world(CustomWorldButtonsPanel, Panel):
    bl_label = "Sky"
    bl_idname = "WORLD_PT_game_world_custom"
    COMPAT_ENGINES = {'BLENDER_GAME'}

    @classmethod
    def poll(cls, context):
        scene = context.scene
        return (scene.world and scene.render.engine in cls.COMPAT_ENGINES)

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        world = context.world
        sky = world.sky_type

        if _world_nodes_active(context):
            layout.label(text="The World uses nodes: the node tree draws the sky", icon='INFO')
            layout.prop(world, "use_nodes", text="Use World Nodes")
            return

        layout.row().prop(world, "sky_type", expand=True)

        box = layout.box()
        if sky == 'FLAT':
            box.prop(world, "horizon_color", text="Color")
        elif sky == 'GRADIENT':
            row = box.row()
            row.prop(world, "horizon_color", text="Horizon")
            row.prop(world, "zenith_color", text="Zenith")
            row = box.row(align=True)
            row.prop(world, "use_sky_paper", text="Paper", toggle=True)
            sub = row.row(align=True)
            sub.active = world.use_sky_paper
            sub.prop(world, "use_sky_real", text="Real", toggle=True)
        elif sky == 'PROCEDURAL':
            row = box.row()
            row.prop(world, "horizon_color", text="Horizon")
            row.prop(world, "zenith_color", text="Zenith")
            row.prop(world, "nadir_color", text="Nadir")
            row = box.row(align=True)
            row.prop(world, "sky_turbidity", text="Turbidity")
            row.prop(world, "ground_color", text="Ground")
        else:
            row = box.row()
            row.label(text="Atmosphere:", icon='WORLD')
            row.operator("world.atmosphere_reset", text="Earth", icon='FILE_REFRESH')
            col = box.column(align=True)
            col.prop(world, "atmosphere_intensity")
            col.prop(world, "atmosphere_altitude")
            col = box.column(align=True)
            col.prop(world, "atmosphere_rayleigh_color")
            col.prop(world, "atmosphere_rayleigh_density")
            col = box.column(align=True)
            col.prop(world, "atmosphere_mie_density")
            col.prop(world, "atmosphere_mie_direction", slider=True)

        if sky in {'PROCEDURAL', 'ATMOSPHERIC'}:
            # The assignment belongs to Scene (the runtime reads Scene.world_sun),
            # but it is presented with the World sky controls deliberately.
            box = layout.box()
            box.label(text="Sun:", icon='LAMP_SUN')
            col = box.column(align=True)
            col.prop(scene, "world_sun_set", text="Object")
            col.prop(scene, "use_auto_world_sun", text="Automatic")
            row = box.row(align=True)
            sub = row.row(align=True)
            sub.active = scene.use_auto_world_sun
            sub.prop(scene, "auto_world_sun_hour", text="Hour")
            row.prop(world, "sun_size", text="Disc Size")
            row = box.row(align=True)
            row.active = scene.use_auto_world_sun
            row.prop(scene, "auto_world_sun_direction", text="Direction")
            if not scene.world_sun_set:
                box.label(text="Without a Sun object the sky stays at noon and has no sun disc", icon='ERROR')

            box = layout.box()
            box.label(text="Night:", icon='SOLO_ON')
            row = box.row()
            row.prop(world, "use_sky_stars", text="Stars")
            row.prop(world, "use_sky_moon", text="Moon")
            row = box.row()
            row.active = world.use_sky_stars
            row.prop(world, "star_style", text="Style")
            row = box.row(align=True)
            row.prop(world, "use_sky_aurora", text="Aurora")
            sub = row.row()
            sub.active = world.use_sky_aurora
            sub.prop(world, "aurora_colors", text="")
            row = box.row(align=True)
            row.active = world.use_sky_moon
            row.prop(world, "moon_size", text="Size")
            row.prop(world, "moon_brightness", text="Brightness")


# ==============================================================================
# ENVIRONMENT (AMBIENTE E EXPOSIÇÃO)
# ==============================================================================
class CUSTOM_PT_game_environment_lighting(CustomWorldButtonsPanel, Panel):
    bl_label = "Environment"
    bl_idname = "WORLD_PT_game_environment_lighting_custom"
    COMPAT_ENGINES = {'BLENDER_GAME'}

    @classmethod
    def poll(cls, context):
        scene = context.scene
        return (scene.world and scene.render.engine in cls.COMPAT_ENGINES)

    def draw(self, context):
        layout = self.layout
        world = context.world
        light = world.light_settings

        box = layout.box()
        box.label(text="Ambient:", icon='COLOR')
        box.prop(world, "ambient_color", text="Color")

        row = box.row(align=True)
        row.prop(light, "use_environment_light", text="")
        sub = row.row(align=True)
        sub.active = light.use_environment_light
        sub.prop(light, "environment_energy", text="Environment Light")
        sub.prop(light, "environment_color", text="")

        box = layout.box()
        box.label(text="Exposure:", icon='CAMERA_DATA')
        row = box.row(align=True)
        row.prop(world, "exposure")
        row.prop(world, "color_range", text="Range")


# ==============================================================================
# FOG / MIST (NEBLINA) -- desenhado dentro do painel Weather
# ==============================================================================
def draw_fog_settings(layout, world):
    mist = world.mist_settings

    box = layout.box()
    if world.sky_type == 'ATMOSPHERIC':
        # In the atmospheric sky the horizon/zenith/nadir colors are only the fog colors.
        row = box.row()
        row.prop(world, "horizon_color", text="Color")
        row.prop(world, "zenith_color", text="Extinction")
        row.prop(world, "nadir_color", text="Inscattering")
    else:
        box.label(text="Uses the sky horizon color", icon='INFO')
    row = box.row(align=True)
    row.prop(mist, "mist_blend_type", text="")
    row.prop(mist, "falloff", text="")
    box.prop(mist, "intensity", text="Minimum Intensity", slider=True)

    box = layout.box()
    box.label(text="Distance:", icon='ARROW_LEFTRIGHT')
    row = box.row(align=True)
    row.prop(mist, "start")
    row.prop(mist, "depth")
    if mist.falloff == 'HEIGHT':
        row = box.row(align=True)
        row.prop(mist, "height_fog")
        row.prop(mist, "density_fog")


# ==============================================================================
# WEATHER (CHUVA, NUVENS, LENS FLARE)
# ==============================================================================
class CUSTOM_PT_game_weather(CustomWorldButtonsPanel, Panel):
    bl_label = "Weather"
    bl_idname = "WORLD_PT_game_weather_custom"
    COMPAT_ENGINES = {'BLENDER_GAME'}

    @classmethod
    def poll(cls, context):
        scene = context.scene
        return (scene.world and scene.render.engine in cls.COMPAT_ENGINES)

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        weather = context.world.weather_settings

        main_box = layout.box()
        main_box.label(text="Weather Effects:", icon="WORLD")

        row = main_box.row(align=True)
        row.prop(weather, "show_expanded_fog", text="Fog", emboss=True)
        row.prop(weather, "show_viewport_fog", text="", icon="RESTRICT_RENDER_OFF", emboss=True)
        row.prop(context.world.mist_settings, "use_mist", text="")

        if weather.show_expanded_fog:
            col = main_box.column()
            col.active = context.world.mist_settings.use_mist
            draw_fog_settings(col, context.world)

        row = main_box.row(align=True)
        row.prop(weather, "show_expanded_rain", text="Rain", emboss=True)
        row.prop(weather, "show_viewport_rain", text="", icon="RESTRICT_RENDER_OFF", emboss=True)
        not_live_layout(row).prop(weather, "use_rain", text="")

        if weather.show_expanded_rain:
            col = main_box.column(align=True)
            col.active = weather.use_rain
            row = col.row()
            row.prop(weather, "use_rain_droplets", text="")
            row.label(text="Droplets")
            col.prop(weather, "rain_style")
            col.prop(weather, "rain_intensity", slider=True)
            col.prop(weather, "rain_speed", text="Fall Speed")
            if weather.rain_style == 'CLASSIC':
                col.prop(weather, "rain_density")
                col.prop(weather, "rain_wind", text="Wind")
                col.prop(weather, "rain_streak_width")
            col.prop(weather, "rain_darken", slider=True)
            col.prop(weather, "rain_color", text="Rain Color")

            # Ripples e Splash: mesma lista, na mesma ordem.
            for effect, label, prop_name in (("ripple", "Ripples", "ripples_effect"),
                                             ("splash", "Splash", "splash_effect")):
                row = col.row()
                row.prop(weather, "use_rain_" + effect, text="")
                row.label(text=label)
                sub = col.column()
                sub.active = getattr(weather, "use_rain_" + effect)
                prefix = "rain_" + effect + "_"
                sub.prop(weather, prefix + "intensity")
                sub.prop(weather, "use_rain_" + effect + "_puddle_only")
                sub.prop(weather, prefix + "size")
                sub.prop(weather, prefix + "rate")
                sub.prop(weather, prefix + "normal")
                sub.prop(weather, prefix + "distance", text=label.rstrip("s") + " Distance")
                sub.prop(weather, prefix + "min_up")
                sub.label(text="Only objects with \"%s\" (all when none has it)" % prop_name, icon='INFO')

            row = col.row()
            row.prop(weather, "use_rain_puddles", text="")
            row.label(text="Puddles")
            sub = col.column()
            sub.active = weather.use_rain_puddles
            sub.prop(weather, "rain_puddle_amount", text="Amount", slider=True)
            sub.prop(weather, "rain_puddle_size", text="Size")
            sub.prop(weather, "rain_puddle_darkness", text="Darkness", slider=True)
            sub.prop(weather, "rain_puddle_reflection", text="Reflection", slider=True)
            sub.prop(weather, "use_rain_puddle_ssr", text="Screen Space Reflection")
            sub.prop(weather, "rain_puddle_distance", text="Puddle Distance")
            sub.prop(weather, "rain_puddle_min_up", text="Upward Surface")
            sub.label(text="Only objects with \"puddles_effect\" (all when none has it)", icon='INFO')

            row = col.row()
            row.prop(weather, "use_rain_aura", text="")
            row.label(text="Aura")
            sub = col.column()
            sub.active = weather.use_rain_aura
            sub.prop(weather, "rain_aura_property", text="Property")
            info = sub.column(align=True)
            info.label(text="Only objects with \"%s\" set to True" % (weather.rain_aura_property or "..."), icon='INFO')
            info.label(text="(every nearby object when none has it)")
            sub.prop(weather, "rain_aura_style", text="Style")
            sub.prop(weather, "rain_aura_size")
            sub.prop(weather, "rain_aura_rate")
            sub.prop(weather, "rain_aura_intensity")
            sub.prop(weather, "rain_aura_distance")

            row = col.row()
            row.prop(weather, "use_rain_lightning", text="")
            row.label(text="Lightning")
            sub = col.column()
            sub.active = weather.use_rain_lightning
            sub.prop(weather, "rain_lightning_rate", text="Per Minute")
            sub.prop(weather, "rain_lightning_intensity", text="Intensity")
            sub.prop(weather, "rain_lightning_distance", text="Distance")
            sub.prop(weather, "rain_lightning_width", text="Width")
            sub.prop(weather, "use_rain_lightning_side")

        row = main_box.row(align=True)
        row.prop(weather, "show_expanded_clouds", text="Clouds", emboss=True)
        row.prop(weather, "show_viewport_clouds", text="", icon="RESTRICT_RENDER_OFF", emboss=True)
        not_live_layout(row).prop(weather, "use_clouds", text="")

        if weather.show_expanded_clouds:
            col = main_box.column(align=True)
            col.active = weather.use_clouds
            col.prop(weather, "cloud_coverage", slider=True)
            col.prop(weather, "cloud_scale")
            col.prop(weather, "cloud_speed")
            col.prop(weather, "cloud_color", text="Cloud Color")

        row = main_box.row(align=True)
        row.prop(weather, "show_expanded_lensflare", text="Lens Flare", emboss=True)
        row.prop(weather, "show_viewport_lensflare", text="", icon="RESTRICT_RENDER_OFF", emboss=True)
        not_live_layout(row).prop(weather, "use_lens_flare", text="")

        if weather.show_expanded_lensflare:
            col = main_box.column(align=True)
            col.active = weather.use_lens_flare
            not_live_layout(col).prop_search(weather, "sun_object_name", scene, "objects",
                                            text=iface_("Sun Object") + " *")
            col.prop(weather, "flare_scale")
            col.prop(weather, "flare_intensity")

        row = main_box.row(align=True)
        row.prop(weather, "show_expanded_earthquake", text="Earthquake", emboss=True)
        row.prop(weather, "use_earthquake", text="")

        if weather.show_expanded_earthquake:
            col = main_box.column(align=True)
            col.active = weather.use_earthquake
            col.prop(weather, "earthquake_level", slider=True, text="Level")
            col.prop(weather, "earthquake_scale", slider=True, text="Scale")
            col.prop(weather, "earthquake_mode", text="Direction")
            col.prop(weather, "earthquake_camera", slider=True, text="Camera Shake Scale")


# ==============================================================================
# GLOBAL PROPERTIES (COMPARTILHADAS ENTRE OBJETOS VIA WORLD)
# ==============================================================================
# Propriedades criadas pela engine, agrupadas por efeito: (título, ícone, nomes).
BUILTIN_WORLD_PROPERTY_GROUPS = (
    ("Sun", 'LAMP_SUN', ("sun_hour", "sun_direction")),
    ("Rain", 'MOD_FLUIDSIM', ("rain_enabled", "rain_intensity")),
    ("Lightning", 'FORCE_CHARGE', ("lightning_enabled",)),
    ("Clouds", 'MOD_SMOKE', ("clouds_enabled", "cloud_type")),
    ("Mist", 'RESTRICT_VIEW_ON', ("mist_enabled", "mist_density")),
    ("Lens Flare", 'LAMP_POINT', ("lens_flare_enabled",)),
    ("Earthquake", 'FORCE_TURBULENCE', ("earthquake_enabled", "earthquake_level")),
    ("Player", 'POSE_HLT', ("player_under_cover",)),
)

BUILTIN_WORLD_PROPERTIES = {
    name for _title, _icon, names in BUILTIN_WORLD_PROPERTY_GROUPS for name in names
}


def _split_header(name):
    parts = name.split("/")
    title = parts[1] if len(parts) > 1 else "Header"
    icon = parts[2] if len(parts) > 2 else "GRIP"
    return title, icon


def _header_icon_items(self, context):
    from .custom_pt_properties import get_icon_enum_items
    return get_icon_enum_items(self, context)


class WORLD_OT_game_header_add(Operator):
    bl_idname = "world.game_header_add"
    bl_label = "Add Header"
    bl_description = "Create a Bool World Property in the format C_Header/Title/Icon"
    bl_options = {'REGISTER', 'UNDO'}

    title: StringProperty(name="Title", default="Header")
    icon: EnumProperty(name="Icon", items=_header_icon_items)
    expanded: BoolProperty(name="Expanded", default=True)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "title")
        layout.prop(self, "icon")
        layout.prop(self, "expanded")

    def execute(self, context):
        world = context.world
        if not world:
            return {'CANCELLED'}
        title = self.title.replace("/", " ").strip() or "Header"
        bpy.ops.world.game_property_new(name="C_Header/{}/{}".format(title, self.icon or "GRIP"), type='BOOL')
        world.properties[-1].value = bool(self.expanded)
        return {'FINISHED'}

    def invoke(self, context, event):
        try:
            self.icon = "GRIP"
        except Exception:
            pass
        return context.window_manager.invoke_props_dialog(self)


class WORLD_OT_game_header_edit(Operator):
    bl_idname = "world.game_header_edit"
    bl_label = "Edit Header"
    bl_description = "Change the title and icon of this header"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty()
    title: StringProperty(name="Title", default="Header")
    icon: EnumProperty(name="Icon", items=_header_icon_items)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "title")
        layout.prop(self, "icon")

    def execute(self, context):
        world = context.world
        if not world or not (0 <= self.index < len(world.properties)):
            return {'CANCELLED'}
        title = self.title.replace("/", " ").strip() or "Header"
        world.properties[self.index].name = "C_Header/{}/{}".format(title, self.icon or "GRIP")
        return {'FINISHED'}

    def invoke(self, context, event):
        world = context.world
        if not world or not (0 <= self.index < len(world.properties)):
            return {'CANCELLED'}
        self.title, icon = _split_header(world.properties[self.index].name)
        try:
            self.icon = icon
        except Exception:
            self.icon = "GRIP"
        return context.window_manager.invoke_props_dialog(self)


class CUSTOM_PT_game_global_properties(CustomWorldButtonsPanel, Panel):
    bl_label = "World Properties"
    bl_idname = "WORLD_PT_game_global_properties_custom"
    COMPAT_ENGINES = {'BLENDER_GAME'}

    @classmethod
    def poll(cls, context):
        scene = context.scene
        return (scene.world and scene.render.engine in cls.COMPAT_ENGINES)

    def _draw_prop_row(self, parent, prop, index, builtin):
        row = parent.box().row()
        row.prop(prop, "name", text="")
        row.prop(prop, "type", text="")
        row.prop(prop, "value", text="")
        if builtin:
            # Propriedades criadas pela engine: ordem fixa pelo grupo e sem botão de apagar.
            return
        sub = row.row(align=True)
        props = sub.operator("world.game_property_move", text="", icon='TRIA_UP')
        props.index = index
        props.direction = 'UP'
        props = sub.operator("world.game_property_move", text="", icon='TRIA_DOWN')
        props.index = index
        props.direction = 'DOWN'
        row.operator("world.game_property_remove", text="", icon='X', emboss=False).index = index

    def draw(self, context):
        layout = self.layout
        world = context.world

        row = layout.row(align=True)
        props = row.operator("world.game_property_new", text="Add World Property", icon='PLUS')
        props.name = ""
        row.operator("world.game_header_add", text="Add Header", icon='PLUS')

        index_by_name = {prop.name: i for i, prop in enumerate(world.properties)}

        for title, icon, names in BUILTIN_WORLD_PROPERTY_GROUPS:
            present = [name for name in names if name in index_by_name]
            if not present:
                continue
            box = layout.box()
            box.label(text=title, icon=icon)
            col = box.column()
            for name in present:
                i = index_by_name[name]
                self._draw_prop_row(col, world.properties[i], i, True)

        custom = [(i, prop) for i, prop in enumerate(world.properties)
                  if prop.name not in BUILTIN_WORLD_PROPERTIES]
        col = None
        group_open = True
        for i, prop in custom:
            if prop.name.startswith("C_Header/"):
                box = layout.box()
                group_open = self._draw_header_row(box, prop, i)
                col = box.column() if group_open else None
                continue
            if col is None:
                if not group_open:
                    continue
                box = layout.box()
                box.label(text="Custom Properties", icon='LINENUMBERS_ON')
                col = box.column()
            self._draw_prop_row(col, prop, i, False)

    def _draw_header_row(self, box, prop, index):
        row = box.row(align=True)
        is_open = bool(prop.value)
        row.prop(prop, "value", text="", emboss=False,
                 icon='TRIA_DOWN' if is_open else 'TRIA_RIGHT')
        title, icon = _split_header(prop.name)
        try:
            row.label(text=title, icon=icon)
        except TypeError:
            row.label(text=title, icon='GRIP')
        row.operator("world.game_header_edit", text="", icon='GREASEPENCIL', emboss=False).index = index
        sub = row.row(align=True)
        props = sub.operator("world.game_property_move", text="", icon='TRIA_UP')
        props.index = index
        props.direction = 'UP'
        props = sub.operator("world.game_property_move", text="", icon='TRIA_DOWN')
        props.index = index
        props.direction = 'DOWN'
        row.operator("world.game_property_remove", text="", icon='X', emboss=False).index = index
        return is_open
