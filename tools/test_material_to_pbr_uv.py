"""Regression test for the legacy-material to PBR UV-map conversion.

Run with:
    build/bin/AnastacioEngine.exe -b --python tools/test_material_to_pbr_uv.py
"""

import bpy


def convert_case(name, uv_names, slot_uv, expected_uv):
    mesh = bpy.data.meshes.new(name + "Mesh")
    mesh.from_pydata(((-1, -1, 0), (1, -1, 0), (1, 1, 0), (-1, 1, 0)), (), ((0, 1, 2, 3),))
    mesh.update()
    for uv_name in uv_names:
        mesh.uv_textures.new(name=uv_name)

    ob = bpy.data.objects.new(name, mesh)
    bpy.context.scene.objects.link(ob)
    bpy.context.scene.objects.active = ob
    ob.select = True

    mat = bpy.data.materials.new(name + "Material")
    mesh.materials.append(mat)
    image = bpy.data.images.new(name + "Image", 1, 1)
    texture = bpy.data.textures.new(name + "Texture", type='IMAGE')
    texture.image = image
    slot = mat.texture_slots.add()
    slot.texture = texture
    slot.texture_coords = 'UV'
    slot.uv_layer = slot_uv
    slot.use_map_color_diffuse = True

    result = bpy.ops.material.to_pbr_nodes()
    assert result == {'FINISHED'}, (name, result)
    uv_nodes = [node for node in mat.node_tree.nodes if node.bl_idname == 'ShaderNodeUVMap']
    tex_coords = [node for node in mat.node_tree.nodes if node.bl_idname == 'ShaderNodeTexCoord']
    assert len(uv_nodes) == 1, (name, len(uv_nodes))
    assert uv_nodes[0].uv_map == expected_uv, (name, uv_nodes[0].uv_map, expected_uv)
    assert not tex_coords, (name, len(tex_coords))

    ob.select = False


bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.render.engine = 'BLENDER_GAME'

convert_case("ImplicitUV", ("FirstUV", "SecondUV"), "", "FirstUV")
convert_case("ExplicitUV", ("FirstUV", "SecondUV"), "SecondUV", "SecondUV")
convert_case("MissingUV", (), "", "")

print("MATERIAL_TO_PBR_UV_TEST ok")
