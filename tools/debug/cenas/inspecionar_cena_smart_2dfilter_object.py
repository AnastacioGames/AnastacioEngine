# Inspecao em background da cena criada por criar_cena_smart_2dfilter_object.py.
import sys
import bpy

argv = sys.argv[sys.argv.index("--") + 1:]
out_path = argv[0]
scene = bpy.context.scene
camera = bpy.data.objects.get("ObjectUniformCamera")
target = bpy.data.objects.get("ObjectUniformTarget")
if camera is None or target is None or scene.camera != camera:
    raise RuntimeError("camera or ObjectUniformTarget is missing")

actuator = camera.game.actuators.get("Object Uniform Filter")
if actuator is None or actuator.type != 'FILTER_2D' or actuator.mode != 'CUSTOMFILTER':
    raise RuntimeError("Object uniform filter actuator is missing")
if actuator.filter_pass != 6 or actuator.glsl_shader is None:
    raise RuntimeError("Object uniform filter configuration changed")

source = actuator.glsl_shader.as_string()
if "uniform vec4 u_target; // @object" not in source:
    raise RuntimeError("@object uniform annotation missing")
if "uniform vec3 u_plain_vector; // permanece nao editavel sem @object" not in source:
    raise RuntimeError("plain vector regression fixture missing")
if "u_target.w * smoothstep" not in source:
    raise RuntimeError("shader no longer makes object visibility affect the glow")

prop = camera.game.properties.get("u_target")
if prop is None or prop.type != 'STRING' or prop.value != target.name:
    raise RuntimeError("object property must name the target")

controller = next((item for item in target.game.controllers
                   if getattr(item, "module", "") == 'smart_2dfilter_object_motion.tick'), None)
motion = bpy.data.texts.get("smart_2dfilter_object_motion.py")
if controller is None or motion is None or "def tick(cont):" not in motion.as_string():
    raise RuntimeError("target motion controller is missing")

with open(out_path, "w") as handle:
    handle.write("scene=%s engine=%s\n" % (scene.name, scene.render.engine))
    handle.write("camera=%s target=%s property=%s:%s\n" %
                 (camera.name, target.name, prop.type, prop.value))
    handle.write("actuator=%s text=%s pass=%d\n" %
                 (actuator.name, actuator.glsl_shader.name, actuator.filter_pass))
    handle.write("motion=%s\n" % controller.module)
