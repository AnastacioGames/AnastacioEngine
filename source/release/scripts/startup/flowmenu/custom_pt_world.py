import bpy
from bpy.types import Menu, Panel, Operator
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

def _rain_section(layout, weather, open_prop, title, use_prop, sound_prop=None):
    """Boxed Rain sub-section: arrow, enable check, optional sound toggle, then the title."""
    box = layout.box()
    row = box.row(align=True)
    row.prop(weather, open_prop, text="", emboss=False,
             icon='TRIA_DOWN' if getattr(weather, open_prop) else 'TRIA_RIGHT')
    row.prop(weather, use_prop, text="")
    if sound_prop:
        row.prop(weather, sound_prop, text="", icon='SPEAKER', emboss=True)
    row.label(text=title)
    return box

class CustomWorldButtonsPanel:
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "world"


# Abas Sky / Atmosphere / Properties no topo da aba World: so estado da tela (WindowManager), nao vai para o .range.
bpy.types.WindowManager.ae_world_panel_category = EnumProperty(
    name="World Panels",
    items=(
        ('SKY', "Sky", "Sky, Sun and Night", 'WORLD', 0),
        ('ATMOSPHERE', "Atmosphere", "Environment lighting and weather", 'MOD_SMOKE', 1),
        ('PROPERTIES', "Properties", "World properties", 'SETTINGS', 2),
    ),
    default='SKY',
)


def _world_tab_is(context, category):
    return context.window_manager.ae_world_panel_category == category


# ==============================================================================
# SELETOR DE MUNDO (TOPO DA ABA)
# ==============================================================================
class CUSTOM_PT_game_context_world(CustomWorldButtonsPanel, Panel):
    bl_label = ""
    bl_options = {'HIDE_HEADER', 'PIN_TO_TOP'}
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

        box = layout.box()
        split = box.split(factor=0.65)
        if scene:
            split.template_ID(scene, "world", new="world.new")
        elif world:
            split.template_ID(space, "pin_id")

        if scene.world:
            row = box.row(align=True)
            row.scale_y = 1.2
            row.prop(context.window_manager, "ae_world_panel_category", expand=True)


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


def _fog_add_property(obj, name, value, prop_type):
    bpy.context.scene.objects.active = obj
    bpy.ops.object.game_property_new(name=name, type=prop_type)
    obj.game.properties[name].value = value


def _fog_add_finish(context, obj):
    for other in context.scene.objects:
        other.select = False
    obj.select = True
    context.scene.objects.active = obj


def _fog_add_volume(context, sphere=False, smoke=False, fire=False):
    cursor = context.scene.cursor_location
    if sphere:
        bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, location=cursor)
    else:
        bpy.ops.mesh.primitive_cube_add(location=cursor)
    obj = context.active_object
    obj.name = "Fire Source" if fire else ("Smoke Source" if smoke else ("Fog Volume (Sphere)" if sphere else "Fog Volume (Box)"))
    obj.draw_type = 'WIRE'
    obj.show_wire = True
    obj.show_all_edges = True
    obj.hide_render = True
    obj.game.physics_type = 'NO_COLLISION'
    _fog_add_property(obj, 'fog_volume', 1.0, 'FLOAT')
    if sphere:
        _fog_add_property(obj, 'fog_shape', 'sphere', 'STRING')
    if smoke:
        obj.scale = (0.6, 0.6, 2.5)
        obj.color = (0.72, 0.74, 0.76, 1.0)
        _fog_add_property(obj, 'fog_smoke', 1.5, 'FLOAT')
    if fire:
        obj.scale = (0.8, 0.8, 1.5)
        obj.color = (1.0, 0.18, 0.02, 1.0)
        _fog_add_property(obj, 'fog_smoke', 1.2, 'FLOAT')
        _fog_add_property(obj, 'fog_fire', 0.9, 'FLOAT')
    _fog_add_finish(context, obj)


class OBJECT_OT_fog_volume_box_add(Operator):
    bl_idname = "object.fog_volume_box_add"
    bl_label = "Fog Volume (Box)"
    bl_description = "Add an invisible box Fog Volume at the 3D Cursor"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        _fog_add_volume(context)
        return {'FINISHED'}


