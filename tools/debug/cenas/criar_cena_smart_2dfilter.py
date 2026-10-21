# Cena estrutural do painel Smart 2D Filter.
#
# Uso:
#   AnastacioEngine.exe -b --factory-startup --python criar_cena_smart_2dfilter.py -- saida.range
#
# A cena deixa de proposito propriedades ausentes e uma com tipo errado: o painel deve
# oferecer '+' / 'Create Missing', sem alterar nenhuma delas durante o redraw.
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

world = bpy.data.worlds.new("Smart Filter World")
world.horizon_color = (0.05, 0.08, 0.13)
world.mist_settings.use_mist = False
scene.world = world

code = '''// Painel Smart 2D Filter: os valores escolhidos verificam tipos, defaults e Choice.
uniform sampler2D bgl_RenderedTexture;
uniform float u_existing; // @min 0 @max 2 @default 0.5
uniform float u_missing; // @min 0 @max 4 @default 1.25
uniform int u_mode; // @choice Linear=2, Smooth=7, Step=12 @default 7
uniform bool u_enabled; // @default 1
uniform float u_wrong; // @min 0 @max 1 @default 0.25
uniform vec3 u_tint; // deve aparecer como nao editavel

in vec2 texCoordVarying;
out vec4 fragColor;
void main()
{
    vec4 color = texture(bgl_RenderedTexture, texCoordVarying);
    float mode = (u_mode == 2) ? 0.25 : ((u_mode == 7) ? 0.6 : 1.0);
    float enabled = u_enabled ? 1.0 : 0.0;
    fragColor = vec4(color.rgb * (u_existing + u_missing * 0.0 + mode * 0.0 + enabled * 0.0), color.a);
}
'''
text = bpy.data.texts.new("smart_2dfilter_panel.glsl")
text.from_string(code)


def game_property(obj, name, kind, value):
    scene.objects.active = obj
    obj.select = True
    bpy.ops.object.game_property_new(type=kind)
    prop = obj.game.properties[-1]
    prop.name = name
    prop.value = value
    return prop


# A camera tambem e o objeto que possui o actuator: assim a cena pode ser aberta
# diretamente no Logic Editor sem procurar um objeto auxiliar.
bpy.ops.object.camera_add(location=(0.0, -10.0, 4.5))
camera = bpy.context.object
camera.name = "SmartFilterCamera"
camera.data.lens = 32
camera.rotation_euler = (Vector((0.0, 0.0, 1.0)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
scene.camera = camera

# Existente correto, ausentes que o operador deve criar, e tipo errado que ele nao pode converter.
game_property(camera, "u_existing", 'FLOAT', 0.75)
game_property(camera, "u_wrong", 'STRING', "keep-me")

bpy.ops.logic.sensor_add(type='ALWAYS', object=camera.name)
sensor = camera.game.sensors[-1]
bpy.ops.logic.controller_add(type='LOGIC_AND', object=camera.name)
controller = camera.game.controllers[-1]
bpy.ops.logic.actuator_add(type='FILTER_2D', object=camera.name)
actuator = camera.game.actuators[-1]
actuator.name = "Smart 2D Filter"
actuator.mode = 'CUSTOMFILTER'
actuator.filter_pass = 5
actuator.glsl_shader = text
sensor.link(controller)
actuator.link(controller)

# Geometria simples e contrastante para o teste visual posterior.
for index, color in enumerate(((0.9, 0.18, 0.05), (0.05, 0.65, 0.95), (0.25, 0.95, 0.35))):
    bpy.ops.mesh.primitive_cube_add(location=(index * 2.6 - 2.6, 0.0, 1.0))
    cube = bpy.context.object
    cube.name = "SmartFilterCube%d" % index
    mat = bpy.data.materials.new("SmartFilterMat%d" % index)
    mat.diffuse_color = color
    cube.data.materials.append(mat)

bpy.ops.mesh.primitive_plane_add(location=(0.0, 0.0, 0.0))
ground = bpy.context.object
ground.name = "SmartFilterGround"
ground.scale = (6.5, 4.0, 1.0)
ground_mat = bpy.data.materials.new("SmartFilterGroundMat")
ground_mat.diffuse_color = (0.12, 0.14, 0.18)
ground.data.materials.append(ground_mat)

lamp_data = bpy.data.lamps.new("SmartFilterSun", 'SUN')
lamp_data.energy = 1.5
lamp = bpy.data.objects.new("SmartFilterSun", lamp_data)
scene.objects.link(lamp)
lamp.rotation_euler = (0.55, -0.35, 0.45)

bpy.ops.wm.save_as_mainfile(filepath=out_path)
print("SMART_2DFILTER_SCENE", out_path, camera.name, actuator.glsl_shader.name)
