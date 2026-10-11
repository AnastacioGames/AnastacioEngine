# Teste do campo Geometry (Material.geomcode) nos dois modos.
# Esquerda: `void geometry()` (modo normal) afasta as faces do cubo.
# Centro: `void main()` com layout proprio (modo livre) poe uma piramide em cada face.
# Direita: `void main()` sem nenhum layout (usa os padroes) encolhe cada triangulo.
# Uso: AnastacioEngine.exe -b --factory-startup --python criar_cena_geometry_livre.py -- saida.range [captura.png]
import sys
import bpy

argv = sys.argv[sys.argv.index("--") + 1:]
out_path = argv[0]
shot_path = argv[1].replace("\\", "/") if len(argv) > 1 else ""

scene = bpy.context.scene
for ob in list(scene.objects):
    scene.objects.unlink(ob)
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.use_shading_nodes = True
world = bpy.data.worlds.new("World")
world.horizon_color = (0.3, 0.35, 0.45)
scene.world = world

GEOMETRY = """\
void geometry()
{
	vec3 n = normalize(cross(geom_position(1) - geom_position(0), geom_position(2) - geom_position(0)));
	for (int i = 0; i < 3; i++) geom_emit_offset(i, n * 0.25);
	EndPrimitive();
}
"""

# Modo livre: o Text tem o proprio main() e os proprios layouts. As entradas vs_* (uma por varying do
# vertex), as saidas de mesmo nome sem o prefixo e os helpers geom_* continuam disponiveis.
MAIN_LAYOUT = """\
layout(triangles) in;
layout(triangle_strip, max_vertices = 12) out;

void main()
{
	vec3 a = vs_varposition[0], b = vs_varposition[1], c = vs_varposition[2];
	vec3 n = normalize(cross(b - a, c - a));
	vec3 tip = (a + b + c) / 3.0 + n * (0.45 + 0.15 * sin(TIME * 2.0));

	/* a face original */
	for (int i = 0; i < 3; i++) geom_emit(i);
	EndPrimitive();

	/* tres lados de uma piramide, com a normal de cada lado */
	for (int i = 0; i < 3; i++) {
		int j = (i + 1) % 3;
		vec3 side = normalize(cross(vs_varposition[j] - vs_varposition[i], tip - vs_varposition[i]));
		geom_copy(i); varnormal = side; EmitVertex();
		geom_copy(j); varnormal = side; EmitVertex();
		geom_copy(i); varnormal = side; geom_set_position(tip); EmitVertex();
		EndPrimitive();
	}
}
"""

MAIN_DEFAULTS = """\
void main()
{
	vec3 center = (vs_varposition[0] + vs_varposition[1] + vs_varposition[2]) / 3.0;
	for (int i = 0; i < 3; i++) {
		geom_copy(i);
		geom_set_position(mix(center, vs_varposition[i], 0.7));
		EmitVertex();
	}
	EndPrimitive();
}
"""


def geom_object(name, text_name, code, color, location, add):
    text = bpy.data.texts.new(text_name)
    text.from_string(code)
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    tree = mat.node_tree
    for n in list(tree.nodes):
        tree.nodes.remove(n)
    out = tree.nodes.new("ShaderNodeOutputMaterial")
    out.location = (300, 0)
    bsdf = tree.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = color
    tree.links.new(bsdf.outputs[0], out.inputs["Surface"])
    mat.script_geom = text
    add(location=location)
    ob = bpy.context.active_object
    ob.name = name
    ob.data.materials.append(mat)
    return ob


geom_object("Geometry", "geometry.glsl", GEOMETRY, (0.9, 0.7, 0.1, 1.0), (-3.2, 0, 1.2),
            bpy.ops.mesh.primitive_cube_add)
geom_object("MainLayout", "main_layout.glsl", MAIN_LAYOUT, (0.2, 0.6, 0.9, 1.0), (0, 0, 1.2),
            bpy.ops.mesh.primitive_cube_add)
geom_object("MainDefaults", "main_defaults.glsl", MAIN_DEFAULTS, (0.9, 0.3, 0.3, 1.0), (3.2, 0, 1.2),
            bpy.ops.mesh.primitive_ico_sphere_add)

lamp = bpy.data.lamps.new("Sun", 'SUN')
sun = bpy.data.objects.new("Sun", lamp)
scene.objects.link(sun)
sun.rotation_euler = (0.8, 0.2, 0.6)
cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
scene.objects.link(cam)
cam.location = (0, -9, 4.5)
cam.rotation_euler = (1.2, 0, 0)
scene.camera = cam

logic = bpy.data.texts.new("probe.py")
logic.from_string("import bge\n"
                  "SHOT = %r\n"
                  "def tick(cont):\n"
                  "    own = cont.owner\n"
                  "    own['t'] = own.get('t', 0) + 1\n"
                  "    if SHOT and own['t'] == 60:\n"
                  "        bge.render.makeScreenshot(SHOT)\n"
                  "    if SHOT and own['t'] == 70:\n"
                  "        bge.logic.endGame()\n" % shot_path)
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
print("GEOMETRY_LIVRE_OK")