class OBJECT_OT_fog_volume_sphere_add(Operator):
    bl_idname = "object.fog_volume_sphere_add"
    bl_label = "Fog Volume (Sphere)"
    bl_description = "Add an invisible sphere Fog Volume at the 3D Cursor"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        _fog_add_volume(context, sphere=True)
        return {'FINISHED'}


class OBJECT_OT_fog_smoke_source_add(Operator):
    bl_idname = "object.fog_smoke_source_add"
    bl_label = "Smoke Source"
    bl_description = "Add an invisible local smoke plume at the 3D Cursor"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        _fog_add_volume(context, sphere=True, smoke=True)
        return {'FINISHED'}


class OBJECT_OT_fog_fire_source_add(Operator):
    bl_idname = "object.fog_fire_source_add"
    bl_label = "Fire Source"
    bl_description = "Add an invisible local fire source at the 3D Cursor"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        _fog_add_volume(context, sphere=True, fire=True)
        return {'FINISHED'}


class OBJECT_OT_fog_pusher_add(Operator):
    bl_idname = "object.fog_pusher_add"
    bl_label = "Fog Pusher"
    bl_description = "Add an Empty that opens fog within its radius"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        bpy.ops.object.empty_add(type='PLAIN_AXES', location=context.scene.cursor_location)
        obj = context.active_object
        obj.name = "Fog Pusher"
        _fog_add_property(obj, 'fog_push', 3.0, 'FLOAT')
        _fog_add_finish(context, obj)
        return {'FINISHED'}


class INFO_MT_fog_add(Menu):
    bl_idname = "INFO_MT_fog_add"
    bl_label = "Fog"

    def draw(self, context):
        layout = self.layout
        layout.operator(OBJECT_OT_fog_volume_box_add.bl_idname, icon='MESH_CUBE')
        layout.operator(OBJECT_OT_fog_volume_sphere_add.bl_idname, icon='MESH_UVSPHERE')
        layout.separator()
        layout.operator(OBJECT_OT_fog_smoke_source_add.bl_idname, icon='MOD_SMOKE')
        layout.operator(OBJECT_OT_fog_fire_source_add.bl_idname, icon='LAMP_HEMI')
        layout.operator(OBJECT_OT_fog_pusher_add.bl_idname, icon='OUTLINER_OB_EMPTY')


def draw_fog_add_menu(self, context):
    self.layout.separator()
    self.layout.menu(INFO_MT_fog_add.bl_idname, icon='MOD_SMOKE')


# Clouds - Procedural e Clouds - Sky Layers: os botões Low/Medium/High só preenchem os valores abaixo,
# que continuam editáveis. Medium é o visual de antes da opção existir.
CLOUD_QUALITY_PRESETS = {
    'CLOUDS': {
        'LOW': {"cloud_detail": 3},
        'MEDIUM': {"cloud_detail": 5},
        'HIGH': {"cloud_detail": 7},
    },
    'SKY_LAYERS': {
        'LOW': {"sky_layer_detail": 3, "sky_layer_relief": 0.0},
        'MEDIUM': {"sky_layer_detail": 5, "sky_layer_relief": 1.0},
        'HIGH': {"sky_layer_detail": 7, "sky_layer_relief": 1.0},
    },
}
CLOUD_QUALITY_LEVELS = (('LOW', "Low"), ('MEDIUM', "Medium"), ('HIGH', "High"))


class WORLD_OT_cloud_quality_preset(Operator):
    """Fill the cloud quality values with a preset (they stay editable)"""
    bl_idname = "world.cloud_quality_preset"
    bl_label = "Cloud Quality Preset"
    bl_options = {'REGISTER', 'UNDO'}

    effect: EnumProperty(items=(('CLOUDS', "Clouds", ""), ('SKY_LAYERS', "Sky Layers", "")))
    level: EnumProperty(items=[(key, name, "") for key, name in CLOUD_QUALITY_LEVELS])

    @classmethod
    def poll(cls, context):
        return context.scene is not None and context.scene.world is not None

    def execute(self, context):
        world = getattr(context, "world", None) or context.scene.world
        weather = world.weather_settings
        for name, value in CLOUD_QUALITY_PRESETS[self.effect][self.level].items():
            setattr(weather, name, value)
        return {'FINISHED'}


