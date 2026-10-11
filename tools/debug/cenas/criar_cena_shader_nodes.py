# Cena de teste dos estagios de vertex/geometry nos nos de material (branch shader-nodes).
# Uso: AnastacioEngine.exe -b --factory-startup --python criar_cena_shader_nodes.py -- saida.range evidencia.txt
# Objetos: plano com Water Waves (Vertex Offset), esfera com Fur, macaco com Toon Outline,
# cubo com GLSL Script, cubo de referencia sem nos novos e cubo com Material.geomcode.
import sys
import bpy
from mathutils import Vector
from bl_operators.node import shader_preset_group

argv = sys.argv[sys.argv.index("--") + 1:]
out_path = argv[0]
evidence = argv[1].replace("\\", "/")

scene = bpy.context.scene
for ob in list(scene.objects):
    scene.objects.unlink(ob)
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.use_shading_nodes = True

world = bpy.data.worlds.new("World")
world.horizon_color = (0.3, 0.35, 0.45)
world.mist_settings.use_mist = False
scene.world = world


def node_material(name, color):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    tree = mat.node_tree
    for n in list(tree.nodes):
        tree.nodes.remove(n)
    out = tree.nodes.new("ShaderNodeOutputMaterial")
    out.location = (400, 0)
    bsdf = tree.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = color
    tree.links.new(bsdf.outputs[0], out.inputs["Surface"])
    return mat, tree, out, bsdf


def add_group(tree, preset):
    node = tree.nodes.new("ShaderNodeGroup")
    node.node_tree = shader_preset_group(preset)
    node.location = (-300, 0)
    return node


def mesh(op, name, loc, mat, **kw):
    op(location=loc, **kw)
    ob = bpy.context.active_object
    ob.name = name
    ob.data.materials.append(mat)
    return ob


# Water: subdivided plane + Water Waves
mat, tree, out, bsdf = node_material("Water", (0.1, 0.4, 0.6, 1.0))
g = add_group(tree, 'WATER_WAVES')
tree.links.new(g.outputs["Color"], bsdf.inputs["Base Color"])
tree.links.new(g.outputs["Offset"], out.inputs["Vertex Offset"])
mesh(bpy.ops.mesh.primitive_grid_add, "Water", (0, 0, 0), mat, x_subdivisions=60, y_subdivisions=60, radius=6)

# Fur sphere
mat, tree, out, bsdf = node_material("Fur", (0.5, 0.3, 0.2, 1.0))
g = add_group(tree, 'FUR')
tree.links.new(g.outputs["Color"], bsdf.inputs["Base Color"])
mat.game_settings.alpha_blend = 'CLIP'
mesh(bpy.ops.mesh.primitive_uv_sphere_add, "FurBall", (-3, 0, 1.5), mat)

# Toon outline monkey
mat, tree, out, bsdf = node_material("Toon", (0.8, 0.8, 0.8, 1.0))
g = add_group(tree, 'TOON_OUTLINE')
tree.links.new(g.outputs["Color"], bsdf.inputs["Base Color"])
mesh(bpy.ops.mesh.primitive_monkey_add, "Toon", (0, 0, 1.5), mat)

# GLSL Script cube
txt = bpy.data.texts.new("stripes.glsl")
txt.from_string("void main(float Scale, vec3 Vector, out vec4 Color, out float Fac)\n"
                "{\n    Fac = step(0.5, fract(Vector.z * Scale));\n"
                "    Color = mix(vec4(1.0, 0.2, 0.1, 1.0), vec4(1.0), Fac);\n}\n")
mat, tree, out, bsdf = node_material("Script", (1, 1, 1, 1))
script = tree.nodes.new("ShaderNodeGLSLScript")
script.script = txt
try:
    script.update()
except Exception as e:
    print("update()", e)
tree.update_tag()
coord = tree.nodes.new("ShaderNodeTexCoord")
script_ok = "Color" in script.outputs and "Scale" in script.inputs
if script_ok:
    script.inputs["Scale"].default_value = 4.0
    tree.links.new(coord.outputs["Object"], script.inputs["Vector"])
    tree.links.new(script.outputs["Color"], bsdf.inputs["Base Color"])
mesh(bpy.ops.mesh.primitive_cube_add, "ScriptCube", (3, 0, 1.5), mat)

# Reference cube (no new nodes) and cube with user geometry code (extrudes each triangle)
mat, tree, out, bsdf = node_material("Reference", (0.2, 0.8, 0.2, 1.0))
mesh(bpy.ops.mesh.primitive_cube_add, "RefCube", (-3, 3, 1), mat)
geo = bpy.data.texts.new("explode.glsl")
geo.from_string("layout(triangle_strip, max_vertices = 3) out;\n"
                "void geometry()\n{\n"
                "    vec3 n = normalize(cross(geom_position(1) - geom_position(0), geom_position(2) - geom_position(0)));\n"
                "    float k = 0.2 * (sin(TIME * 2.0) * 0.5 + 0.5);\n"
                "    for (int i = 0; i < 3; i++) geom_emit_offset(i, n * k);\n"
                "    EndPrimitive();\n}\n")
mat, tree, out, bsdf = node_material("Explode", (0.9, 0.7, 0.1, 1.0))
mat.script_geom = geo
mesh(bpy.ops.mesh.primitive_cube_add, "GeomCube", (3, 3, 1), mat)

# Light + camera
lamp = bpy.data.lamps.new("Sun", 'SUN')
sun = bpy.data.objects.new("Sun", lamp)
scene.objects.link(sun)
sun.rotation_euler = (0.8, 0.2, 0.6)
cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
cam.data.lens = 16
scene.objects.link(cam)
cam.location = (0, -9, 6)
cam.rotation_euler = (Vector((0, 1, 1)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
scene.camera = cam

# Auto quit after a few seconds, writing evidence
logic = bpy.data.texts.new("probe.py")
logic.from_string("import bge\n"
                  "def tick(cont):\n"
                  "    own = cont.owner\n"
                  "    own['t'] = own.get('t', 0) + 1\n"
                  "    if own['t'] == 300:\n"
                  "        with open(%r, 'w') as f:\n"
                  "            f.write('frames=%%d fps=%%.1f\\n' %% (own['t'], bge.logic.getAverageFrameRate()))\n"
                  "        bge.logic.endGame()\n" % evidence)
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
print("SCRIPT_SOCKETS", script_ok, [s.name for s in script.inputs], [s.name for s in script.outputs])
