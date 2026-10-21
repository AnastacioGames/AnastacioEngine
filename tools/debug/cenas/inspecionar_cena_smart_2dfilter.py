# Inspecao em background da cena criada por criar_cena_smart_2dfilter.py.
# Uso: AnastacioEngine.exe -b cena.range --python inspecionar_cena_smart_2dfilter.py -- evidencia.txt
import sys
import bpy

argv = sys.argv[sys.argv.index("--") + 1:]
out_path = argv[0]
scene = bpy.context.scene
camera = bpy.data.objects.get("SmartFilterCamera")
if camera is None or scene.camera != camera:
    raise RuntimeError("SmartFilterCamera is missing or inactive")

actuator = camera.game.actuators.get("Smart 2D Filter")
if actuator is None or actuator.type != 'FILTER_2D' or actuator.mode != 'CUSTOMFILTER':
    raise RuntimeError("Custom Filter actuator is missing")
if actuator.filter_pass != 5 or actuator.glsl_shader is None:
    raise RuntimeError("Custom Filter actuator configuration changed")

text = actuator.glsl_shader
required = (
    "uniform float u_existing; // @min 0 @max 2 @default 0.5",
    "uniform float u_missing; // @min 0 @max 4 @default 1.25",
    "uniform int u_mode; // @choice Linear=2, Smooth=7, Step=12 @default 7",
    "uniform bool u_enabled; // @default 1",
    "uniform float u_wrong; // @min 0 @max 1 @default 0.25",
    "uniform vec3 u_tint; // deve aparecer como nao editavel",
)
source = text.as_string()
for line in required:
    if line not in source:
        raise RuntimeError("annotation missing: %s" % line)

props = camera.game.properties
existing = props.get("u_existing")
wrong = props.get("u_wrong")
if existing is None or existing.type != 'FLOAT' or abs(existing.value - 0.75) > 0.0001:
    raise RuntimeError("existing float property changed")
if wrong is None or wrong.type != 'STRING' or wrong.value != "keep-me":
    raise RuntimeError("wrong-type property changed")
for name in ("u_missing", "u_mode", "u_enabled", "u_tint"):
    if props.get(name) is not None:
        raise RuntimeError("property must stay absent before Create Missing: %s" % name)

with open(out_path, "w") as handle:
    handle.write("scene=%s engine=%s\n" % (scene.name, scene.render.engine))
    handle.write("camera=%s actuator=%s text=%s pass=%d\n" %
                 (camera.name, actuator.name, text.name, actuator.filter_pass))
    handle.write("existing=%s:%s wrong=%s:%s\n" %
                 (existing.type, existing.value, wrong.type, wrong.value))
    handle.write("missing=u_missing,u_mode,u_enabled,u_tint\n")
