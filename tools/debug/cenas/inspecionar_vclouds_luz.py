# Inspeciona a cena multi-variante gerada por criar_cena_vclouds_luz.py: confirma as 4
# cenas, seus parametros de weather e a cadeia de Scene Actuators que alterna entre elas.
#   AnastacioEngine.exe -b <cena.range> --factory-startup --python inspecionar_vclouds_luz.py -- saida.txt
import bpy
import sys

argv = sys.argv[sys.argv.index('--') + 1:]
out = argv[0]

lines = []


def log(s):
    lines.append(s)


log('scenes=%s' % sorted(s.name for s in bpy.data.scenes))

for scene in bpy.data.scenes:
    log('--- %s ---' % scene.name)
    log('camera=%s' % (scene.camera.name if scene.camera else None))
    world = scene.world
    if world:
        w = world.weather_settings
        log('vcloud_silver_intensity=%s coverage=%s density=%s' % (
            w.vcloud_silver_intensity, w.vcloud_coverage, w.vcloud_density))
    terreno = next((o for o in scene.objects if o.name.endswith('_terreno')), None)
    if terreno:
        sensors = [(s.name, s.type, getattr(s, 'delay', None)) for s in terreno.game.sensors]
        controllers = [(c.name, c.type) for c in terreno.game.controllers]
        actuators = [(a.name, a.type, getattr(a, 'mode', None), getattr(a.scene, 'name', None) if hasattr(a, 'scene') else None)
                     for a in terreno.game.actuators]
        log('terreno.sensors=%s' % sensors)
        log('terreno.controllers=%s' % controllers)
        log('terreno.actuators=%s' % actuators)
    label = next((o for o in scene.objects if o.name.endswith('_label')), None)
    log('label_text=%s' % (label.data.body if label else None))

with open(out, 'w') as f:
    f.write('\n'.join(lines) + '\n')
print('INSPECAO VCLOUDS LUZ gravada em', out)
