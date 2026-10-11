# Cena de teste do no GLSL Script: funcoes auxiliares, uniforms "u_" e TIME (branch shader-nodes).
# Uso: AnastacioEngine.exe -b --factory-startup --python criar_cena_glsl_script_uniforms.py -- saida.range shot.png evidencia.txt
# Rodar: AnastacioRuntime.exe -w 1280 720 saida.range (tira o print no quadro 90 e fecha).
# Objetos:
#   Helpers  - cubo com DOIS nos GLSL Script no mesmo material; os dois Texts declaram pattern(), SCALE e TINT.
#   Padrao   - esfera com uniforms no valor do @default (verde, 4 listras).
#   Python   - esfera com o mesmo Text, uniforms trocados pelo jogo (magenta, 10 listras).
#   Onda     - grade com GLSL Script no Vertex Offset (helper pattern(), TIME e u_height trocado pelo jogo).
import sys
import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
out_path = argv[0]
shot = argv[1].replace("\\", "/")
evidence = argv[2].replace("\\", "/")

scene = bpy.context.scene
for ob in list(scene.objects):
    scene.objects.unlink(ob)
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.use_shading_nodes = True

world = bpy.data.worlds.new("World")
world.horizon_color = (0.25, 0.3, 0.4)
world.mist_settings.use_mist = False
scene.world = world


def node_material(name):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    tree = mat.node_tree
    for n in list(tree.nodes):
        tree.nodes.remove(n)
    out = tree.nodes.new("ShaderNodeOutputMaterial")
    out.location = (500, 0)
    bsdf = tree.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (250, 0)
    tree.links.new(bsdf.outputs[0], out.inputs["Surface"])
    coord = tree.nodes.new("ShaderNodeTexCoord")
    coord.location = (-500, 0)
    return mat, tree, out, bsdf, coord


def script_node(tree, text, loc):
    node = tree.nodes.new("ShaderNodeGLSLScript")
    node.script = text
    node.location = loc
    node.update()
    tree.update_tag()
    return node


def text(name, code):
    txt = bpy.data.texts.new(name)
    txt.from_string(code)
    return txt


def mesh(op, name, loc, mat, **kw):
    op(location=loc, **kw)
    ob = bpy.context.active_object
    ob.name = name
    ob.data.materials.append(mat)
    return ob


# --- Two scripts with the same helper names in one material
checker = text("checker.glsl", """// Xadrez: mesmos nomes de helper que rings.glsl
#define TINT vec4(1.0, 0.85, 0.2, 1.0)
const float SCALE = 2.0;

float pattern(vec3 p)
{
	vec3 c = floor(p * SCALE + 0.001);
	return mod(c.x + c.y + c.z, 2.0);
}

void main(vec3 Vector, out vec4 Color)
{
	Color = mix(vec4(0.05, 0.05, 0.05, 1.0), TINT, pattern(Vector));
}
""")
rings = text("rings.glsl", """// Aneis: mesmos nomes de helper que checker.glsl
#define TINT vec4(0.1, 0.4, 1.0, 1.0)
const float SCALE = 9.0;
struct Ring { float width; };

float pattern(vec3 p)
{
	Ring ring = Ring(0.35);
	return step(1.0 - ring.width, fract(length(p.xy) * SCALE * 0.5));
}

void main(vec4 Base, vec3 Vector, out vec4 Color)
{
	Color = mix(Base, TINT, pattern(Vector));
}
""")
mat, tree, out, bsdf, coord = node_material("Helpers")
a = script_node(tree, checker, (-250, 100))
b = script_node(tree, rings, (0, 0))
tree.links.new(coord.outputs["Object"], a.inputs["Vector"])
tree.links.new(coord.outputs["Object"], b.inputs["Vector"])
tree.links.new(a.outputs["Color"], b.inputs["Base"])
tree.links.new(b.outputs["Color"], bsdf.inputs["Base Color"])
mesh(bpy.ops.mesh.primitive_cube_add, "Helpers", (-3.2, 0, 1.2), mat)

# --- Uniforms: one Text, two materials; the game changes only the second
stripes = text("stripes.glsl", """uniform vec4 u_color;     // @default 0.1 0.8 0.2 1
uniform float u_stripes;  // @min 1 @max 20 @default 4
uniform int u_invert;     // @min 0 @max 1
uniform vec2 u_shift;

float band(float v)
{
	return step(0.5, fract(v * u_stripes + u_shift.x));
}

void main(vec3 Vector, out vec4 Color)
{
	float f = band(Vector.z * 0.5 + 0.5);
	if (u_invert == 1) f = 1.0 - f;
	Color = mix(vec4(1.0), u_color, f);
}
""")
uniform_nodes = []
for name, x in (("Padrao", 0.0), ("Python", 3.2)):
    mat, tree, out, bsdf, coord = node_material(name)
    n = script_node(tree, stripes, (0, 0))
    tree.links.new(coord.outputs["Object"], n.inputs["Vector"])
    tree.links.new(n.outputs["Color"], bsdf.inputs["Base Color"])
    mesh(bpy.ops.mesh.primitive_uv_sphere_add, name, (x, 0, 1.2), mat, segments=48, ring_count=24)
    bpy.ops.object.shade_smooth()
    uniform_nodes.append(n)

