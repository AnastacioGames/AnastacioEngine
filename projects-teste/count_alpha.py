import bpy
scene = bpy.context.scene
count = 0
alpha_objs = []
for obj in scene.objects:
    if obj.type == 'MESH':
        for slot in obj.material_slots:
            mat = slot.material
            if mat and mat.game_settings.alpha_blend != 'OPAQUE':
                alpha_objs.append(obj.name)
                count += 1
                break
print("TOTAL_OBJECTS:", len(scene.objects))
print("ALPHA_OBJECTS:", count)
print("SAMPLE:", alpha_objs[:20])
