# Cena combinada de validacao headless (branch shader-nodes): junta tudo que foi acumulado e
# ainda nao teve confirmacao visual do usuario -- Billboard, Strands, Explode, Fur Shells
# (classico + Direction) e Planar Reflection -- numa unica cena/.range, pra um teste so.
# Confirma que todos os tipos existem em bpy.types com os sockets certos, que dao pra
# criar/ligar nos materiais e que o .range salvo roda sem crash no AnastacioRuntime
# (sobrevivencia + screenshot pra inspecao manual; NAO confirma visualmente o resultado de
# cada efeito, so que a cena toda convive sem conflito).
# Uso: AnastacioEngine.exe -b --factory-startup --python criar_cena_tudo_junto.py -- saida.range shot.png evidencia.txt
#      (shot.png em caminho absoluto: com caminho relativo o screenshot nao aparece na pasta atual)
# Objetos (da esquerda pra direita, eixo X):
#   BillboardCard - plano fino com o no Billboard no Vertex Offset.
#   Grama         - plano com o no Strands (geometry stage).
#   FurNormal     - esfera com Fur Shells classico (Direction Strength 0).
#   FurDirecao    - esfera com Fur Shells + Direction (vento) e Direction Strength 1.
#   Destroco      - cubo com o no Explode (geometry stage).
#   Espelho       - plano horizontal com Planar Reflection (Enable=True), refletindo o Cubo acima.
#   Cubo          - cubo colorido acima do Espelho, o que deveria aparecer refletido.
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

# --- Billboard
mat, tree, out, bsdf = node_material("MatBillboard")
billboard = tree.nodes.new("ShaderNodeBillboard")
billboard.location = (0, 250)
checks["BILLBOARD_INPUTS"] = [s.identifier for s in billboard.inputs]
checks["BILLBOARD_OUTPUTS"] = [s.identifier for s in billboard.outputs]
billboard.inputs["Lock Axis"].default_value = 1.0
billboard.inputs["Scale"].default_value = 1.0
tree.links.new(billboard.outputs["Offset"], out.inputs["Vertex Offset"])
mesh(bpy.ops.mesh.primitive_plane_add, "BillboardCard", (-12, 0, 1.0), mat, radius=0.5)

# --- Strands
mat, tree, out, bsdf = node_material("MatStrands")
strands = tree.nodes.new("ShaderNodeStrands")
strands.location = (0, 250)
checks["STRANDS_INPUTS"] = [s.identifier for s in strands.inputs]
checks["STRANDS_OUTPUTS"] = [s.identifier for s in strands.outputs]
strands.inputs["Density"].default_value = 6.0
strands.inputs["Length"].default_value = 0.2
strands.inputs["Curvature"].default_value = 0.5
tree.links.new(strands.outputs["Tip Factor"], bsdf.inputs["Base Color"])
mesh(bpy.ops.mesh.primitive_plane_add, "Grama", (-8, 0, 0), mat, radius=1.0)


def make_fur(name, loc, direction, strength):
    mat, tree, out, bsdf = node_material(name)
    mat.game_settings.alpha_blend = 'CLIP'
    fur = tree.nodes.new("ShaderNodeFurShells")
    fur.location = (0, 250)
    checks["%s_INPUTS" % name] = [s.identifier for s in fur.inputs]
    checks["%s_OUTPUTS" % name] = [s.identifier for s in fur.outputs]
    fur.inputs["Length"].default_value = 0.25
    fur.inputs["Layers"].default_value = 10.0
    fur.inputs["Density"].default_value = 180.0
    fur.inputs["Direction"].default_value = direction
    fur.inputs["Direction Strength"].default_value = strength
    tree.links.new(fur.outputs["Alpha"], bsdf.inputs["Base Color"])
    ob = mesh(bpy.ops.mesh.primitive_uv_sphere_add, name, loc, mat)
    bpy.ops.object.shade_smooth()
    return ob


# --- Fur Shells: classico (retrocompatibilidade) + Direction (vento)
make_fur("FurNormal", (-4, 0, 1.2), (0.0, 0.0, 0.0), 0.0)
make_fur("FurDirecao", (0, 0, 1.2), (1.0, 0.0, 0.0), 1.0)

# --- Explode
mat, tree, out, bsdf = node_material("MatExplode")
explode = tree.nodes.new("ShaderNodeExplode")
explode.location = (0, 250)
checks["EXPLODE_INPUTS"] = [s.identifier for s in explode.inputs]
checks["EXPLODE_OUTPUTS"] = [s.identifier for s in explode.outputs]
explode.inputs["Factor"].default_value = 0.4
tree.links.new(explode.outputs["Amount"], bsdf.inputs["Metallic"])
mesh(bpy.ops.mesh.primitive_cube_add, "Destroco", (4, 0, 1.0), mat)

# --- Planar Reflection: Espelho (plano horizontal) + Cubo refletido acima
mat, tree, out, bsdf = node_material("MatEspelho")
planar = tree.nodes.new("ShaderNodePlanarReflection")
planar.location = (0, 250)
checks["PLANAR_REFLECTION_INPUTS"] = [s.identifier for s in planar.inputs]
checks["PLANAR_REFLECTION_OUTPUTS"] = [s.identifier for s in planar.outputs]
planar.inputs["Enable"].default_value = True
planar.inputs["Resolution"].default_value = 1024
planar.inputs["Clip End"].default_value = 50.0
# Emission, nao Base Color: pelo BSDF o reflexo seria iluminado de novo pelas luzes da cena.
tree.nodes.remove(bsdf)
emission = tree.nodes.new("ShaderNodeEmission")
emission.location = (300, 0)
emission.inputs["Strength"].default_value = 1.0
tree.links.new(planar.outputs["Color"], emission.inputs["Color"])
tree.links.new(emission.outputs[0], out.inputs["Surface"])
mesh(bpy.ops.mesh.primitive_plane_add, "Espelho", (9, 0, 0), mat, radius=3.0)

mat2, tree2, out2, bsdf2 = node_material("MatCuboEspelho")
bsdf2.inputs["Base Color"].default_value = (0.9, 0.2, 0.1, 1.0)
mesh(bpy.ops.mesh.primitive_cube_add, "CuboEspelho", (9, 0, 2.0), mat2)

# Light + camera (afastada pra enquadrar a fila inteira, -12..12 em X)
lamp = bpy.data.lamps.new("Sun", 'SUN')
sun = bpy.data.objects.new("Sun", lamp)
scene.objects.link(sun)
sun.rotation_euler = (0.8, 0.2, 0.6)
cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
cam.data.lens = 18
scene.objects.link(cam)
cam.location = (0, -26, 9)
cam.rotation_euler = (Vector((0, 0, 1.2)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
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
