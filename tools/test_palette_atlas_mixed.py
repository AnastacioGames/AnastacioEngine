"""Atlas misturado: build/bin/AnastacioEngine.exe -b --factory-startup --python tools/test_palette_atlas_mixed.py
Auto escolhe Bake; materiais lisos viram quadrados exatos na faixa de baixo,
faces texturizadas ficam acima da faixa.
"""
import bpy


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)


def pixel(image, uv):
    x = int(uv[0] * image.size[0])
    y = int(uv[1] * image.size[1])
    o = (y * image.size[0] + x) * 4
    return tuple(image.pixels[o:o + 4])


def principled(mat):
    return [n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'][0]


def flat(name, color, rough, metal):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    tree = mat.node_tree
    tree.nodes.clear()
    out = tree.nodes.new("ShaderNodeOutputMaterial")
    b = tree.nodes.new("ShaderNodeBsdfPrincipled")
    tree.links.new(b.outputs["BSDF"], out.inputs["Surface"])
    b.inputs["Base Color"].default_value = color + (1.0,)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    return mat


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    import addon_utils
    addon_utils.enable('cycles', default_set=False)
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_GAME'
    scene.game_settings.use_shading_nodes = True
    scene.cycles.device = 'CPU'

    verts = [(-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
             (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)]
    faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
             (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    mesh = bpy.data.meshes.new("Mixed")
    mesh.from_pydata(verts, [], faces)
    mesh.uv_textures.new("UVMap")
    ob = bpy.data.objects.new("Mixed", mesh)
    scene.objects.link(ob)
    scene.objects.active = ob
    ob.select = True

    img = bpy.data.images.new("Checker", 16, 16)
    img.generated_type = 'COLOR_GRID'
    tex_mat = flat("Textured", (1, 1, 1), 0.5, 0.0)
    node = tex_mat.node_tree.nodes.new("ShaderNodeTexImage")
    node.image = img
    tex_mat.node_tree.links.new(node.outputs["Color"], principled(tex_mat).inputs["Base Color"])
    red = flat("Red", (0.8, 0.05, 0.05), 0.4, 0.0)
    iron = flat("Iron", (0.55, 0.56, 0.57), 0.3, 1.0)
    glass = flat("Glass", (0.6, 0.7, 0.8), 0.1, 1.0)
    gt = glass.node_tree
    out = [n for n in gt.nodes if n.type == 'OUTPUT_MATERIAL'][0]
    tr = gt.nodes.new("ShaderNodeBsdfTransparent")
    mix = gt.nodes.new("ShaderNodeMixShader")
    mix.inputs[0].default_value = 0.35
    gt.links.new(tr.outputs["BSDF"], mix.inputs[1])
    gt.links.new(principled(glass).outputs["BSDF"], mix.inputs[2])
    gt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    glass.game_settings.alpha_blend = 'ALPHA'
    glass.use_transparency = True
    glass.alpha = 0.999
    for m in (tex_mat, red, iron, glass):
        mesh.materials.append(m)
    for i, poly in enumerate(mesh.polygons):
        poly.material_index = [0, 0, 0, 3, 1, 2][i]

    from bl_operators import anastacio_palette_atlas as pa
    summary = pa.classify(ob)
    check([s[2] for s in summary] == [False, True, True, True], "classify: %s" % summary)

    size = 1024
    bpy.ops.material.anastacio_atlas_auto(mode='AUTO')
    check(ob.data.name != "Mixed" and len(ob.data.materials) == 2, "bake did not apply: %s" % [m.name for m in ob.data.materials])
    check(ob.data.materials[1].name.startswith("AnastacioPalette_Alpha"), "glass slot not palette alpha")
    pal = bpy.data.images[pa.PALETTE_NAME]
    puv = ob.data.uv_layers[pa.UV_NAME]
    gpoly = ob.data.polygons[3]
    check(gpoly.material_index == 1, "glass face not on alpha slot")
    point = tuple(puv.data[gpoly.loop_indices[0]].uv)
    check(abs(pixel(pal, point)[3] - 0.35) < 0.01, "glass alpha in palette: %s" % (pixel(pal, point),))
    check(all(p.material_index == 0 for p in ob.data.polygons if p.index != 3), "other faces must use atlas")
    atlas = ob.data.uv_layers["AnastacioAtlas"]
    strip = (8 + 2) / size
    base = bpy.data.images["AnastacioAtlas_BaseColor"]
    rough = bpy.data.images["AnastacioAtlas_Roughness"]
    metal = bpy.data.images["AnastacioAtlas_Metallic"]
    want = {1: (red, 0.4, 0.0), 2: (iron, 0.3, 1.0)}
    for poly in ob.data.polygons:
        uvs = [tuple(atlas.data[li].uv) for li in poly.loop_indices]
        src = [0, 0, 0, 3, 1, 2][poly.index]
        if src == 3:
            continue
        if src == 0:
            check(all(v[1] >= strip - 1e-4 for v in uvs), "textured face %d inside strip" % poly.index)
            continue
        check(len(set(uvs)) == 1 and uvs[0][1] < strip, "flat face %d not a cell point" % poly.index)
        mat, r, m = want[src]
        col = principled(mat).inputs["Base Color"].default_value
        got = pixel(base, uvs[0])
        check(all(abs(a - b) < 0.002 for a, b in zip(got[:3], col[:3])), "color %s vs %s" % (got, list(col)))
        check(abs(pixel(rough, uvs[0])[0] - r) < 0.002, "roughness cell")
        check(abs(pixel(metal, uvs[0])[0] - m) < 0.002, "metallic cell")
    check(bpy.ops.material.anastacio_atlas_restore() == {'FINISHED'}, "restore failed")
    check([m.name for m in ob.data.materials] == ["Textured", "Red", "Iron", "Glass"], "restore materials")
    print("MIXED PALETTE ATLAS TEST OK")


main()
