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
        world = context.world

        world_panel = layout.box()
        box = world_panel.box()
        box.label(text="Background Colors:", icon="COLOR")
        split = box.split()
        
        col = split.column()
        col.prop(world, "horizon_color", text="Horizon/Ambient")
        col.prop(world, "ambient_color", text="Ambient")
        
        col = split.column()
        if not world.use_sky_atmospheric:
            col.prop(world, "zenith_color", text="Zenith")
            col.prop(world, "nadir_color", text="Nadir")
            col.active = world.use_sky_blend
        else:
            col.prop(world, "zenith_color", text="Extinction")
            col.prop(world, "nadir_color", text="Inscattering")

        box2 = box.box()
        box2.label(text="Sky Render:", icon="WORLD")
        
        row = box2.row(align=True)
        row.prop(world, "use_sky_paper", text="Paper", toggle=True)
        row.prop(world, "use_sky_blend", text="Blend", toggle=True)
        row.prop(world, "use_sky_real", text="Real", toggle=True)

        sun_box = box2.box()
        sun_box.label(text="World Sun", icon="LAMP_SUN")
        # The assignment belongs to Scene (the runtime reads Scene.world_sun),
        # but it is presented with the World sky controls deliberately.
        sun_box.prop(context.scene, "world_sun_set")
        sun_box.prop(context.scene, "use_auto_world_sun")
        hour_row = sun_box.row()
        hour_row.active = context.scene.use_auto_world_sun
        hour_row.prop(context.scene, "auto_world_sun_hour")

        sky_box = box2.box()
        sky_box.label(text="Sky Objects", icon="WORLD")
        sky_box.prop(world, "use_sky_atmospheric", text="Atmospheric")
        sky_box.prop(world, "sun_size", text="Sun Size")
        sky_box.prop(world, "use_sky_stars", text="Stars")

        moon_row = sky_box.row()
        moon_row.prop(world, "use_sky_moon", text="Moon")
        moon_col = sky_box.column()
        moon_col.active = world.use_sky_moon
        moon_col.prop(world, "moon_size")
        moon_col.prop(world, "moon_brightness")

        if not world.use_sky_atmospheric:
            box3 = layout.box()
            box3.label(text="Atmosphere Settings:", icon="NLA")
            row = box3.row()
            row.prop(world, "sky_turbidity")
            row.prop(world, "ground_color")


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

    def draw_header(self, context):
        light = context.world.light_settings
        self.layout.prop(light, "use_environment_light", text="")

    def draw(self, context):
        layout = self.layout
        light = context.world.light_settings
        world = context.world

        environment_box = layout.box()
        main_box = environment_box.box()
        main_box.active = light.use_environment_light

        main_box.label(text="Environment Lighting:", icon="LAMP_SUN")
        split = main_box.split()
        split.prop(light, "environment_energy", text="Energy")
        split.prop(light, "environment_color", text="Color")

        exp_box = environment_box.box()
        exp_box.label(text="Camera Exposure:", icon="CAMERA_DATA")
        row = exp_box.row()
        row.prop(world, "exposure")
        row.prop(world, "color_range", text="Color Range")


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

    def draw_header(self, context):
        world = context.world
        self.layout.prop(world.mist_settings, "use_mist", text="")

    def draw(self, context):
        layout = self.layout
        world = context.world

        main_box = layout.box()
        main_box.active = world.mist_settings.use_mist

        row = main_box.row(align=True)
        row.prop(world.mist_settings, "mist_blend_type", text="")

        main_box.prop(world.mist_settings, "falloff")

        dist_box = main_box.box()
        dist_box.label(text="Distance:", icon="IMAGE_ZDEPTH")
        split = dist_box.split()
        col = split.column()
        col.prop(world.mist_settings, "start")
        col = split.column()
        col.prop(world.mist_settings, "depth")

        if world.mist_settings.falloff == 'HEIGHT':
            h_box = main_box.box()
            h_box.label(text="Height Fog:", icon="MOD_WAVE")
            split_h = h_box.split()
            col_h = split_h.column()
            col_h.prop(world.mist_settings, "height_fog")
            col_h = split_h.column()
            col_h.prop(world.mist_settings, "density_fog")

        main_box.prop(world.mist_settings, "intensity", text="Minimum Intensity", slider=True)


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


# ==============================================================================
# GLOBAL PROPERTIES (COMPARTILHADAS ENTRE OBJETOS VIA WORLD)
# ==============================================================================
class CUSTOM_PT_game_global_properties(CustomWorldButtonsPanel, Panel):
    bl_label = "Global Properties"
    bl_idname = "WORLD_PT_game_global_properties_custom"
    COMPAT_ENGINES = {'BLENDER_GAME'}

    @classmethod
    def poll(cls, context):
        scene = context.scene
        return (scene.world and scene.render.engine in cls.COMPAT_ENGINES)

    def draw(self, context):
        layout = self.layout
        world = context.world

        props = layout.operator("world.game_property_new", text="Add Global Property", icon='PLUS')
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
