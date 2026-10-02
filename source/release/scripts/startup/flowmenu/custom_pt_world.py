import bpy
from bpy.types import Panel

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
            if not scene.world_sun_set:
                box.label(text="Without a Sun object the sky stays at noon and has no sun disc", icon='ERROR')

            box = layout.box()
            box.label(text="Night:", icon='SOLO_ON')
            row = box.row()
            row.prop(world, "use_sky_stars", text="Stars")
            row.prop(world, "use_sky_moon", text="Moon")
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
# FOG / MIST (NEBLINA)
# ==============================================================================
class CUSTOM_PT_game_mist(CustomWorldButtonsPanel, Panel):
    bl_label = "Fog"
    bl_idname = "WORLD_PT_game_mist_custom"
    COMPAT_ENGINES = {'BLENDER_GAME'}

    @classmethod
    def poll(cls, context):
        scene = context.scene
        return (scene.world and scene.render.engine in cls.COMPAT_ENGINES)

    def draw_header(self, context):
        self.layout.prop(context.world.mist_settings, "use_mist", text="")

    def draw(self, context):
        layout = self.layout
        world = context.world
        mist = world.mist_settings
        layout.active = mist.use_mist

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
        row.prop(weather, "show_expanded_rain", text="Rain", emboss=True)
        row.prop(weather, "use_rain", text="")

        if weather.show_expanded_rain:
            col = main_box.column(align=True)
            col.active = weather.use_rain
            col.prop(weather, "rain_style")
            col.prop(weather, "rain_intensity", slider=True)
            col.prop(weather, "rain_speed", text="Fall Speed")
            if weather.rain_style == 'CLASSIC':
                col.prop(weather, "rain_density")
                col.prop(weather, "rain_wind", text="Wind")
                col.prop(weather, "rain_streak_width")
            col.prop(weather, "rain_darken", slider=True)
            col.prop(weather, "rain_color", text="Rain Color")

            row = col.row()
            row.prop(weather, "use_rain_droplets", text="")
            row.label(text="Droplets")

            row = col.row()
            row.prop(weather, "use_rain_ripple", text="")
            row.label(text="Ripples")
            sub = col.column()
            sub.active = weather.use_rain_ripple
            sub.prop(weather, "rain_ripple_intensity")
            sub.prop(weather, "rain_ripple_normal")
            sub.prop(weather, "rain_ripple_distance")
            sub.prop(weather, "rain_ripple_min_up")

            row = col.row()
            row.prop(weather, "use_rain_splash", text="")
            row.label(text="Splash")
            sub = col.column()
            sub.active = weather.use_rain_splash
            sub.prop(weather, "rain_splash_size")
            sub.prop(weather, "rain_splash_rate")
            sub.prop(weather, "rain_splash_intensity")
            sub.prop(weather, "rain_splash_distance")

            row = col.row()
            row.prop(weather, "use_rain_aura", text="")
            row.label(text="Aura")
            sub = col.column()
            sub.active = weather.use_rain_aura
            sub.prop(weather, "rain_aura_property", text="Property")
            info = sub.column(align=True)
            info.label(text="Objects need a Bool game property", icon='INFO')
            info.label(text="\"%s\" set to True" % (weather.rain_aura_property or "..."))
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

        row = main_box.row(align=True)
        row.prop(weather, "show_expanded_clouds", text="Clouds", emboss=True)
        row.prop(weather, "use_clouds", text="")

        if weather.show_expanded_clouds:
            col = main_box.column(align=True)
            col.active = weather.use_clouds
            col.prop(weather, "cloud_coverage", slider=True)
            col.prop(weather, "cloud_scale")
            col.prop(weather, "cloud_speed")
            col.prop(weather, "cloud_color", text="Cloud Color")

        row = main_box.row(align=True)
        row.prop(weather, "show_expanded_lensflare", text="Lens Flare", emboss=True)
        row.prop(weather, "use_lens_flare", text="")

        if weather.show_expanded_lensflare:
            col = main_box.column(align=True)
            col.active = weather.use_lens_flare
            col.prop_search(weather, "sun_object_name", scene, "objects", text="Sun Object")
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
class CUSTOM_PT_game_global_properties(CustomWorldButtonsPanel, Panel):
    bl_label = "World Properties"
    bl_idname = "WORLD_PT_game_global_properties_custom"
    COMPAT_ENGINES = {'BLENDER_GAME'}

    @classmethod
    def poll(cls, context):
        scene = context.scene
        return (scene.world and scene.render.engine in cls.COMPAT_ENGINES)

    def draw(self, context):
        layout = self.layout
        world = context.world

        props = layout.operator("world.game_property_new", text="Add World Property", icon='PLUS')
        props.name = ""

        for i, prop in enumerate(world.properties):
            box = layout.box()
            row = box.row()
            row.prop(prop, "name", text="")
            row.prop(prop, "type", text="")
            row.prop(prop, "value", text="")
            sub = row.row(align=True)
            props = sub.operator("world.game_property_move", text="", icon='TRIA_UP')
            props.index = i
            props.direction = 'UP'
            props = sub.operator("world.game_property_move", text="", icon='TRIA_DOWN')
            props.index = i
            props.direction = 'DOWN'
            row.operator("world.game_property_remove", text="", icon='X', emboss=False).index = i