def draw_cloud_quality(layout, weather, effect):
    """Botões Low/Medium/High (o que bate com os valores atuais fica pressionado) e os valores."""
    presets = CLOUD_QUALITY_PRESETS[effect]
    row = layout.row(align=True)
    row.label(text="Quality:")
    for key, name in CLOUD_QUALITY_LEVELS:
        matches = all(abs(getattr(weather, prop) - value) < 1e-4 for prop, value in presets[key].items())
        op = row.operator("world.cloud_quality_preset", text=name, depress=matches)
        op.effect = effect
        op.level = key
    for prop in presets['MEDIUM']:
        layout.prop(weather, prop)


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
        return (scene.world and scene.render.engine in cls.COMPAT_ENGINES and _world_tab_is(context, 'SKY'))

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
            row = box.row(align=True)
            row.operator("world.atmosphere_reset", text="Earth", icon='FILE_REFRESH')
            row.prop(world, "atmosphere_intensity")
            row.prop(world, "atmosphere_altitude")
            split = box.split()
            col = split.column(align=True)
            col.label(text="Air Color:")
            col.row(align=True).prop(world, "atmosphere_rayleigh_color", text="")
            col.prop(world, "atmosphere_rayleigh_density")
            col = split.column(align=True)
            col.label(text="")
            col.prop(world, "atmosphere_mie_density")
            col.prop(world, "atmosphere_mie_direction", slider=True)



class CUSTOM_PT_game_world_sun(CustomWorldButtonsPanel, Panel):
    """Top-level Sun panel alongside Sky."""
    bl_label = "Sun"
    bl_idname = "WORLD_PT_game_world_sun_custom"
    COMPAT_ENGINES = {'BLENDER_GAME'}

    @classmethod
    def poll(cls, context):
        scene = context.scene
        return (scene.world and not _world_nodes_active(context) and
                scene.render.engine in cls.COMPAT_ENGINES and
                _world_tab_is(context, 'SKY') and
                scene.world.sky_type in {'PROCEDURAL', 'ATMOSPHERIC'})

    def draw(self, context):
        scene = context.scene
        world = context.world
        box = self.layout.box()

        # The assignment belongs to Scene (the runtime reads Scene.world_sun),
        # but it is presented with the World sky controls deliberately.
        col = box.column(align=True)
        # The sun object is picked/created when the scene is converted: next Play only.
        not_live_layout(col).prop(scene, "world_sun_set", text="Object")
        not_live_layout(col).prop(scene, "use_auto_world_sun", text="Auto Sun Position")
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


