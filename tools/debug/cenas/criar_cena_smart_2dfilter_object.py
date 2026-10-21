# Cena visual do uniform @object do Smart 2D Filter.
# Uso: AnastacioEngine.exe -b --factory-startup --python criar_cena_smart_2dfilter_object.py -- saida.range
import sys
import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
out_path = argv[0]
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.resolution_x = 960
scene.game_settings.resolution_y = 540
scene.game_settings.use_frame_rate = False

world = bpy.data.worlds.new("Object Uniform World")
world.horizon_color = (0.025, 0.04, 0.08)
world.mist_settings.use_mist = False
scene.world = world

def game_property(obj, name, kind, value):
    scene.objects.active = obj
    obj.select = True
    bpy.ops.object.game_property_new(type=kind)
    prop = obj.game.properties[-1]
    prop.name = name
    prop.value = value
    return prop

shader = bpy.data.texts.new("smart_2dfilter_object.glsl")
shader.from_string('''// O brilho acompanha o objeto selecionado no painel Smart.
uniform sampler2D bgl_RenderedTexture;
uniform vec4 u_target; // @object
uniform vec3 u_plain_vector; // permanece nao editavel sem @object

in vec2 texCoordVarying;
out vec4 fragColor;
void main()
{
    vec4 color = texture(bgl_RenderedTexture, texCoordVarying);
    float distance_to_target = distance(texCoordVarying, u_target.xy);
    float glow = u_target.w * smoothstep(0.18, 0.015, distance_to_target);
    color.rgb = mix(color.rgb, vec3(1.0, 0.82, 0.12), glow);
    fragColor = color;
}
''')

bpy.ops.object.camera_add(location=(0.0, -11.0, 5.0))
camera = bpy.context.object
camera.name = "ObjectUniformCamera"
camera.data.lens = 30
camera.rotation_euler = (Vector((0.0, 0.0, 1.0)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
scene.camera = camera
game_property(camera, "u_target", 'STRING', "ObjectUniformTarget")

bpy.ops.logic.sensor_add(type='ALWAYS', object=camera.name)
sensor = camera.game.sensors[-1]
bpy.ops.logic.controller_add(type='LOGIC_AND', object=camera.name)
controller = camera.game.controllers[-1]
bpy.ops.logic.actuator_add(type='FILTER_2D', object=camera.name)
actuator = camera.game.actuators[-1]
actuator.name = "Object Uniform Filter"
actuator.mode = 'CUSTOMFILTER'
actuator.filter_pass = 6
actuator.glsl_shader = shader
sensor.link(controller)
actuator.link(controller)

# O alvo se move continuamente para comprovar, numa janela, que o brilho segue a projeção.
bpy.ops.mesh.primitive_cube_add(location=(0.0, 0.0, 1.0))
target = bpy.context.object
target.name = "ObjectUniformTarget"
target_mat = bpy.data.materials.new("ObjectUniformTargetMat")
target_mat.diffuse_color = (0.9, 0.08, 0.04)
target.data.materials.append(target_mat)
motion = bpy.data.texts.new("smart_2dfilter_object_motion.py")
motion.write('''import bge
import math

def tick(cont):
    own = cont.owner
    t = bge.logic.getRealTime()
    own.worldPosition.x = math.sin(t * 0.9) * 3.2
    own.worldPosition.z = 1.0 + math.sin(t * 1.7) * 0.65
''')
bpy.ops.logic.sensor_add(type='ALWAYS', object=target.name)
motion_sensor = target.game.sensors[-1]
motion_sensor.use_pulse_true_level = True
bpy.ops.logic.controller_add(type='PYTHON', object=target.name)
motion_controller = target.game.controllers[-1]
motion_controller.mode = 'MODULE'
motion_controller.module = 'smart_2dfilter_object_motion.tick'
motion_sensor.link(motion_controller)

# Referências frias tornam o halo amarelo e o cubo vermelho fáceis de distinguir.
for x, color in ((-4.0, (0.05, 0.35, 0.9)), (4.0, (0.08, 0.72, 0.28))):
    bpy.ops.mesh.primitive_cube_add(location=(x, 0.0, 1.0))
    marker = bpy.context.object
    marker.name = "ObjectUniformMarker%s" % ("Left" if x < 0 else "Right")
    mat = bpy.data.materials.new(marker.name + "Mat")
    mat.diffuse_color = color
    marker.data.materials.append(mat)

bpy.ops.mesh.primitive_plane_add(location=(0.0, 0.0, 0.0))
ground = bpy.context.object
ground.name = "ObjectUniformGround"
ground.scale = (7.0, 4.0, 1.0)
ground_mat = bpy.data.materials.new("ObjectUniformGroundMat")
ground_mat.diffuse_color = (0.08, 0.1, 0.15)
ground.data.materials.append(ground_mat)

lamp_data = bpy.data.lamps.new("ObjectUniformSun", 'SUN')
lamp_data.energy = 1.6
lamp = bpy.data.objects.new("ObjectUniformSun", lamp_data)
scene.objects.link(lamp)
lamp.rotation_euler = (0.55, -0.35, 0.45)

bpy.ops.wm.save_as_mainfile(filepath=out_path)
print("SMART_2DFILTER_OBJECT_SCENE", out_path, camera.name, target.name)
