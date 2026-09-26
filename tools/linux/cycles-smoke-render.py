# Smoke test do Cycles (CPU): monta esfera + chao + lampada e renderiza.
# Uso: RangeEngine -b --factory-startup --python cycles-smoke-render.py -- saida.png <amostras>
import bpy, sys, time
out = sys.argv[sys.argv.index("--")+1]; spp = int(sys.argv[-1])
for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)
sc = bpy.context.scene; sc.cursor_location = (0,0,0)
sc.render.engine = 'CYCLES'
bpy.ops.mesh.primitive_plane_add(radius=6, location=(0,0,0))
bpy.ops.mesh.primitive_uv_sphere_add(size=1, location=(0,0,1)); bpy.ops.object.shade_smooth()
m = bpy.data.materials.new("Red"); m.use_nodes = True
m.node_tree.nodes["Diffuse BSDF"].inputs[0].default_value = (0.8,0.1,0.1,1)
bpy.context.object.data.materials.append(m)
bpy.ops.object.lamp_add(type='POINT', location=(3,-2,4))
lamp = bpy.context.object.data; lamp.use_nodes = True
lamp.node_tree.nodes["Emission"].inputs["Strength"].default_value = 800
bpy.ops.object.camera_add(location=(0,-7,3), rotation=(1.2,0,0)); sc.camera = bpy.context.object
sc.cycles.samples = spp; sc.cycles.device = 'CPU'
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 320, 240, 100
sc.render.filepath = out
t = time.time(); bpy.ops.render.render(write_still=True)
print("ENGINE", sc.render.engine, "SPP", spp, "RENDER_OK %.2fs" % (time.time()-t))