# --- Vertex stage: helper + TIME + uniform
wave = text("wave.glsl", """uniform float u_height;  // @min 0 @max 2 @default 0.1

float pattern(vec3 p)
{
	return sin(p.x * 3.0 + TIME * 2.0) * cos(p.y * 3.0);
}

void main(vec3 Position, out vec3 Offset, out vec4 Color)
{
	float h = pattern(Position);
	Offset = vec3(0.0, 0.0, h * u_height);
	Color = mix(vec4(0.05, 0.2, 0.5, 1.0), vec4(0.6, 0.9, 1.0, 1.0), h * 0.5 + 0.5);
}
""")
mat, tree, out, bsdf, coord = node_material("Onda")
n = script_node(tree, wave, (0, 0))
tree.links.new(coord.outputs["Object"], n.inputs["Position"])
tree.links.new(n.outputs["Offset"], out.inputs["Vertex Offset"])
tree.links.new(n.outputs["Color"], bsdf.inputs["Base Color"])
mesh(bpy.ops.mesh.primitive_grid_add, "Onda", (0, 0, 0), mat, x_subdivisions=80, y_subdivisions=80, radius=7)

# Light + camera
lamp = bpy.data.lamps.new("Sun", 'SUN')
sun = bpy.data.objects.new("Sun", lamp)
scene.objects.link(sun)
sun.rotation_euler = (0.8, 0.2, 0.6)
cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
cam.data.lens = 22
scene.objects.link(cam)
cam.location = (0, -9, 5)
cam.rotation_euler = (Vector((0, 0, 0.8)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
scene.camera = cam

logic = bpy.data.texts.new("probe.py")
logic.from_string("""import bge

def material(scene, obname):
    return scene.objects[obname].meshes[0].materials[0]

def tick(cont):
    own = cont.owner
    scene = bge.logic.getCurrentScene()
    own['t'] = own.get('t', 0) + 1
    t = own['t']
    mat = material(scene, 'Python')
    if t == 20:
        own['before'] = repr((mat.getScriptUniform('u_color'), mat.getScriptUniform('u_stripes')))
    if t >= 20:
        # Every frame: the value reaches the GPU without compiling again.
        k = min((t - 20) / 40.0, 1.0)
        own['ok'] = repr((mat.setScriptUniform('u_color', (0.1 + 0.8 * k, 0.8 - 0.7 * k, 0.2 + 0.7 * k, 1.0)),
                          mat.setScriptUniform('u_stripes', 4.0 + 6.0 * k),
                          mat.setScriptUniform('u_missing', 1.0),
                          material(scene, 'Onda').setScriptUniform('u_height', 0.1 + 0.5 * k)))
    if t == 90:
        bge.render.makeScreenshot(%r)
    if t == 95:
        with open(%r, 'w') as f:
            f.write('before=%%s\\nset=%%s\\nafter=%%r\\ndefault_material=%%r\\n' %% (
                own['before'], own['ok'],
                (mat.getScriptUniform('u_color'), mat.getScriptUniform('u_stripes'), mat.getScriptUniform('u_shift')),
                material(scene, 'Padrao').getScriptUniform('u_color')))
        bge.logic.endGame()
""" % (shot, evidence))
scene.objects.active = cam
bpy.ops.logic.sensor_add(type='ALWAYS', object=cam.name)
bpy.ops.logic.controller_add(type='PYTHON', object=cam.name)
s = cam.game.sensors[-1]
s.use_pulse_true_level = True
c = cam.game.controllers[-1]
c.mode = 'MODULE'
c.module = 'probe.tick'
s.link(c)

bpy.ops.wm.save_as_mainfile(filepath=out_path)
for node in [a, b] + uniform_nodes[:1] + [n]:
    print("SCRIPT_SOCKETS", node.script.name, [(s.identifier, s.bl_idname) for s in node.inputs],
          [s.identifier for s in node.outputs])
u = uniform_nodes[0].inputs
print("UNIFORM_VALUES", tuple(u["u_color"].default_value), u["u_stripes"].default_value,
      u["u_invert"].default_value, tuple(u["u_shift"].default_value))
