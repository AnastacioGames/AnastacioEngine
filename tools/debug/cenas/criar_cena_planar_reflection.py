# Cena de validacao headless (branch shader-nodes) do no Planar Reflection (ver
# docs/shader-nodes.md). Confirma que o tipo existe em bpy.types com os sockets certos, que da
# pra criar/ligar a saida Color num material Principled, que o Enable liga a criacao de um
# KX_PlanarReflector na conversao de cena (objeto proprio como espelho, chao com normal +Z) e que
# o .range salvo roda sem crash no AnastacioRuntime (sem checagem visual, so sobrevivencia +
# screenshot pra inspecao manual).
# Uso: AnastacioEngine.exe -b --factory-startup --python criar_cena_planar_reflection.py -- saida.range shot.png evidencia.txt
# Objetos:
#   Espelho - plano horizontal com o no Planar Reflection (Enable=True) alimentando o Base Color
#             do Principled (reflexo puro, sem Fresnel/Mix, so para confirmar que a textura chega).
#   Cubo    - cubo colorido acima do espelho, o que deveria aparecer refletido.
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

# --- Planar Reflection: fragment node, Color feeds Base Color directly (pure mirror, no blend)
mat, tree, out, bsdf = node_material("MatEspelho")
planar = tree.nodes.new("ShaderNodePlanarReflection")
planar.location = (0, 250)
checks["PLANAR_REFLECTION_INPUTS"] = [s.identifier for s in planar.inputs]
checks["PLANAR_REFLECTION_OUTPUTS"] = [s.identifier for s in planar.outputs]
planar.inputs["Enable"].default_value = True
planar.inputs["Resolution"].default_value = 256
planar.inputs["Clip End"].default_value = 50.0
tree.links.new(planar.outputs["Color"], bsdf.inputs["Base Color"])
espelho = mesh(bpy.ops.mesh.primitive_plane_add, "Espelho", (0, 0, 0), mat, radius=3.0)

# --- Cubo above the mirror, what the reflection should show
mat2, tree2, out2, bsdf2 = node_material("MatCubo")
bsdf2.inputs["Base Color"].default_value = (0.9, 0.2, 0.1, 1.0)
mesh(bpy.ops.mesh.primitive_cube_add, "Cubo", (0, 0, 2.0), mat2)

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
