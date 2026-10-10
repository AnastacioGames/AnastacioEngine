"""Actual GI/atlas interoperability and device tests; no visual assertions.

Use --python-exit-code 1. Add -- --undo in a windowed editor for undo/redo.
"""
import json
import math
import os
import sys
import traceback

import addon_utils
import bpy


def check(value, message):
    if not value:
        raise AssertionError(message)


def setup():
    if bpy.app.background:
        bpy.ops.wm.read_factory_settings(use_empty=True)
    else:
        for item in list(bpy.context.scene.objects):
            bpy.context.scene.objects.unlink(item)
            bpy.data.objects.remove(item)
    addon_utils.enable('cycles', default_set=False)
    scene = bpy.context.scene
    scene.game_settings.use_shading_nodes = True
    scene.render.engine = 'BLENDER_GAME'
    bpy.ops.mesh.primitive_cube_add()
    ob = scene.objects.active
    ob.name = 'IntegrationCube'
    ob.data.uv_textures.new(name='SourceUV')
    for poly in ob.data.polygons:
        for loop, uv in zip(poly.loop_indices, [(0, 0), (1, 0), (1, 1), (0, 1)]):
            ob.data.uv_layers['SourceUV'].data[loop].uv = uv
    for color in [(0.7, 0.2, 0.1, 1), (0.1, 0.5, 0.7, 1)]:
        mat = bpy.data.materials.new('IntegrationMaterial')
        mat.use_nodes = True
        mat.node_tree.nodes.clear()
        shader = mat.node_tree.nodes.new('ShaderNodeBsdfPrincipled')
        output = mat.node_tree.nodes.new('ShaderNodeOutputMaterial')
        shader.inputs['Base Color'].default_value = color
        shader.inputs['Roughness'].default_value = 0.5
        mat.node_tree.links.new(shader.outputs[0], output.inputs['Surface'])
        ob.data.materials.append(mat)
    for poly in ob.data.polygons:
        poly.material_index = poly.index % 2
    world = bpy.data.worlds.new('IntegrationWorld')
    world.use_nodes = True
    world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.3, 0.3, 0.3, 1)
    world.node_tree.nodes['Background'].inputs['Strength'].default_value = 1
    scene.world = world
    settings = scene.ae_lightmap_settings
    settings.resolution = '256'
    settings.samples = 8
    settings.use_gpu = False
    settings.use_denoise = False
    settings.use_volume = False
    settings.use_world = True
    scene.cycles.device = 'CPU'
    scene.update()
    return scene, ob


def uvs(ob, name):
    return [tuple(item.uv) for item in ob.data.uv_layers[name].data]


def maps(ob):
    return {n.image.name.split('_')[-1]: n.image for n in ob.active_material.node_tree.nodes
            if n.type == 'TEX_IMAGE' and n.image}


def atlas(ob, configured=False):
    check(bpy.ops.material.anastacio_atlas_bake(resolution=128, margin=3, samples=1,
          use_configured_device=configured) == {'FINISHED'}, 'Atlas failed')
    check(len(ob.data.materials) == 1 and len(maps(ob)) == 5, 'Invalid atlas result')
    colors = [(0.7, 0.2, 0.1), (0.1, 0.5, 0.7)]
    image = maps(ob)['BaseColor']
    for poly in ob.data.polygons:
        coords = [ob.data.uv_layers['AnastacioAtlas'].data[i].uv for i in poly.loop_indices]
        center = [sum(uv[c] for uv in coords) / len(coords) for c in range(2)]
        x, y = [int(center[c] * image.size[c]) for c in range(2)]
        offset = (y * image.size[0] + x) * 4
        check(max(abs(a-b) for a, b in zip(image.pixels[offset:offset+3],
              colors[poly.index % 2])) < 0.025, 'GI contaminated base color')


def lightmap(scene, ob):
    check(bpy.ops.scene.ae_lightmap_bake() == {'FINISHED'}, 'GI bake failed')
    image = bpy.data.images[scene.ae_lightmap]
    pixels = list(image.pixels)
    check(image.packed_file and scene.ae_lightmap_use, 'GI not packed/enabled')
    check(all(math.isfinite(v) for v in pixels), 'Non-finite GI pixels')
    rgb = [pixels[i] * pixels[i - i % 4 + 3] * 8 for i in range(len(pixels)) if i % 4 < 3]
    check(max(rgb) > 0.01, 'GI unexpectedly black')
    check('Lightmap' in ob.data.uv_layers, 'GI UV missing')
    return pixels


