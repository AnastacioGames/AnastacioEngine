# Gera weather_logic_test.range (logic bricks) e weather_logic_test_python.range
# (os mesmos bricks convertidos por logic.convert_to_component).
#   RangeEngine.exe -b --factory-startup --python make_weather_logic_test.py
# Rodar no RangeRuntime: cada Delay dispara um Property actuator de clima; no
# frame 30 o controller "check" imprime WEATHER_CHECK ok/falha e fecha o jogo.
import os
import bpy

HERE = os.path.dirname(os.path.abspath(__file__))

# (categoria, propriedade RNA do efeito, identificador, valor)
CASES = [
    ('RAIN', "weather_effect", 'WEATHER_RAIN', True),
    ('RAIN', "weather_effect", 'WEATHER_RAIN_INTENSITY', 0.75),
    ('RAIN', "weather_effect", 'WEATHER_DROPLETS', True),
    ('SPLASH', "splash_effect", 'WEATHER_SPLASH_SIZE', 0.4),
    ('AURA', "aura_effect", 'WEATHER_AURA', True),
    ('LIGHTNING', "lightning_effect", 'WEATHER_LIGHTNING_RATE', 6.0),
    ('CLOUDS', "cloud_effect", 'WEATHER_CLOUD_COVERAGE', 0.6),
    ('LENS_FLARE', "lens_flare_effect", 'WEATHER_FLARE_INTENSITY', 1.5),
    ('MIST', "mist_effect", 'WEATHER_MIST_START', 7.0),
    ('EARTHQUAKE', "earthquake_effect", 'WEATHER_EARTHQUAKE', True),
    ('EARTHQUAKE', "earthquake_effect", 'WEATHER_EARTHQUAKE_LEVEL', 2.0),
]

CHECK = '''import bge
w = bge.logic.getCurrentScene().world
ob = bge.logic.getCurrentController().owner
bad = []
# 1) Valores gravados pelos actuators (bricks ou component).
for name, want in EXPECT:
    got = w.getWeather(name)
    if abs(float(got) - float(want)) > 1e-4:
        bad.append("%s: esperado %r, veio %r" % (name, want, got))
# 2) Ida e volta set/get em todos os nomes.
for name in NAMES:
    want = True if name in BOOLS else (1.0 if name == "earthquake_level" else 0.5)
    try:
        w.setWeather(name, want)
        got = w.getWeather(name)
        if abs(float(got) - float(want)) > 1e-4:
            bad.append("%s: set %r, get %r" % (name, want, got))
    except Exception as e:
        bad.append("%s: %s" % (name, e))
ok = ob.get("counter", 0) == 3 and not bad
out = bge.logic.expandPath("//weather_check_" + ("python" if len(ob.components) else "bricks") + ".txt")
with open(out, "w") as f:
    f.write("WEATHER_CHECK %s counter=%r bad=%r\\n" % ("ok" if ok else "falha", ob.get("counter"), bad))
bge.logic.endGame()
'''


def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_GAME'
    if scene.world is None:
        scene.world = bpy.data.worlds.new("World")
    world = scene.world

    bpy.ops.mesh.primitive_cube_add()
    ob = bpy.context.active_object
    ob.name = "WeatherDriver"
    bpy.ops.object.game_property_new(type='INT', name="counter")

    for i, (cat, prop, ident, value) in enumerate(CASES):
        tag = "w%02d" % i
        bpy.ops.logic.sensor_add(type='DELAY', name=tag)
        s = ob.game.sensors[-1]
        s.delay = 2 + i
        bpy.ops.logic.controller_add(type='LOGIC_AND', name=tag)
        c = ob.game.controllers[-1]
        bpy.ops.logic.actuator_add(type='PROPERTY', name=tag)
        a = ob.game.actuators[-1]
        a.actuator_mode = 'WEATHER_EFFECTS'
        a.weather_category = cat
        setattr(a, prop, ident)
        if isinstance(value, bool):
            a.runtime_bool_value = value
        else:
            a.runtime_value[0] = value
        s.link(c)
        a.link(c)

    # Game Property local com Add (caminho de bricks ja suportado, serve de controle).
    for i in range(3):
        tag = "add%d" % i
        bpy.ops.logic.sensor_add(type='DELAY', name=tag)
        s = ob.game.sensors[-1]
        s.delay = 3 + i
        bpy.ops.logic.controller_add(type='LOGIC_AND', name=tag)
        c = ob.game.controllers[-1]
        bpy.ops.logic.actuator_add(type='PROPERTY', name=tag)
        a = ob.game.actuators[-1]
        a.property = "counter"
        a.mode = 'ADD'
        a.value = "1"
        s.link(c)
        a.link(c)

    text = bpy.data.texts.new("weather_check.py")
    names = sorted(set(i[len("WEATHER_"):].lower() for _c, _p, i, _v in CASES) | {
        "rain_density", "rain_speed", "rain_wind", "rain_darken", "rain_streak_width", "ripples",
        "ripple_intensity", "ripple_normal", "splash", "splash_rate", "splash_intensity",
        "splash_distance", "aura_size", "aura_rate", "aura_intensity", "aura_distance",
        "lightning", "lightning_intensity", "lightning_distance", "lightning_width", "clouds",
        "cloud_scale", "cloud_speed", "lens_flare", "flare_scale", "mist", "mist_intensity",
        "mist_depth", "mist_height", "mist_density", "earthquake_scale", "earthquake_camera"})
    bools = ["rain", "ripples", "droplets", "clouds", "lens_flare", "mist", "splash", "aura",
             "lightning", "earthquake"]
    expect = [(i[len("WEATHER_"):].lower(), v) for _c, _p, i, v in CASES]
    text.from_string("NAMES = %r\nBOOLS = %r\nEXPECT = %r\n" % (names, bools, expect) + CHECK)
    bpy.ops.logic.sensor_add(type='DELAY', name="check")
    s = ob.game.sensors[-1]
    s.delay = 30
    bpy.ops.logic.controller_add(type='PYTHON', name="check")
    c = ob.game.controllers[-1]
    c.text = text
    s.link(c)
    return ob


def main():
    ob = build()
    bricks = os.path.join(HERE, "weather_logic_test.range")
    bpy.ops.wm.save_as_mainfile(filepath=bricks)

    # Mesmos bricks -> Python Component (o check em Python continua como brick).
    bpy.context.scene.objects.active = ob
    ret = bpy.ops.logic.convert_to_component(mode='COMPONENT', disable_originals=True)
    print("CONVERT", ret)
    for t in bpy.data.texts:
        if t.name.endswith("_logic.py"):
            print("----", t.name)
            print(t.as_string())
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "weather_logic_test_python.range"))


main()
