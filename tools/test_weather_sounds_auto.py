# Chuva/raio ligados sem som no Effects: ao salvar (save_pre) e ao rodar o jogo (game_pre) a engine cria o
# modulo Effects, poe chuva.wav/trovao*.wav e copia os arquivos para <projeto>/sounds.
# Uso: AnastacioEngine.exe -b --factory-startup --python tools/test_weather_sounds_auto.py -- <pasta temporaria>
import os
import sys

import bpy
from bl_ui import properties_world_sound as ws

out_dir = sys.argv[sys.argv.index("--") + 1]
os.makedirs(out_dir, exist_ok=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
world = scene.world or bpy.data.worlds.new("World")
scene.world = world
for m in list(world.sound_modules):
    world.sound_modules.remove(m)

assert ws.weather_sounds_handler in bpy.app.handlers.save_pre
assert ws.weather_sounds_handler in bpy.app.handlers.game_pre

# Nada ligado: nada muda.
world.weather_settings.use_rain = False
assert ws.ensure_weather_sounds(scene) == 0 and len(world.sound_modules) == 0

# So um Empty com Lightning, sem chuva: entra so o trovao, o slot Rain fica vazio.
empty = bpy.data.objects.new("Raio", None)
scene.objects.link(empty)
empty.use_lightning = True
assert ws.ensure_weather_sounds(scene) == 3
assert not any(s.filepath for m in world.sound_modules for s in m.sounds if s.event != 'THUNDER')
# Som do raio desligado no Empty: nada entra.
for m in list(world.sound_modules):
    world.sound_modules.remove(m)
empty.lightning.use_sound = False
assert ws.ensure_weather_sounds(scene) == 0 and len(world.sound_modules) == 0
scene.objects.unlink(empty)
bpy.data.objects.remove(empty)
for m in list(world.sound_modules):
    world.sound_modules.remove(m)

world.weather_settings.use_rain = True
world.weather_settings.use_rain_lightning = True
# Som ligado por padrao; com os dois desligados nada entra.
ws_ = world.weather_settings
assert ws_.use_rain_sound and ws_.use_rain_lightning_sound
ws_.use_rain_sound = ws_.use_rain_lightning_sound = False
assert ws.ensure_weather_sounds(scene) == 0 and len(world.sound_modules) == 0
ws_.use_rain_sound = ws_.use_rain_lightning_sound = True
bomba = bpy.data.objects.new("Bomba", None)
assert bomba.game.explosive.use_sound and bomba.game.destruction.fx.use_sound if True else bomba.game.explosive.use_sound
bpy.data.objects.remove(bomba)
path = os.path.join(out_dir, "tempestade.range")
bpy.ops.wm.save_as_mainfile(filepath=path)  # arquivo novo: save_post copia os sons para o projeto
bpy.ops.wm.save_mainfile()  # agora o caminho gravado e relativo

effects = [m for m in world.sound_modules if m.type == 'EFFECTS']
assert len(effects) == 1, effects
by_event = {}
for s in effects[0].sounds:
    if s.filepath:
        by_event.setdefault(s.event, []).append(s.filepath)
assert len(by_event.get('THUNDER', [])) == 3, by_event
assert len(by_event.get('RAIN', [])) == 1, by_event
for fp in by_event['THUNDER'] + by_event['RAIN']:
    assert fp.startswith("//"), fp
    assert os.path.isfile(bpy.path.abspath(fp)), fp
for name in ("trovao1.wav", "trovao2.wav", "trovao3.wav", "chuva.wav"):
    assert os.path.isfile(os.path.join(out_dir, "sounds", name)), name

# Segunda vez nao duplica.
assert ws.ensure_weather_sounds(scene) == 0
# O .range gravado ja tem os caminhos relativos.
bpy.ops.wm.open_mainfile(filepath=path)
world = bpy.context.scene.world
scene = bpy.context.scene
effects = [m for m in world.sound_modules if m.type == 'EFFECTS']
assert all(s.filepath.startswith("//") for s in effects[0].sounds if s.event in {'THUNDER', 'RAIN'} and s.filepath)
# Usuario apagou o trovao: volta so o trovao.
for s in list(effects[0].sounds):
    if s.event == 'THUNDER':
        effects[0].sounds.remove(s)
assert ws.ensure_weather_sounds(scene) == 3
print("WEATHER_SOUNDS_AUTO_TEST ok")
