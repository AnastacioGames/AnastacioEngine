# Bake dos meshmaps numa cena com fendas (Suzanne + peça com encaixes) e grava PNGs para conferir.
# Uso: AnastacioEngine.exe -b --factory-startup -P tools/debug/cenas/medir_meshmap_bake.py -- <pasta_saida>
import bpy, bmesh, sys, os, time
from bl_operators import node_meshmap as nm

out = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "."
os.makedirs(out, exist_ok=True)
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
sc = bpy.context.scene

def finish(ob):
    sc.objects.link(ob); sc.objects.active = ob; ob.select = True
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(island_margin=0.03)
    bpy.ops.object.mode_set(mode='OBJECT')
    ob.select = False
    return ob

# Suzanne subdividida (orelhas, olhos e boca dão fendas).
me = bpy.data.meshes.new("Suzanne"); bm = bmesh.new()
bmesh.ops.create_monkey(bm)
bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=1, use_grid_fill=True, smooth=1.0)
bm.to_mesh(me); bm.free()
for p in me.polygons: p.use_smooth = True
finish(bpy.data.objects.new("Suzanne", me))

# Peça: bloco com degraus extrudados para dentro e para fora.
me = bpy.data.meshes.new("Peca"); bm = bmesh.new()
bmesh.ops.create_cube(bm, size=2.0)
top = [f for f in bm.faces if f.normal.z > 0.9]
r = bmesh.ops.inset_individual(bm, faces=top, thickness=0.3)
bmesh.ops.translate(bm, verts=list(top[0].verts), vec=(0, 0, -0.6))
sides = [f for f in bm.faces if abs(f.normal.x) > 0.9]
bmesh.ops.inset_individual(bm, faces=sides, thickness=0.25)
for f in sides:
    ext = bmesh.ops.extrude_discrete_faces(bm, faces=[f])["faces"][0]
    bmesh.ops.translate(bm, verts=list(ext.verts), vec=ext.normal * 0.4)
bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=2, use_grid_fill=True)
bm.to_mesh(me); bm.free()
finish(bpy.data.objects.new("Peca", me))

# Cubo simples (8 vértices): a curvatura tem de marcar só as quinas.
me = bpy.data.meshes.new("Cubo"); bm = bmesh.new()
bmesh.ops.create_cube(bm, size=2.0); bm.to_mesh(me); bm.free()
finish(bpy.data.objects.new("Cubo", me))

for ob in (sc.objects["Suzanne"], sc.objects["Peca"], sc.objects["Cubo"]):
    for kind in nm.KINDS:
        t = time.time()
        img = nm.bake_image(ob, kind, 256, "%s_%s" % (ob.name, kind))
        import numpy as np; np.save(os.path.join(out, "%s_%s.npy" % (ob.name, kind)), np.array(img.pixels[:], np.float32).reshape(256, 256, 4))
        print("MESHMAP %s %s %.2fs" % (ob.name, kind, time.time() - t))
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, "meshmap_teste.range"))

# Material com o Mesh Wear ligado nos mapas assados, para ver no jogo (os 3 objetos girando).
import math
lib = os.path.join(bpy.utils.preset_paths("glsl_nodes")[0], "mesh_wear.glsl")
text = bpy.data.texts.new("mesh_wear.glsl"); text.from_string(open(lib, encoding="utf-8").read())
for i, ob in enumerate((sc.objects["Suzanne"], sc.objects["Peca"], sc.objects["Cubo"])):
    ob.location = ((i - 1) * 3.2, 0, 0)
    mat = bpy.data.materials.new("Wear_" + ob.name); mat.use_nodes = True
    mat.specular_intensity = 0.3
    ob.data.materials.append(mat)
    tree = mat.node_tree
    base = [n for n in tree.nodes if n.type in ('MATERIAL', 'MATERIAL_EXT')][0]
    node = tree.nodes.new("ShaderNodeGLSLScript"); node.script = text
    tree.interface_update(bpy.context)
    node["img_ao"] = bpy.data.images[ob.name + "_ao"]
    node["img_curvature"] = bpy.data.images[ob.name + "_curvature"]
    tree.interface_update(bpy.context)
    tree.links.new(node.outputs[0], base.inputs["Color"])
    bpy.ops.logic.sensor_add(type='ALWAYS', object=ob.name)
    bpy.ops.logic.actuator_add(type='MOTION', object=ob.name)
    ob.game.actuators[-1].offset_rotation = (0, 0, 0.01)
    bpy.ops.logic.controller_add(type='LOGIC_AND', object=ob.name)
    ob.game.controllers[-1].link(ob.game.sensors[-1], ob.game.actuators[-1])
cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera")); sc.objects.link(cam)
cam.location = (0, -9, 2.5); cam.rotation_euler = (math.radians(78), 0, 0); sc.camera = cam
sun = bpy.data.objects.new("Sol", bpy.data.lamps.new("Sol", 'SUN')); sc.objects.link(sun)
sun.rotation_euler = (math.radians(50), 0, math.radians(30))
sc.world = sc.world or bpy.data.worlds.new("World"); sc.world.horizon_color = (0.25, 0.27, 0.3)
sc.render.engine = 'BLENDER_GAME'
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, "meshmap_teste.range"))
