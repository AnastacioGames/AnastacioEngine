"""Direcao de arte da versao Codex, com assets reais e iluminacao da engine."""
from mathutils import Vector


def setup(scene):
    world = scene.world
    world.use_sky_atmospheric = False
    world.use_sky_stars = False
    world.use_sky_blend = True
    world.use_sky_real = True
    world.horizon_color = (0.095, 0.14, 0.22)
    world.zenith_color = (0.012, 0.025, 0.065)
    w = world.weather_settings
    w.use_clouds = True
    w.cloud_coverage = 0.8
    w.cloud_scale = 0.65
    w.cloud_color = (0.16, 0.20, 0.29)
    w.rain_intensity = 0.48
    w.rain_streak_width = 0.28
    w.rain_ripple_intensity = 0.18
    w.rain_ripple_size = 0.65
    w.rain_ripple_rate = 0.55
    w.rain_puddle_amount = 0.58
    w.rain_puddle_reflection = 0.8
    w.rain_darken = 0.12
    scene.camera.data.game_fx.dof_blur = 1.0
    scene.camera.data.game_fx.vignette_strength = 0.16
    scene.objects['Cenario_Sun_pista1'].data.energy = 0.45
    scene.objects['Cenario_Sun_pista1'].data.color = (0.42, 0.60, 1.0)
    warm = scene.objects['Splash_Luz_quente']
    warm.data.energy = 3.0
    warm.data.color = (1.0, 0.58, 0.26)
    blue = scene.objects['Splash_Recorte_azul']
    blue.data.energy = 4.0
    blue.data.color = (0.20, 0.52, 1.0)
    blue.location = Vector((2.4, 2.0, 2.5))