class CUSTOM_PT_game_world_night(CustomWorldButtonsPanel, Panel):
    """Top-level Night panel alongside Sky."""
    bl_label = "Night"
    bl_idname = "WORLD_PT_game_world_night_custom"
    COMPAT_ENGINES = {'BLENDER_GAME'}

    @classmethod
    def poll(cls, context):
        scene = context.scene
        return (scene.world and not _world_nodes_active(context) and
                scene.render.engine in cls.COMPAT_ENGINES and
                _world_tab_is(context, 'SKY') and
                scene.world.sky_type in {'PROCEDURAL', 'ATMOSPHERIC'})

    def draw(self, context):
        world = context.world
        box = self.layout.box()

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
        return (scene.world and scene.render.engine in cls.COMPAT_ENGINES and _world_tab_is(context, 'ATMOSPHERE'))

    def draw(self, context):
        layout = self.layout
        world = context.world
        light = world.light_settings

        box = layout.box()
        box.label(text="Ambient:", icon='COLOR')
        split = box.split(factor=0.55)
        col = split.column()
        col.label(text="Color:")
        col.prop(world, "ambient_color", text="")
        col = split.column()
        col.label(text="")
        col.prop(light, "use_environment_light", text="Environment Light")

        col = box.column(align=True)
        col.active = light.use_environment_light
        col.prop(light, "environment_energy", text="Energy")
        col.row(align=True).prop(light, "environment_color", expand=True)

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
        return (scene.world and scene.render.engine in cls.COMPAT_ENGINES and _world_tab_is(context, 'ATMOSPHERE'))

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
        row.prop(weather, "show_expanded_vfog", text="Fog - Volumetric", emboss=True)
        row.prop(weather, "show_viewport_vfog", text="", icon="RESTRICT_RENDER_OFF", emboss=True)
        not_live_layout(row).prop(weather, "use_volumetric_fog", text="")

        if weather.show_expanded_vfog:
            col = main_box.column()
            col.active = weather.use_volumetric_fog
            low = weather.vfog_quality == 'LOW'

            row = col.row()
            row.prop(weather, "vfog_quality", text="")
            row.prop(weather, "vfog_resolution", text="")
            row = col.row()
            row.prop(weather, "vfog_color", text="")
            row.prop(weather, "vfog_density", text="Density")

            split = col.split()
            c = split.column()
            c.label(text="Shape:")
            c.prop(weather, "vfog_base", text="Base")
            c.prop(weather, "vfog_falloff", text="Falloff")
            c.prop(weather, "vfog_distance", text="Distance")
            c = split.column()
            c.label(text="Noise:")
            c.prop(weather, "vfog_noise_amount", text="Amount", slider=True)
            c.prop(weather, "vfog_noise_scale", text="Scale")
            c.prop(weather, "vfog_speed", text="Speed")
            row = col.row()
            row.prop(weather, "vfog_use_layer", toggle=True)
            row.prop(weather, "vfog_use_reach_clouds", toggle=True)

            split = col.split()
            c = split.column()
            c.label(text="Light:")
            c.prop(weather, "vfog_sun_intensity", text="Sun")
            c.prop(weather, "vfog_ambient", text="Ambient")
            c.prop(weather, "vfog_anisotropy", text="Anisotropy", slider=True)
            c = split.column()
            c.label(text="Lamps:")
            c.prop(weather, "vfog_use_lamps", text="Enabled")
            lamps = c.column()
            lamps.active = weather.vfog_use_lamps
            lamps.prop(weather, "vfog_light_intensity", text="Intensity")
            lamps.prop(weather, "vfog_max_lights", text="Max")

            split = col.split()
            c = split.column()
            c.label(text="Shafts:")
            sun = c.column()
            sun.active = not low
            sun.prop(weather, "vfog_use_sun_shafts", text="Sun Shafts")
            shafts = c.column()
            shafts.active = weather.vfog_use_lamps and not low
            shafts.prop(weather, "vfog_use_shafts", text="Lamp Shafts")
            shafts.prop(weather, "vfog_shaft_intensity", text="Intensity")
            dust = c.column()
            dust.active = not low
            dust.prop(weather, "vfog_dust", text="Dust", slider=True)
            c = split.column()
            c.label(text="Motion:")
            c.prop(weather, "vfog_use_wind", text="Wind")
            wind = c.column()
            wind.active = weather.vfog_use_wind
            wind.prop(weather, "vfog_wind_direction", text="Direction")
            c.prop(weather, "vfog_use_time_of_day", text="Morning Fog")
            morning = c.column()
            morning.active = weather.vfog_use_time_of_day
            morning.prop(weather, "vfog_morning_boost", text="Boost")

            row = col.row()
            row.prop(weather, "vfog_volumes_only", text="Only Volumes")
            row.prop(weather, "vfog_edge", text="Edge", slider=True)
            info = col.column()
            info.label(text="Add > Fog creates volumes, smoke sources and pushers", icon='INFO')
            info.label(text="fog_volume=density; fog_shape=sphere; fog_edge=soft edge", icon='INFO')
            info.label(text="fog_smoke=rise m/s; fog_fire=temperature; fog_push=radius m", icon='INFO')
            if context.world.mist_settings.use_mist:
                info.label(text="Mist is also on: the scene gets fogged twice", icon='ERROR')
            if weather.vfog_quality == 'HIGH':
                info.label(text="High quality is costly on integrated GPUs", icon='INFO')

        row = main_box.row(align=True)
        row.prop(weather, "show_expanded_rain", text="Rain", emboss=True)
        row.prop(weather, "show_viewport_rain", text="", icon="RESTRICT_RENDER_OFF", emboss=True)
        not_live_layout(row).prop(weather, "use_rain", text="")

        if weather.show_expanded_rain:
            col = main_box.column()
            col.active = weather.use_rain
            box = _rain_section(col, weather, "show_expanded_rain_droplets", "Droplets", "use_rain_droplets",
                               "use_rain_sound")
            if weather.show_expanded_rain_droplets:
                sub = box.column()
                sub.active = weather.use_rain_droplets
                sub.prop(weather, "rain_style")
                sub.prop(weather, "rain_intensity", slider=True)
                sub.prop(weather, "rain_speed", text="Fall Speed")
                if weather.rain_style == 'CLASSIC':
                    sub.prop(weather, "rain_density")
                    sub.prop(weather, "rain_wind", text="Wind")
                    sub.prop(weather, "rain_streak_width")
                sub.prop(weather, "rain_darken", slider=True)
                sub.prop(weather, "rain_color", text="Rain Color")

            for effect, label, prop_name, expanded_prop in (("ripple", "Ripples", "ripples_effect", "show_expanded_rain_ripples"),
                                                            ("splash", "Splash", "splash_effect", "show_expanded_rain_splash")):
                box = _rain_section(col, weather, expanded_prop, label, "use_rain_" + effect)
                if getattr(weather, expanded_prop):
                    sub = box.column()
                    sub.active = getattr(weather, "use_rain_" + effect)
                    puddle_only = sub.row()
                    puddle_only.prop(weather, "use_rain_" + effect + "_puddle_only")
                    prefix = "rain_" + effect + "_"
                    sub.prop(weather, prefix + "intensity")
                    sub.prop(weather, prefix + "size")
                    sub.prop(weather, prefix + "rate")
                    sub.prop(weather, prefix + "normal")
                    sub.prop(weather, prefix + "distance", text=label.rstrip("s") + " Distance")
                    sub.prop(weather, prefix + "min_up")
                    sub.label(text="Only objects with \"%s\" (all when none has it)" % prop_name, icon='INFO')

            box = _rain_section(col, weather, "show_expanded_rain_puddles", "Puddles", "use_rain_puddles")
            if weather.show_expanded_rain_puddles:
                sub = box.column()
                sub.active = weather.use_rain_puddles
                sub.prop(weather, "rain_puddle_amount", text="Amount", slider=True)
                sub.prop(weather, "rain_puddle_size", text="Size")
                sub.prop(weather, "rain_puddle_darkness", text="Darkness", slider=True)
                sub.prop(weather, "rain_puddle_reflection", text="Reflection", slider=True)
                sub.prop(weather, "use_rain_puddle_ssr", text="Screen Space Reflection")
                sub.prop(weather, "rain_puddle_distance", text="Puddle Distance")
                sub.prop(weather, "rain_puddle_min_up", text="Upward Surface")
                sub.label(text="Only objects with \"puddles_effect\" (all when none has it)", icon='INFO')

            box = _rain_section(col, weather, "show_expanded_rain_aura", "Aura", "use_rain_aura")
            if weather.show_expanded_rain_aura:
                sub = box.column()
                sub.active = weather.use_rain_aura
                sub.prop(weather, "rain_aura_property", text="Property")
                info = sub.column()
                info.label(text="Only objects with \"%s\" set to True" % (weather.rain_aura_property or "..."), icon='INFO')
                info.label(text="(every nearby object when none has it)")
                sub.prop(weather, "rain_aura_style", text="Style")
                sub.prop(weather, "rain_aura_size")
                sub.prop(weather, "rain_aura_rate")
                sub.prop(weather, "rain_aura_intensity")
                sub.prop(weather, "rain_aura_distance")

            box = _rain_section(col, weather, "show_expanded_rain_lightning", "Lightning",
                                "use_rain_lightning", "use_rain_lightning_sound")
            if weather.show_expanded_rain_lightning:
                sub = box.column()
                sub.active = weather.use_rain_lightning
                sub.prop(weather, "rain_lightning_rate", text="Per Minute")
                sub.prop(weather, "rain_lightning_intensity", text="Intensity")
                sub.prop(weather, "rain_lightning_distance", text="Distance")
                sub.prop(weather, "rain_lightning_width", text="Width")
                sub.prop(weather, "use_rain_lightning_side")

        row = main_box.row(align=True)
        row.prop(weather, "show_expanded_clouds", text="Clouds - Procedural", emboss=True)
        row.prop(weather, "show_viewport_clouds", text="", icon="RESTRICT_RENDER_OFF", emboss=True)
        not_live_layout(row).prop(weather, "use_clouds", text="")

        if weather.show_expanded_clouds:
            col = main_box.column()
            col.active = weather.use_clouds
            col.prop(weather, "cloud_coverage", slider=True)
            col.prop(weather, "cloud_scale")
            col.prop(weather, "cloud_speed")
            col.prop(weather, "cloud_color", text="Cloud Color")
            draw_cloud_quality(col.column(), weather, 'CLOUDS')

        row = main_box.row(align=True)
        row.prop(weather, "show_expanded_vclouds", text="Clouds - Volumetric", emboss=True)
        row.prop(weather, "show_viewport_vclouds", text="", icon="RESTRICT_RENDER_OFF", emboss=True)
        not_live_layout(row).prop(weather, "use_volumetric_clouds", text="")

        if weather.show_expanded_vclouds:
            col = main_box.column()
            col.active = weather.use_volumetric_clouds
            col.prop(weather, "vcloud_coverage", slider=True)
            col.prop(weather, "vcloud_scale")
            col.prop(weather, "vcloud_detail_scale")
            col.prop(weather, "vcloud_speed")
            col.prop(weather, "vcloud_density", slider=True)
            col.prop(weather, "vcloud_altitude")
            col.prop(weather, "vcloud_thickness")
            col.prop(weather, "vcloud_silver_intensity", slider=True)
            col.prop(weather, "vcloud_color", text="Cloud Color")
            col.prop(weather, "vcloud_quality", text="Quality")

            sub = col.column()
            sub_row = sub.row()
            sub_row.prop(weather, "vcloud_shadow_enable", text="")
            sub_row.label(text="Cast Shadow on Terrain")
            shadow_col = sub.column()
            shadow_col.active = weather.vcloud_shadow_enable
            shadow_col.prop(weather, "vcloud_shadow_strength", text="Strength")

            if weather.vcloud_quality == 'HIGH':
                info = col.column()
                info.label(text="High quality is costly on integrated GPUs", icon='INFO')

        row = main_box.row(align=True)
        row.prop(weather, "show_expanded_sky_layers", text="Clouds - Sky Layers", emboss=True)
        row.prop(weather, "show_viewport_sky_layers", text="", icon="RESTRICT_RENDER_OFF", emboss=True)
        not_live_layout(row).prop(weather, "use_sky_layers", text="")

        if weather.show_expanded_sky_layers:
            col = main_box.column()
            col.active = weather.use_sky_layers
            col.prop(weather, "sky_layer_coverage", slider=True)
            col.prop(weather, "sky_layer_scale")
            col.prop(weather, "sky_layer_speed")
            col.prop(weather, "sky_layer_color", text="Cloud Color")
            draw_cloud_quality(col.column(), weather, 'SKY_LAYERS')

        row = main_box.row(align=True)
        row.prop(weather, "show_expanded_lensflare", text="Lens Flare", emboss=True)
        row.prop(weather, "show_viewport_lensflare", text="", icon="RESTRICT_RENDER_OFF", emboss=True)
        not_live_layout(row).prop(weather, "use_lens_flare", text="")

        if weather.show_expanded_lensflare:
            col = main_box.column()
            col.active = weather.use_lens_flare
            not_live_layout(col).prop_search(weather, "sun_object_name", scene, "objects",
                                            text=iface_("Sun Object") + " *")
            col.prop(weather, "flare_scale")
            col.prop(weather, "flare_intensity")

        row = main_box.row(align=True)
        row.prop(weather, "show_expanded_earthquake", text="Earthquake", emboss=True)
        row.prop(weather, "use_earthquake", text="")

        if weather.show_expanded_earthquake:
            col = main_box.column()
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
    ("Fog - Volumetric", 'MOD_SMOKE', ("vfog_enabled", "vfog_density")),
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
        return (scene.world and scene.render.engine in cls.COMPAT_ENGINES and _world_tab_is(context, 'PROPERTIES'))

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
