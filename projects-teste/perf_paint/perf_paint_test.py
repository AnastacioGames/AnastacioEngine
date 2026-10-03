# Teste de desempenho/correção: armature deform + weight paint + sculpt.
# Uso: RangeEngine.exe -b --python perf_paint_test.py
import bpy, time, os
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "perf_paint_test.range")
bpy.ops.wm.read_factory_settings()
for o in list(bpy.data.objects):
    if o.type == "MESH": bpy.data.objects.remove(o, do_unlink=True)
sc = bpy.context.scene
bpy.ops.mesh.primitive_uv_sphere_add(segments=256, ring_count=128)  # ~32k verts
me_ob = bpy.context.object
bpy.ops.object.armature_add(location=(0, 0, -1))
arm = bpy.context.object
bpy.ops.object.mode_set(mode='EDIT')
b = arm.data.edit_bones[0]; b.head = (0, 0, -1); b.tail = (0, 0, 0)
b2 = arm.data.edit_bones.new("Bone.001"); b2.head = (0, 0, 0); b2.tail = (0, 0, 1); b2.parent = b
bpy.ops.object.mode_set(mode='OBJECT')
me_ob.select = True; arm.select = True; sc.objects.active = arm
bpy.ops.object.parent_set(type='ARMATURE_AUTO')
pb = arm.pose.bones["Bone.001"]; pb.rotation_mode = 'XYZ'
nv = len(me_ob.data.vertices)
def deformed():
    m = me_ob.to_mesh(sc, True, 'PREVIEW'); r = [v.co.copy() for v in m.vertices]
    bpy.data.meshes.remove(m); return r
t = time.time(); N = 20
for i in range(N):
    pb.rotation_euler.x = 0.05 * i; sc.update()
    m = me_ob.to_mesh(sc, True, 'PREVIEW'); bpy.data.meshes.remove(m)
print("PERF armature deform: %d verts, %.2f ms/frame" % (nv, (time.time() - t) * 1000 / N))
# correção: deformação determinística e realmente aplicada
pb.rotation_euler.x = 0.8; sc.update(); a = deformed(); c = deformed()
moved = sum(1 for v, o in zip(a, me_ob.data.vertices) if (v - o.co).length > 1e-4)
print("CHECK deterministic:", a == c, "moved verts:", moved)
# weight paint
sc.objects.active = me_ob; me_ob.select = True
bpy.ops.object.mode_set(mode='WEIGHT_PAINT'); sc.update()
print("CHECK weight paint mode:", me_ob.mode)
bpy.ops.object.mode_set(mode='OBJECT')
# sculpt
bpy.ops.object.mode_set(mode='SCULPT'); print("CHECK sculpt mode:", me_ob.mode)
bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.wm.save_as_mainfile(filepath=out)
print("SAVED", out)
