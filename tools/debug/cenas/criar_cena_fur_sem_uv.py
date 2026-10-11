# Teste do preset Fur/Grass: recorte (Alpha) ligado sozinho pelo operador e malha sem UV.
# Esquerda: esfera SEM UV. Direita: esfera COM UV. As duas devem mostrar fios separados.
# Uso: AnastacioEngine.exe -b --factory-startup --python criar_cena_fur_sem_uv.py -- saida.range [captura.png]
import sys
import bpy
from bl_operators.node import shader_preset_group, NODE_OT_shader_preset_add

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


def fur_material(name, preset):
    """Same steps as Add > Presets in the Node Editor, without the editor context."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    tree = mat.node_tree
    for n in list(tree.nodes):
        tree.nodes.remove(n)
    out = tree.nodes.new("ShaderNodeOutputMaterial")
    out.location = (400, 0)
    bsdf = tree.nodes.new("ShaderNodeBsdfPrincipled")
    tree.links.new(bsdf.outputs[0], out.inputs["Surface"])
    node = tree.nodes.new("ShaderNodeGroup")
    node.node_tree = shader_preset_group(preset)
    node.location = (-300, 0)
    mat.game_settings.alpha_blend = 'CLIP'
    NODE_OT_shader_preset_add.link_alpha(tree, node)
    return mat


bpy.ops.mesh.primitive_uv_sphere_add(location=(-1.6, 0, 1.2))
a = bpy.context.active_object
a.name = "SemUV"
bpy.ops.object.shade_smooth()
a.data.materials.append(fur_material("FurSemUV", 'FUR'))
print("UV_LAYERS_SEM", len(a.data.uv_layers))

bpy.ops.mesh.primitive_uv_sphere_add(location=(1.6, 0, 1.2))
b = bpy.context.active_object
b.name = "ComUV"
bpy.ops.object.shade_smooth()
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project()
bpy.ops.object.mode_set(mode='OBJECT')
b.data.materials.append(fur_material("FurComUV", 'FUR'))
print("UV_LAYERS_COM", len(b.data.uv_layers))

bpy.ops.mesh.primitive_plane_add(location=(0, 0, 0), radius=5)
g = bpy.context.active_object
g.name = "ChaoSemUV"
g.data.materials.append(fur_material("GrassSemUV", 'GRASS'))

lamp = bpy.data.lamps.new("Sun", 'SUN')
sun = bpy.data.objects.new("Sun", lamp)
scene.objects.link(sun)
sun.rotation_euler = (0.8, 0.2, 0.6)
cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
scene.objects.link(cam)
cam.location = (0, -7, 3)
cam.rotation_euler = (1.25, 0, 0)
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
print("FUR_OK")
