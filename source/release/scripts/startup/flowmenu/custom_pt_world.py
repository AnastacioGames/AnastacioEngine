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
# CORES DO MUNDO E CÉU
# ==============================================================================
class CUSTOM_PT_game_world(CustomWorldButtonsPanel, Panel):
    bl_label = "World"
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

        main_box = layout.box()
        main_box.label(text="World Settings:", icon="WORLD")

        row = main_box.row(align=True)
        row.prop(world, "use_sky_paper", text="Paper", toggle=True)
        row.prop(world, "use_sky_blend", text="Blend", toggle=True)
        row.prop(world, "use_sky_real", text="Real", toggle=True)

        # Colors
        main_box.prop(world, "flow_expand_colors", text="Colors", emboss=True)
        if world.flow_expand_colors:
            split = main_box.split()
            col = split.column()
            col.prop(world, "horizon_color", text="Horizon")
            col.prop(world, "ambient_color", text="Ambient")

            col = split.column()
            if world.use_sky_atmospheric:
                col.prop(world, "zenith_color", text="Extinction")
                col.prop(world, "nadir_color", text="Inscattering")
            else:
                col.active = world.use_sky_blend
                col.prop(world, "zenith_color", text="Zenith")
                col.prop(world, "nadir_color", text="Nadir")

        # Sun
        main_box.prop(world, "flow_expand_sun", text="Sun", emboss=True)
        if world.flow_expand_sun:
            col = main_box.column(align=True)
            # The assignment belongs to Scene (the runtime reads Scene.world_sun),
            # but it is presented with the World sky controls deliberately.
            col.prop(scene, "world_sun_set", text="Object")
            col.prop(scene, "use_auto_world_sun", text="Automatic")
            hour_row = col.row()
            hour_row.active = scene.use_auto_world_sun
            hour_row.prop(scene, "auto_world_sun_hour", text="Hour")
            col.prop(world, "sun_size", text="Size")

        # Sky Objects
        main_box.prop(world, "flow_expand_sky", text="Sky Objects", emboss=True)
        if world.flow_expand_sky:
            split = main_box.split()
            col = split.column()
            col.prop(world, "use_sky_atmospheric", text="Atmospheric")
            col.prop(world, "use_sky_stars", text="Stars")

            col = split.column()
            col.prop(world, "use_sky_moon", text="Moon")
            moon_col = col.column()
            moon_col.active = world.use_sky_moon
            moon_col.prop(world, "moon_size", text="Size")
            moon_col.prop(world, "moon_brightness", text="Brightness")

            if not world.use_sky_atmospheric:
                row = main_box.row()
                row.prop(world, "sky_turbidity", text="Turbidity")
                row.prop(world, "ground_color", text="Ground")


# ==============================================================================
# ENVIRONMENT LIGHTING (ILUMINAÇÃO GLOBAL)
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
        light = context.world.light_settings
        world = context.world

        main_box = layout.box()
        main_box.label(text="Environment Effects:", icon="LAMP_SUN")

        row = main_box.row(align=True)
        row.prop(world, "flow_expand_env_light", text="Environment Lighting", emboss=True)
        row.prop(light, "use_environment_light", text="")

        if world.flow_expand_env_light:
            col = main_box.column(align=True)
            col.active = light.use_environment_light
            col.prop(light, "environment_energy", text="Energy")
            col.prop(light, "environment_color", text="Color")

        main_box.prop(world, "flow_expand_exposure", text="Camera Exposure", emboss=True)
        if world.flow_expand_exposure:
            col = main_box.column(align=True)
            col.prop(world, "exposure")
            col.prop(world, "color_range", text="Color Range")


# ==============================================================================
# FOG / MIST (NEBLINA)
# ==============================================================================
class CUSTOM_PT_game_mist(CustomWorldButtonsPanel, Panel):
    bl_label = "Fog / Mist"
    bl_idname = "WORLD_PT_game_mist_custom"
    COMPAT_ENGINES = {'BLENDER_GAME'}

    @classmethod
    def poll(cls, context):
        scene = context.scene
        return (scene.world and scene.render.engine in cls.COMPAT_ENGINES)

    def draw(self, context):
        layout = self.layout
        world = context.world
        mist = world.mist_settings

        main_box = layout.box()
        main_box.label(text="Fog Effects:", icon="IMAGE_ZDEPTH")

        row = main_box.row(align=True)
        row.prop(world, "flow_expand_mist", text="Mist", emboss=True)
        row.prop(mist, "use_mist", text="")

        if world.flow_expand_mist:
            col = main_box.column(align=True)
            col.active = mist.use_mist
            col.prop(mist, "mist_blend_type", text="")
            col.prop(mist, "falloff")
            col.prop(mist, "intensity", text="Minimum Intensity", slider=True)

        main_box.prop(world, "flow_expand_mist_distance", text="Distance", emboss=True)
        if world.flow_expand_mist_distance:
            col = main_box.column(align=True)
            col.active = mist.use_mist
            col.prop(mist, "start")
            col.prop(mist, "depth")

        if mist.falloff == 'HEIGHT':
            main_box.prop(world, "flow_expand_mist_height", text="Height Fog", emboss=True)
            if world.flow_expand_mist_height:
                col = main_box.column(align=True)
                col.active = mist.use_mist
                col.prop(mist, "height_fog")
                col.prop(mist, "density_fog")


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
            sub.prop(weather, "rain_ripple_distance")
            sub.prop(weather, "rain_ripple_min_up")

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
