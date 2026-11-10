"""Palette Atlas: build/bin/AnastacioEngine.exe -b --factory-startup --python tools/test_palette_atlas.py
Testa dados e pixels (não aparência): classificação, cores na paleta, UV no centro
do quadrado, transparência, paleta compartilhada, save/reload e Restore.
"""
import os
import tempfile

import bpy


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)


def near(a, b, label, eps=0.01):
    check(all(abs(x - y) < eps for x, y in zip(a, b)), "%s: got %s expected %s" % (label, list(a), list(b)))


def pixel(image, uv):
    x = int(uv[0] * image.size[0])
    y = int(uv[1] * image.size[1])
    o = (y * image.size[0] + x) * 4
    return tuple(image.pixels[o:o + 4])


def srgb(c):
    return c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def cube(name, location):
    verts = [(-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
             (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)]
    faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
             (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.uv_textures.new("UVMap")
    mesh.uv_textures.new("Lightmap")
    ob = bpy.data.objects.new(name, mesh)
    ob.location = location
    bpy.context.scene.objects.link(ob)
    return ob


def pbr(name, color, rough, metal, alpha=None):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    tree = mat.node_tree
    tree.nodes.clear()
    out = tree.nodes.new("ShaderNodeOutputMaterial")
    bsdf = tree.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = color + (1.0,)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    surface = bsdf.outputs["BSDF"]
    if alpha is not None:
        tr = tree.nodes.new("ShaderNodeBsdfTransparent")
        mix = tree.nodes.new("ShaderNodeMixShader")
        mix.inputs[0].default_value = alpha
        tree.links.new(tr.outputs["BSDF"], mix.inputs[1])
        tree.links.new(surface, mix.inputs[2])
        surface = mix.outputs["Shader"]
        mat.game_settings.alpha_blend = 'ALPHA'
        mat.use_transparency = True
        mat.alpha = 0.999
    tree.links.new(surface, out.inputs["Surface"])
    return mat


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_GAME'
    scene.game_settings.use_shading_nodes = True
    from bl_operators import anastacio_palette_atlas as pa

    red = pbr("Red", (0.8, 0.05, 0.05), 0.4, 0.0)
    iron = pbr("Iron", (0.55, 0.56, 0.57), 0.3, 1.0)
    glass = pbr("IronGlass", (0.6, 0.7, 0.8), 0.1, 1.0, alpha=0.35)

    a = cube("A", (0, 0, 0))
    for m in (red, iron, glass):
        a.data.materials.append(m)
    for i, poly in enumerate(a.data.polygons):
        poly.material_index = i % 3

    b = cube("B", (3, 0, 0))  # compartilha cor com A
    b.data.materials.append(iron)

    c = cube("C", (6, 0, 0))  # textura -> fica de fora
    tex_mat = pbr("Textured", (1, 1, 1), 0.5, 0.0)
    img = bpy.data.images.new("Tex", 4, 4)
    node = tex_mat.node_tree.nodes.new("ShaderNodeTexImage")
    node.image = img
    bsdf = [n for n in tex_mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'][0]
    tex_mat.node_tree.links.new(node.outputs["Color"], bsdf.inputs["Base Color"])
    c.data.materials.append(tex_mat)

    summary = pa.classify(a)
    check(all(flat for _i, _n, flat, _r in summary), "A should be all flat: %s" % summary)
    check(not pa.classify(c)[0][2], "C should need bake")

    for ob in scene.objects:
        ob.select = True
    scene.objects.active = a
    result = bpy.ops.material.anastacio_palette_atlas()
    check(result == {'FINISHED'}, "operator failed")

    pal = bpy.data.images[pa.PALETTE_NAME]
    data = bpy.data.images[pa.DATA_NAME]
    check(pal.packed_file is not None and data.packed_file is not None, "images not packed")
    check(c.data.name == "C", "textured object must be untouched")
    check(len(a.data.materials) == 2, "A: opaque + alpha result, got %d" % len(a.data.materials))
    check(b.data.materials[0] == a.data.materials[0], "B must share the opaque palette material")
    check(len(a.data.uv_layers) == 3 and "Lightmap" in a.data.uv_layers, "Lightmap UV lost")

    expected = {0: (red, 0.4, 0.0, 1.0), 1: (iron, 0.3, 1.0, 1.0), 2: (glass, 0.1, 1.0, 0.35)}
    uv = a.data.uv_layers[pa.UV_NAME]
    for poly in a.data.polygons:
        mat, rough, metal, alpha = expected[poly.index % 3]
        coords = {tuple(round(v, 6) for v in uv.data[li].uv) for li in poly.loop_indices}
        check(len(coords) == 1, "face UV must be one point")
        point = coords.pop()
        col = [n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'][0].inputs["Base Color"].default_value
        near(pixel(pal, point), [srgb(col[0]), srgb(col[1]), srgb(col[2]), alpha], "color face %d" % poly.index)
        near(pixel(data, point)[:2], [rough, metal], "data face %d" % poly.index)
        want_alpha = alpha < 1.0
        got = a.data.materials[poly.material_index]
        check(got.get(pa.SIG_PROP) and ('"transparent": true' in got[pa.SIG_PROP]) == want_alpha,
              "face %d wrong result material" % poly.index)
    check(len(pa.Palette(scene).keys) == 3, "3 unique colors expected")

    # Material legado entra na mesma paleta.
    d = cube("D", (9, 0, 0))
    leg = bpy.data.materials.new("Legacy")
    leg.diffuse_color = (0.1, 0.6, 0.2)
    d.data.materials.append(leg)
    for ob in scene.objects:
        ob.select = ob == d
    scene.objects.active = d
    check(bpy.ops.material.anastacio_palette_atlas() == {'FINISHED'}, "legacy failed")
    lm = d.data.materials[0]
    check(not lm.use_nodes and lm.texture_slots[0].texture.image == pal, "legacy result wrong")
    check(len(pa.Palette(scene).keys) == 4, "legacy color should add one cell")

    path = os.path.join(tempfile.gettempdir(), "ae_palette_test.range")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    scene = bpy.context.scene
    pal = bpy.data.images[pa.PALETTE_NAME]
    check(pal.packed_file is not None and len(pa.Palette(scene).keys) == 4, "palette lost on reload")

    a = scene.objects["A"]
    for ob in scene.objects:
        ob.select = ob == a
    scene.objects.active = a
    check(bpy.ops.material.anastacio_atlas_restore() == {'FINISHED'}, "restore failed")
    check(a.data.name == "A" and [m.name for m in a.data.materials] == ["Red", "Iron", "IronGlass"],
          "restore did not bring materials back")
    print("PALETTE ATLAS TEST OK")


main()
