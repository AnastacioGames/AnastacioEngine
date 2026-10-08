"""Run with build/bin/AnastacioEngine.exe -b --factory-startup --python this_file.
Data/pixel tests only: visual acceptance still belongs in the user's real game.
"""
import json
import os

import bpy
from mathutils import Vector


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def uv_values(mesh, name):
    return [tuple(item.uv) for item in mesh.uv_layers[name].data]


def pixel(image, uv):
    x = min(image.size[0] - 1, int(uv[0] * image.size[0]))
    y = min(image.size[1] - 1, int(uv[1] * image.size[1]))
    offset = (y * image.size[0] + x) * 4
    return tuple(image.pixels[offset:offset + 4])


def near(actual, expected, label, epsilon=0.025):
    check(all(abs(a - b) < epsilon for a, b in zip(actual, expected)),
          '{}: got {}, expected {}'.format(label, actual, expected))


def normal_in_object(mesh, poly, sample, uv_name):
    loops = list(poly.loop_indices)
    p = [mesh.vertices[mesh.loops[j].vertex_index].co for j in loops]
    uv = [mesh.uv_layers[uv_name].data[j].uv for j in loops]
    e1, e2 = p[1] - p[0], p[3] - p[0]
    d1, d2 = uv[1] - uv[0], uv[3] - uv[0]
    determinant = d1.x * d2.y - d1.y * d2.x
    tangent = ((e1 * d2.y - e2 * d1.y) / determinant).normalized()
    bitangent = ((e2 * d1.x - e1 * d2.x) / determinant).normalized()
    normal = e1.cross(e2).normalized()
    data = Vector([2 * v - 1 for v in sample[:3]])
    return (tangent * data.x + bitangent * data.y + normal * data.z).normalized()


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    import addon_utils
    addon_utils.enable('cycles', default_set=False)
    scene = bpy.context.scene
    scene.game_settings.use_shading_nodes = True
    scene.render.engine = 'BLENDER_GAME'
    scene.cycles.samples = 13
    scene.cycles.device = 'CPU'
    verts = [(-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
             (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)]
    faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
             (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    mesh = bpy.data.meshes.new('AtlasSource')
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    ob = bpy.data.objects.new('AtlasCube', mesh)
    scene.objects.link(ob)
    scene.objects.active = ob
    ob.select = True
    source_uv = mesh.uv_textures.new(name='SourceUV')
    source_uv.active_render = True
    for poly in mesh.polygons:
        for loop, co in zip(poly.loop_indices, [(0, 0), (1, 0), (1, 1), (0, 1)]):
            mesh.uv_layers['SourceUV'].data[loop].uv = co
    mesh.uv_textures.new(name='Lightmap')
    for i, item in enumerate(mesh.uv_layers['Lightmap'].data):
        item.uv = (0.1 + i * 0.003, 0.2 + i * 0.002)
    source_uv.active_render = True
    colors = [(0.8, 0.1, 0.02, 1), (0.03, 0.7, 0.2, 1), (0.1, 0.04, 0.9, 1),
              (0.4, 0.4, 0.04, 1), (0.05, 0.3, 0.5, 1), (0.6, 0.07, 0.4, 1)]
    materials = []
    for i, color in enumerate(colors):
        mat = bpy.data.materials.new('SourceMat{}'.format(i))
        mat.use_nodes = True
        tree = mat.node_tree
        tree.nodes.clear()
        shader = tree.nodes.new('ShaderNodeBsdfPrincipled')
        output = tree.nodes.new('ShaderNodeOutputMaterial')
        tree.links.new(shader.outputs['BSDF'], output.inputs['Surface'])
        shader.inputs['Base Color'].default_value = color
        shader.inputs['Metallic'].default_value = i / 5.0
        shader.inputs['Roughness'].default_value = 0.15 + i * 0.13
        shader.inputs['Specular'].default_value = 0.1 + i * 0.12
        mesh.materials.append(mat)
        mesh.polygons[i].material_index = i
        materials.append(mat)
    # A texture sampled from SourceUV, while the atlas uses a different UV layout.
    source_image = bpy.data.images.new('SourceGradient', 16, 16, float_buffer=True)
    source_image.colorspace_settings.name = 'Non-Color'
    source_image.pixels = [v for y in range(16) for x in range(16)
                           for v in ((x + 0.5) / 16, (y + 0.5) / 16, 0.25, 1)]
    source_image.pack(as_png=True)
    source_normal = bpy.data.images.new('SourceNormal', 8, 8, float_buffer=True)
    source_normal.colorspace_settings.name = 'Non-Color'
    normal_value = (0.6, 0.5, (1 - 0.2 ** 2) ** 0.5 * 0.5 + 0.5, 1)
    source_normal.pixels = list(normal_value) * 64
    source_normal.pack(as_png=True)
    tree = materials[0].node_tree
    shader = next(n for n in tree.nodes if n.type == 'BSDF_PRINCIPLED')
    texture = tree.nodes.new('ShaderNodeTexImage')
    texture.image = source_image
    texture.color_space = 'NONE'
    tree.links.new(texture.outputs['Color'], shader.inputs['Base Color'])
    normal_texture = tree.nodes.new('ShaderNodeTexImage')
    normal_texture.image = source_normal
    normal_texture.color_space = 'NONE'
    normal_node = tree.nodes.new('ShaderNodeNormalMap')
    # Intentionally implicit: the operator must pin the SOURCE tangent UV.
    tree.links.new(normal_texture.outputs['Color'], normal_node.inputs['Color'])
    tree.links.new(normal_node.outputs['Normal'], shader.inputs['Normal'])
    shared = bpy.data.objects.new('UnselectedSharedMesh', mesh)
    scene.objects.link(shared)
    shared.location.x = 5
    shared.select = True  # must not be baked accidentally
    lightmap = bpy.data.images.new('ExistingGI', 8, 8)
    lightmap.pixels = [0.2, 0.3, 0.4, 1] * 64
    lightmap.pack(as_png=True)
    scene.ae_lightmap = lightmap.name
    scene.ae_lightmap_use = True
    source_values = uv_values(mesh, 'SourceUV')
    light_values = uv_values(mesh, 'Lightmap')
    before_ids = (set(bpy.data.meshes.keys()), set(bpy.data.materials.keys()), set(bpy.data.images.keys()))
    # Preflight rejection must leave IDs and data intact.
    mat = materials[2]
    node = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    node.inputs['Transmission'].default_value = 0.5
    try:
        bpy.ops.material.anastacio_atlas_bake(resolution=64, samples=1, margin=2)
    except RuntimeError:
        pass
    else:
        raise AssertionError('Unsupported transmission must fail')
    check(ob.data == mesh, 'Failure replaced source mesh')
    check(before_ids == (set(bpy.data.meshes.keys()), set(bpy.data.materials.keys()), set(bpy.data.images.keys())),
          'Preflight failure leaked IDs')
    node.inputs['Transmission'].default_value = 0
    bad_uv = materials[0].node_tree.nodes.new('ShaderNodeUVMap')
    bad_uv.uv_map = 'MissingSourceUV'
    try:
        bpy.ops.material.anastacio_atlas_bake(resolution=64, samples=1, margin=2)
    except RuntimeError:
        pass
    else:
        raise AssertionError('Missing source UV must be reported before baking')
    check(ob.data == mesh, 'Missing UV rejection replaced source')
    materials[0].node_tree.nodes.remove(bad_uv)
    # A late failure after other maps were baked must also roll back cleanly.
    bad_math = materials[1].node_tree.nodes.new('ShaderNodeMath')
    bad_math.operation = 'ADD'
    bad_math.inputs[0].default_value = 2
    bad_math.inputs[1].default_value = 0
    shader = next(n for n in materials[1].node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    materials[1].node_tree.links.new(bad_math.outputs[0], shader.inputs['Metallic'])
    late_ids = (set(bpy.data.meshes.keys()), set(bpy.data.materials.keys()), set(bpy.data.images.keys()))
    try:
        bpy.ops.material.anastacio_atlas_bake(resolution=64, samples=1, margin=2)
    except RuntimeError:
        pass
    else:
        raise AssertionError('Out-of-range data must not be silently clipped by PNG packing')
    check(ob.data == mesh and shared.data == mesh, 'Late failure replaced original mesh')
    check(late_ids == (set(bpy.data.meshes.keys()), set(bpy.data.materials.keys()), set(bpy.data.images.keys())),
          'Late failure leaked temporary maps or materials')
    check(scene.render.engine == 'BLENDER_GAME' and scene.cycles.samples == 13,
          'Late failure did not restore render settings')
    check(uv_values(mesh, 'SourceUV') == source_values and uv_values(mesh, 'Lightmap') == light_values,
          'Late failure changed source UVs')
    materials[1].node_tree.nodes.remove(bad_math)
    # Failure after staging/copying materials must release every temporary ID.
    degenerate = bpy.data.meshes.new('DegenerateSource')
    degenerate.from_pydata([(0, 0, 0)] * 3, [], [(0, 1, 2)])
    degenerate.materials.append(materials[1])
    bad = bpy.data.objects.new('DegenerateObject', degenerate)
    scene.objects.link(bad)
    scene.objects.active = bad
    bad.select = True
    staged_ids = (set(bpy.data.meshes.keys()), set(bpy.data.materials.keys()), set(bpy.data.images.keys()))
    try:
        bpy.ops.material.anastacio_atlas_bake(resolution=64, samples=1, margin=2)
    except RuntimeError:
        pass
    else:
        raise AssertionError('Degenerate atlas must fail')
    check(bad.data == degenerate, 'Staging failure replaced source')
    check(staged_ids == (set(bpy.data.meshes.keys()), set(bpy.data.materials.keys()), set(bpy.data.images.keys())),
          'Staging failure leaked IDs')
    check(ob.select and shared.select and bad.select, 'Staging failure lost selection')
    scene.objects.unlink(bad)
    bpy.data.objects.remove(bad)
    bpy.data.meshes.remove(degenerate)
    scene.objects.active = ob
    result = bpy.ops.material.anastacio_atlas_bake(resolution=128, samples=1, margin=3)
    check(result == {'FINISHED'}, 'Atlas did not finish')
    check(ob.data != mesh and shared.data == mesh, 'Shared source mesh changed')
    check(mesh.use_fake_user, 'Source backup has no fake user')
    check(len(ob.data.materials) == 1, 'Result does not have a single material')
    check(all(p.material_index == 0 for p in ob.data.polygons), 'Face material index not remapped')
    check(uv_values(mesh, 'SourceUV') == source_values, 'Source UV changed')
    check(uv_values(ob.data, 'SourceUV') == source_values, 'Result lost source UV')
    check(uv_values(ob.data, 'Lightmap') == light_values, 'Result changed existing GI UV')
    check(scene.ae_lightmap == lightmap.name and scene.ae_lightmap_use, 'Existing GI settings changed')
    check(scene.render.engine == 'BLENDER_GAME' and scene.cycles.samples == 13,
          'Render settings not restored')
    check(ob.select and shared.select, 'Selection not restored')
    maps = {n.image.name.split('_')[-1]: n.image for n in ob.active_material.node_tree.nodes
            if n.type == 'TEX_IMAGE'}
    check(len(maps) == 5 and all(image.packed_file for image in maps.values()), 'Maps not packed')
    for i, poly in enumerate(ob.data.polygons):
        points = [ob.data.uv_layers['AnastacioAtlas'].data[j].uv for j in poly.loop_indices]
        center = [sum(p[c] for p in points) / len(points) for c in range(2)]
        expected_color = (0.5, 0.5, 0.25) if i == 0 else colors[i][:3]
        near(pixel(maps['BaseColor'], center)[:3], expected_color, 'BaseColor face {}'.format(i))
        near(pixel(maps['Metallic'], center)[:3], [i / 5.0] * 3, 'Metallic face {}'.format(i))
        near(pixel(maps['Roughness'], center)[:3], [0.15 + i * 0.13] * 3, 'Roughness face {}'.format(i))
        near(pixel(maps['Specular'], center)[:3], [0.1 + i * 0.12] * 3, 'Specular face {}'.format(i))
        if i == 0:
            expected_normal = normal_in_object(mesh, mesh.polygons[i], normal_value, 'SourceUV')
            actual_normal = normal_in_object(ob.data, poly, pixel(maps['Normal'], center), 'AnastacioAtlas')
            near(actual_normal, expected_normal, 'Normal orientation after UV repacking')
        else:
            near(pixel(maps['Normal'], center)[:3], [0.5, 0.5, 1], 'Normal face {}'.format(i))
    for i, mat in enumerate(materials):
        shader = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
        near(shader.inputs['Base Color'].default_value, colors[i], 'Original material')
        check(len(mat.node_tree.nodes) == (5 if i == 0 else 2), 'Temporary nodes leaked into original material')
    check(normal_node.uv_map == '', 'Original Normal Map UV was modified')
    result_ids = (set(bpy.data.meshes.keys()), set(bpy.data.materials.keys()), set(bpy.data.images.keys()))
    try:
        bpy.ops.material.anastacio_atlas_bake(resolution=64, samples=1, margin=2)
    except RuntimeError:
        pass
    else:
        raise AssertionError('Existing atlas UV must not be overwritten')
    check(result_ids == (set(bpy.data.meshes.keys()), set(bpy.data.materials.keys()), set(bpy.data.images.keys())),
          'Repeated bake leaked IDs')
    camera = bpy.data.cameras.new('AtlasCamera')
    camera_ob = bpy.data.objects.new('AtlasCamera', camera)
    scene.objects.link(camera_ob)
    camera_ob.location = (4, -7, 4)
    camera_ob.rotation_euler = (-camera_ob.location).to_track_quat('-Z', 'Y').to_euler()
    scene.camera = camera_ob
    scene.render.resolution_x = 480
    scene.render.resolution_y = 320
    # Short standalone smoke: no screenshot or visual assertions.
    text = bpy.data.texts.new('anastacio_atlas_runtime.py')
    text.write('import bge\n'
               'def run(cont):\n'
               '    own = cont.owner\n'
               '    own["ticks"] = own.get("ticks", 0) + 1\n'
               '    if own["ticks"] == 5:\n'
               '        obj = bge.logic.getCurrentScene().objects["AtlasCube"]\n'
               '        assert len(obj.meshes[0].materials) == 1\n'
               '        print("ANASTACIO_ATLAS_RUNTIME_PASS")\n'
               '        bge.logic.endGame()\n')
    bpy.ops.logic.sensor_add(type='ALWAYS', object=camera_ob.name)
    sensor = camera_ob.game.sensors[-1]
    sensor.name = 'AtlasSmoke'
    sensor.use_pulse_true_level = True
    bpy.ops.logic.controller_add(type='PYTHON', object=camera_ob.name)
    controller = camera_ob.game.controllers[-1]
    controller.name = 'AtlasSmoke'
    controller.mode = 'MODULE'
    controller.module = 'anastacio_atlas_runtime.run'
    controller.link(sensor=sensor)
    out_dir = os.path.join(bpy.path.abspath('//'), 'projects-teste', 'material-atlas')
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, 'native_atlas_test.range')
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    ob = bpy.data.objects['AtlasCube']
    maps = {n.image.name.split('_')[-1]: n.image for n in ob.active_material.node_tree.nodes
            if n.type == 'TEX_IMAGE'}
    for i, poly in enumerate(ob.data.polygons):
        points = [ob.data.uv_layers['AnastacioAtlas'].data[j].uv for j in poly.loop_indices]
        center = [sum(p[c] for p in points) / len(points) for c in range(2)]
        expected_color = (0.5, 0.5, 0.25) if i == 0 else colors[i][:3]
        near(pixel(maps['BaseColor'], center)[:3], expected_color, 'Reloaded BaseColor')
        near(pixel(maps['Metallic'], center)[:3], [i / 5.0] * 3, 'Reloaded Metallic')
        if i == 0:
            mesh = bpy.data.meshes['AtlasSource']
            expected_normal = normal_in_object(mesh, mesh.polygons[i], normal_value, 'SourceUV')
            actual_normal = normal_in_object(ob.data, poly, pixel(maps['Normal'], center), 'AnastacioAtlas')
            near(actual_normal, expected_normal, 'Reloaded normal orientation')
        else:
            near(pixel(maps['Normal'], center)[:3], [0.5, 0.5, 1], 'Reloaded Normal')
    print('ANASTACIO_ATLAS_TEST_PASS ' + json.dumps({'file': path, 'maps': list(maps)}))


main()
