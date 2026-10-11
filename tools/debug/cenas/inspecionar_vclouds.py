# Inspeciona uma cena .range ja salva e grava em arquivo a confirmacao dos campos
# de Volumetric Clouds / Clouds / Sky Layers no World, e dos objetos esperados (Sun,
# terreno, monte, camera, modulo de autoclose).
#   AnastacioEngine.exe -b <cena.range> --factory-startup --python inspecionar_vclouds.py -- saida.txt
import bpy
import sys

argv = sys.argv[sys.argv.index('--') + 1:]
out = argv[0]

scene = bpy.context.scene
lines = []


def log(s):
    lines.append(s)


log('scene=%s' % scene.name)
log('camera=%s' % (scene.camera.name if scene.camera else None))
names = sorted(ob.name for ob in scene.objects)
log('objects=%s' % names)

suns = [ob for ob in scene.objects if ob.type == 'LAMP' and ob.data.type == 'SUN']
log('suns=%s' % [s.name for s in suns])

world = scene.world
log('world=%s' % (world.name if world else None))
if world:
    w = world.weather_settings
    for attr in ('use_clouds', 'use_sky_layers', 'use_volumetric_clouds',
                 'vcloud_quality', 'vcloud_shadow_enable', 'vcloud_shadow_strength',
                 'vcloud_coverage', 'vcloud_altitude', 'vcloud_thickness',
                 'vcloud_density', 'vcloud_detail_scale', 'vcloud_silver_intensity',
                 'vcloud_scale', 'vcloud_speed', 'vcloud_color'):
        log('weather.%s=%s' % (attr, getattr(w, attr)))

terreno = scene.objects.get('terreno')
if terreno:
    log('terreno.always_sensors=%s' % [s.name for s in terreno.game.sensors])
    log('terreno.controllers=%s' % [(c.name, c.type, getattr(c, 'module', None)) for c in terreno.game.controllers])

txt = bpy.data.texts.get('vclouds_autoclose.py')
log('autoclose_text_present=%s' % (txt is not None))
if txt:
    log('autoclose_text_has_tick=%s' % ('def tick(' in txt.as_string()))

with open(out, 'w') as f:
    f.write('\n'.join(lines) + '\n')
print('INSPECAO gravada em', out)