def integrations():
    for order in ['GI_ATLAS_GI', 'ATLAS_GI']:
        scene, ob = setup()
        if order == 'GI_ATLAS_GI':
            pixels = lightmap(scene, ob)
            before = uvs(ob, 'Lightmap')
            atlas(ob)
            check(uvs(ob, 'Lightmap') == before, 'Atlas changed GI UV')
            check(list(bpy.data.images[scene.ae_lightmap].pixels) == pixels, 'Atlas changed GI pixels')
        else:
            atlas(ob)
        before = uvs(ob, 'AnastacioAtlas')
        material_pixels = {name: list(image.pixels) for name, image in maps(ob).items()}
        lightmap(scene, ob)
        check(uvs(ob, 'AnastacioAtlas') == before, 'GI changed atlas UV')
        check(material_pixels == {name: list(image.pixels) for name, image in maps(ob).items()},
              'GI changed material maps')
        check(scene.render.engine == 'BLENDER_GAME', 'Render engine not restored')
        print('ANASTACIO_ATLAS_INTEGRATION_PASS ' + order, flush=True)
    scene, ob = setup()
    prefs = bpy.context.user_preferences.addons['cycles'].preferences
    import _cycles
    devices = []
    for backend in ['CUDA', 'OPENCL']:
        for entry in _cycles.available_devices(backend):
            if entry[1] == backend:
                devices.append((backend, entry[0], entry[2]))
    print('ANASTACIO_ATLAS_GPU_DEVICES ' + json.dumps(devices), flush=True)
    if not devices:
        print('ANASTACIO_ATLAS_GPU_UNAVAILABLE', flush=True)
        atlas(ob, configured=True)
        print('ANASTACIO_ATLAS_CONFIGURED_CPU_PASS', flush=True)
    else:
        backend, name, ident = devices[0]
        prefs.compute_device_type = backend
        prefs.get_devices(backend)
        for device in prefs.devices:
            device.use = device.id == ident
        scene.cycles.device = 'GPU'
        atlas(ob, configured=True)
        check(scene.cycles.device == 'GPU', 'GPU setting not restored')
        print('ANASTACIO_ATLAS_GPU_PASS ' + name, flush=True)


def undo():
    scene, ob = setup()
    bpy.context.user_preferences.edit.use_global_undo = True
    bpy.ops.ed.undo_push(message='Atlas integration baseline')
    atlas(ob)
    # Scripted operators do not automatically push the UI event's undo step.
    bpy.ops.ed.undo_push(message='Bake Material Atlas')
    check(bpy.ops.ed.undo() == {'FINISHED'}, 'Undo failed')
    ob = bpy.data.objects['IntegrationCube']
    check(len(ob.data.materials) == 2 and 'AnastacioAtlas' not in ob.data.uv_layers,
          'Undo did not restore source')
    check(not any(image.name.endswith('_BaseColor') for image in bpy.data.images), 'Undo leaked maps')
    check(bpy.ops.ed.redo() == {'FINISHED'}, 'Redo failed')
    ob = bpy.data.objects['IntegrationCube']
    check(len(ob.data.materials) == 1 and len(maps(ob)) == 5, 'Redo did not restore atlas')
    check(all(image.packed_file for image in maps(ob).values()), 'Redo lost packed images')
    print('ANASTACIO_ATLAS_UNDO_REDO_PASS', flush=True)


def restore():
    scene, ob = setup()
    source = ob.data
    ob.active_material_index = 1
    source_uv = uvs(ob, 'SourceUV')
    atlas(ob)
    baked = ob.data
    check(baked.get('_anastacio_atlas_source') == source, 'Missing explicit backup reference')
    source.name = 'RenamedSourceBackup'
    duplicate = ob.copy()
    scene.objects.link(duplicate)
    duplicate.name = 'SharedAtlas'
    path = os.path.abspath('projects-teste/material-atlas/restore_atlas_test.range')
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    scene = bpy.context.scene
    ob = bpy.data.objects['IntegrationCube']
    duplicate = bpy.data.objects['SharedAtlas']
    source = bpy.data.meshes['RenamedSourceBackup']
    baked = ob.data
    check(baked.get('_anastacio_atlas_source') == source, 'Backup reference lost on reload')
    scene.objects.active = ob
    ob.select = True
    modifier = ob.modifiers.new('RestoreGuard', 'SUBSURF')
    try:
        bpy.ops.material.anastacio_atlas_restore()
    except RuntimeError:
        pass
    else:
        raise AssertionError('Restore silently discarded modifier')
    check(ob.data == baked, 'Refused restore changed mesh')
    ob.modifiers.remove(modifier)
    check(bpy.ops.material.anastacio_atlas_restore() == {'FINISHED'}, 'Restore failed')
    check(ob.data == source and duplicate.data == baked, 'Restore changed shared atlas')
    check(len(ob.data.materials) == 2 and ob.active_material_index == 1, 'Source slots not restored')
    check(uvs(ob, 'SourceUV') == source_uv and 'AnastacioAtlas' not in ob.data.uv_layers,
          'Original UVs not restored')
    check(baked.use_fake_user and source.use_fake_user, 'Variant backup not preserved')
    check(len(maps(duplicate)) == 5 and all(image.packed_file for image in maps(duplicate).values()),
          'Shared atlas lost maps')
    check(not bpy.ops.material.anastacio_atlas_restore.poll(), 'Restore accepts unbaked mesh')
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    check(bpy.data.objects['IntegrationCube'].data.name == 'RenamedSourceBackup',
          'Restored source lost on save/reload')
    print('ANASTACIO_ATLAS_RESTORE_PASS', flush=True)


def main():
    try:
        if '--undo' in sys.argv:
            undo()
        elif '--restore' in sys.argv:
            restore()
        else:
            integrations()
    except Exception:
        traceback.print_exc()
        sys.stdout.flush()
        sys.stderr.flush()
        if not bpy.app.background:
            os._exit(1)
        raise
    else:
        print('ANASTACIO_ATLAS_EXTENDED_TEST_PASS', flush=True)
        if not bpy.app.background:
            bpy.ops.wm.quit_blender()


if __name__ == '__main__':
    main()
