"""Viewport x Game parity test (Game PBR): 4 Points with shadows (1st with IES cone), Wireframe sphere/cube.
Run with: RangeEngine -b --python tools/create_viewport_parity_test.py"""
import bpy, math
for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.use_shading_nodes = True
world = bpy.data.worlds.new("Parity World"); world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.02, 0.02, 0.025, 1.0)
scene.world = world

def diffuse(name, col):
    m = bpy.data.materials.new(name); m.use_nodes = True
    m.node_tree.nodes["Diffuse BSDF"].inputs["Color"].default_value = col + (1.0,)
    return m
floor = diffuse("Floor", (0.8, 0.8, 0.8))
bpy.ops.mesh.primitive_plane_add(location=(0, 0, 0), radius=12); bpy.context.object.data.materials.append(floor)
bpy.ops.mesh.primitive_plane_add(location=(0, 5, 5), radius=12, rotation=(math.pi / 2, 0, 0)); bpy.context.object.data.materials.append(floor)

pillar = diffuse("Pillar", (0.8, 0.3, 0.2))
cone = bpy.data.texts.new("cone.ies")
v = list(range(0, 91, 5))
cone.write("IESNA:LM-63-2002\n[TEST] cone\nTILT=NONE\n1 1000 1 %d 1 1 2 0 0 0\n1 1 100\n%s\n0\n%s\n" % (
    len(v), " ".join(str(a) for a in v),
    " ".join("%.1f" % (1000.0 * (1.0 if a <= 25 else max(0.0, 1.0 - (a - 25) / 10.0))) for a in v)))

for i in range(4):
    x = -7.5 + i * 5
    bpy.ops.mesh.primitive_cube_add(location=(x + 0.8, 1.0, 0.75), radius=0.4)
    bpy.context.object.scale.z = 1.9
    bpy.context.object.data.materials.append(pillar)
    bpy.ops.object.lamp_add(type='POINT', location=(x, 0, 2.5))
    bpy.context.object.name = "Point%d" % (i + 1)
    lamp = bpy.context.object.data
    lamp.energy = 0.8; lamp.distance = 6.0; lamp.use_nodes = True
    lamp.shadow_buffer_size = 512; lamp.shadow_buffer_clip_start = 0.1; lamp.shadow_buffer_clip_end = 20
    if i == 0:
        t = lamp.node_tree
        ies = t.nodes.new("ShaderNodeTexIES"); ies.mode = 'INTERNAL'; ies.ies = cone
        t.links.new(ies.outputs["Fac"], t.nodes["Emission"].inputs["Strength"])

wm = bpy.data.materials.new("Wire"); wm.use_nodes = True
t = wm.node_tree
for n in list(t.nodes):
    if n.type != 'OUTPUT_MATERIAL': t.nodes.remove(n)
wire = t.nodes.new("ShaderNodeWireframe"); wire.inputs["Size"].default_value = 0.03
base = t.nodes.new("ShaderNodeBsdfDiffuse"); base.inputs["Color"].default_value = (0.2, 0.2, 0.25, 1.0)
edge = t.nodes.new("ShaderNodeEmission"); edge.inputs["Color"].default_value = (1.0, 0.8, 0.1, 1.0)
mix = t.nodes.new("ShaderNodeMixShader")
t.links.new(wire.outputs["Fac"], mix.inputs["Fac"]); t.links.new(base.outputs[0], mix.inputs[1]); t.links.new(edge.outputs[0], mix.inputs[2])
t.links.new(mix.outputs[0], t.nodes["Material Output"].inputs["Surface"])
bpy.ops.mesh.primitive_uv_sphere_add(location=(-2.5, -3, 1.2), size=1.0); bpy.context.object.data.materials.append(wm)
bpy.ops.mesh.primitive_cube_add(location=(2.5, -3, 1.0), radius=0.9); bpy.context.object.data.materials.append(wm)

bpy.ops.object.camera_add(location=(0, -16, 8), rotation=(1.12, 0, 0)); scene.camera = bpy.context.object
bpy.ops.wm.save_as_mainfile(filepath=r"D:\AnastacioEngine\viewport_parity_test.range")
