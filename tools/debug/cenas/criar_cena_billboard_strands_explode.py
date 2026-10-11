# Cena de validacao headless (branch shader-nodes) dos nos novos de vertex/geometry: Billboard,
# Strands e Explode (ver docs/shader-nodes.md). Confirma que os tipos existem em bpy.types com os
# sockets certos, que dao pra criar/ligar no Material Output e que o .range salvo roda sem crash
# no AnastacioRuntime (sem checagem visual, so sobrevivencia + screenshot pra inspecao manual).
# Uso: AnastacioEngine.exe -b --factory-startup --python criar_cena_billboard_strands_explode.py -- saida.range shot.png evidencia.txt
# Objetos:
#   BillboardCard - plano fino com o no Billboard ligado ao Vertex Offset do Material Output.
#   Grama         - plano com o no Strands (geometry stage) + Shell Layer lendo o Tip Factor.
#   Destroco      - cubo com o no Explode (geometry stage).
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
world.horizon_color = (0.05, 0.05, 0.08)
scene.world = world


def node_material(name):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    tree = mat.node_tree
    for n in list(tree.nodes):
        tree.nodes.remove(n)
    out = tree.nodes.new("ShaderNodeOutputMaterial")
    out.location = (600, 0)
    bsdf = tree.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (300, 0)
    tree.links.new(bsdf.outputs[0], out.inputs["Surface"])
    return mat, tree, out, bsdf


def mesh(op, name, loc, mat, **kw):
    op(location=loc, **kw)
    ob = bpy.context.active_object
    ob.name = name
    ob.data.materials.append(mat)
    return ob


checks = {}

# --- Billboard: vertex node feeding Material Output "Vertex Offset"
mat, tree, out, bsdf = node_material("MatBillboard")
billboard = tree.nodes.new("ShaderNodeBillboard")
billboard.location = (0, 250)
checks["BILLBOARD_INPUTS"] = [s.identifier for s in billboard.inputs]
checks["BILLBOARD_OUTPUTS"] = [s.identifier for s in billboard.outputs]
billboard.inputs["Lock Axis"].default_value = 1.0
billboard.inputs["Scale"].default_value = 1.0
tree.links.new(billboard.outputs["Offset"], out.inputs["Vertex Offset"])
mesh(bpy.ops.mesh.primitive_plane_add, "BillboardCard", (-4, 0, 1.0), mat, radius=0.5)

# --- Strands: geometry node, Tip Factor reused via the existing Shell Layer "Layer" output
mat, tree, out, bsdf = node_material("MatStrands")
strands = tree.nodes.new("ShaderNodeStrands")
strands.location = (0, 250)
checks["STRANDS_INPUTS"] = [s.identifier for s in strands.inputs]
checks["STRANDS_OUTPUTS"] = [s.identifier for s in strands.outputs]
strands.inputs["Density"].default_value = 6.0
strands.inputs["Length"].default_value = 0.2
strands.inputs["Curvature"].default_value = 0.5
tree.links.new(strands.outputs["Tip Factor"], bsdf.inputs["Base Color"])
mesh(bpy.ops.mesh.primitive_plane_add, "Grama", (0, 0, 0), mat, radius=1.0)

# --- Explode: geometry node, Amount just passes Factor through
mat, tree, out, bsdf = node_material("MatExplode")
explode = tree.nodes.new("ShaderNodeExplode")
explode.location = (0, 250)
checks["EXPLODE_INPUTS"] = [s.identifier for s in explode.inputs]
checks["EXPLODE_OUTPUTS"] = [s.identifier for s in explode.outputs]
explode.inputs["Factor"].default_value = 0.4
tree.links.new(explode.outputs["Amount"], bsdf.inputs["Metallic"])
mesh(bpy.ops.mesh.primitive_cube_add, "Destroco", (4, 0, 1.0), mat)

# Light + camera
lamp = bpy.data.lamps.new("Sun", 'SUN')
sun = bpy.data.objects.new("Sun", lamp)
scene.objects.link(sun)
sun.rotation_euler = (0.8, 0.2, 0.6)
cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
cam.data.lens = 28
scene.objects.link(cam)
cam.location = (0, -10, 4)
cam.rotation_euler = (Vector((0, 0, 1.0)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
scene.camera = cam

logic = bpy.data.texts.new("probe.py")
logic.from_string("""import bge

def tick(cont):
    own = cont.owner
    own['t'] = own.get('t', 0) + 1
    t = own['t']
    if t == 60:
        bge.render.makeScreenshot(%r)
    if t == 65:
        with open(%r, 'w') as f:
            f.write('frames_ok=%%d\\n' %% t)
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
for k in sorted(checks):
    print("CHECK", k, checks[k])
