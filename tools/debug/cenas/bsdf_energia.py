"""Legacy bpy BSDF fixtures. editor -b --factory-startup --python this.py -- OUTDIR

Generates furnace, sun, hdri_ssgi, lightmap and clearcoat .range files.
Reopen with -- OUTDIR inspect to validate saved data. Includes real CPU bakes
(256 atlas, 8 samples). No player window is launched.
BSDF_SECONDS/BSDF_LOG enable timed runtime evidence; --server is logic only.
"""
import bpy
import json
import os
import sys
from mathutils import Vector

ARGS = sys.argv[sys.argv.index('--')+1:]
DEST = os.path.abspath(ARGS[0])
os.makedirs(DEST, exist_ok=True)
VARIANTS = ('furnace', 'sun', 'hdri_ssgi', 'lightmap', 'clearcoat')


def material(name, rough=.5, metal=0, distribution='GGX', coat=0, ccrough=.1, own=False):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    p = nt.nodes.new('ShaderNodeBsdfPrincipled')
    p.distribution = distribution
    p.inputs['Base Color'].default_value = (1, 1, 1, 1) if metal else (.12, .25, .55, 1)
    for key, value in (('Roughness', rough), ('Metallic', metal), ('Clearcoat', coat),
                       ('Clearcoat Roughness', ccrough)):
        p.inputs[key].default_value = value
    if own:
        # Normal node's normal output, transformed by the GPU node into view space.
        normal = nt.nodes.new('ShaderNodeNormal')
        normal.outputs['Normal'].default_value = (.3, -.5, .81240384)
        nt.links.new(normal.outputs['Normal'], p.inputs['Clearcoat Normal'])
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(p.outputs[0], out.inputs['Surface'])
    return mat


def mesh(name, loc, mat, sphere=True, scale=(1, 1, 1)):
    if sphere:
        bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, size=.72, location=loc)
    else:
        bpy.ops.mesh.primitive_cube_add(radius=1, location=loc)
    ob = bpy.context.object
    ob.name = name
    ob.scale = scale
    ob.game.physics_type = 'STATIC'
    ob.data.materials.append(mat)
    for poly in ob.data.polygons:
        poly.use_smooth = sphere
    return ob


def world(scene, variant):
    w = bpy.data.worlds.new('BSDF_'+variant)
    scene.world = w
    w.mist_settings.use_mist = False
    w.use_nodes = True
    w.node_tree.nodes.clear()
    bg = w.node_tree.nodes.new('ShaderNodeBackground')
    bg.inputs['Color'].default_value = (0, 0, 0, 1) if variant == 'sun' else (1, 1, 1, 1)
    output = w.node_tree.nodes.new('ShaderNodeOutputWorld')
    w.node_tree.links.new(bg.outputs[0], output.inputs[0])
    w.light_settings.use_environment_light = variant != 'sun'
    w.light_settings.environment_energy = 1
    w.light_settings.environment_color = 'SKY_TEXTURE'
    if variant in ('hdri_ssgi', 'lightmap', 'clearcoat'):
        # Deterministic linear HDR studio map, packed as float OpenEXR, no external dependency.
        image = bpy.data.images.new('BSDF_studio', 128, 64, float_buffer=True)
        px = []
        for y in range(64):
            for x in range(128):
                bright = 10 if (12 < x < 28 and 28 < y < 53) else .12
                px.extend((bright, bright*.85, bright*.65, 1))
        image.pixels[:] = px
        image.filepath_raw = os.path.join(DEST, 'bsdf_studio.exr')
        image.file_format = 'OPEN_EXR'
        image.save()
        image.pack()
        env = w.node_tree.nodes.new('ShaderNodeTexEnvironment')
        env.image = image
        w.node_tree.links.new(env.outputs['Color'], bg.inputs['Color'])


def logic(scene):
    text = bpy.data.texts.new('bsdf_probe.py')
    text.write('''import json, os, time
import Range
def tick(cont):
    own = cont.owner
    now = time.perf_counter()
    if not own.get('started', False):
        own['started'] = True
        own['start'] = now
        own['frames'] = 0
    own['frames'] += 1
    seconds = float(os.environ.get('BSDF_SECONDS', '0'))
    shot = os.environ.get('BSDF_SHOT')
    if shot and seconds > 0 and not own.get('shot') and now-own['start'] >= seconds-1:
        own['shot'] = True
        Range.render.makeScreenshot(shot)
    if seconds > 0 and now-own['start'] >= seconds:
        path = os.environ.get('BSDF_LOG')
        if path:
            with open(path, 'w') as f:
                json.dump({'scene': Range.logic.getCurrentScene().name,
                           'frames': own['frames'], 'elapsed': now-own['start'],
                           'logic_only': '--server' in __import__('sys').argv}, f)
        Range.logic.endGame()
''')
    cam = scene.camera
    scene.objects.active = cam
    bpy.ops.logic.sensor_add(type='ALWAYS', name='EveryFrame', object=cam.name)
    sensor = cam.game.sensors[-1]
    sensor.use_pulse_true_level = True
    bpy.ops.logic.controller_add(type='PYTHON', name='Probe', object=cam.name)
    controller = cam.game.controllers[-1]
    controller.mode = 'MODULE'
    controller.module = 'bsdf_probe.tick'
    sensor.link(controller)


def build(variant):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.name = 'BSDF_'+variant
    sc['bsdf_variant'] = variant
    sc.render.engine = 'BLENDER_GAME'
    gs = sc.game_settings
    gs.use_shading_nodes = True
    gs.resolution_x, gs.resolution_y = 960, 640
    gs.vsync = 'OFF'
    gs.use_frame_rate = False
    sc['ae_ssgi_use'] = variant == 'hdri_ssgi'
    sc['ae_ssgi_rays'], sc['ae_ssgi_steps'] = 8, 16
    sc['ae_ssgi_radius'], sc['ae_ssgi_divisor'] = 4., 2
    sc['ae_ssgi_strength'], sc['ae_ssgi_denoise'] = 1., 1
    names = sc.view_settings.bl_rna.properties['view_transform'].enum_items.keys()
    sc.view_settings.view_transform = 'Standard' if 'Standard' in names else 'Default'
    sc.view_settings.exposure, sc.view_settings.gamma = 0, 1
    world(sc, variant)
    if variant == 'clearcoat':
        for own in (False, True):
            for row, coat in enumerate((0., .5, 1.)):
                for col, rough in enumerate((0., .1, .5, 1.)):
                    name = 'coat%g_r%g_normal%d' % (coat, rough, own)
                    mesh(name, ((col-1.5)*2, (row+3*own)*2, .8),
                         material(name, .3, .6, coat=coat, ccrough=rough, own=own))
    else:
        for dist_idx, dist in enumerate(('GGX', 'MULTI_GGX')):
            for row, metal in enumerate((0., .5, 1.)):
                for col, rough in enumerate((.1, .35, .65, 1.)):
                    name = '%s_m%g_r%g' % (dist, metal, rough)
                    mesh(name, ((col-1.5)*2, (row+3*dist_idx)*2, .8),
                         material(name, rough, metal, dist))
    if variant != 'furnace':
        mesh('Ground', (0, 5, -.2), material('Ground', 1), False, (6, 7, .2))
        lamp = bpy.data.lamps.new('Sun', 'SUN')
        lamp.energy = .6
        lamp.use_shadow = True
        ob = bpy.data.objects.new('Sun', lamp)
        sc.objects.link(ob)
        ob.rotation_euler = Vector((-.7, .4, -1)).to_track_quat('-Z', 'Y').to_euler()
    cam = bpy.data.objects.new('Camera', bpy.data.cameras.new('Camera'))
    sc.objects.link(cam)
    cam.location = (0, -10, 12)
    cam.data.lens = 24
    cam.rotation_euler = (Vector((0, 5, .5))-cam.location).to_track_quat('-Z', 'Y').to_euler()
    sc.camera = cam
    logic(sc)
    if variant == 'lightmap':
        # Produce two actual bake modes from identical geometry/materials.
        for mode in ('AO', 'INDIRECT'):
            settings = sc.ae_lightmap_settings
            settings.mode, settings.resolution = mode, '256'
            settings.samples, settings.use_gpu, settings.use_volume = 8, False, False
            assert 'FINISHED' in bpy.ops.scene.ae_lightmap_bake()
            sc['bsdf_bake_mode'] = mode
            path = os.path.join(DEST, 'bsdf_lightmap_'+mode.lower()+'.range')
            bpy.ops.wm.save_as_mainfile(filepath=path, check_existing=False)
    else:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(DEST, 'bsdf_'+variant+'.range'), check_existing=False)


def inspect():
    sc = bpy.context.scene
    variant = sc['bsdf_variant']
    assert sc.render.engine == 'BLENDER_GAME' and sc.game_settings.use_shading_nodes
    assert sc.camera and len([o for o in sc.objects if o.type == 'MESH']) >= 24
    assert sc.camera.game.controllers[-1].module == 'bsdf_probe.tick'
    assert 'def tick(cont):' in bpy.data.texts['bsdf_probe.py'].as_string()
    assert sc.camera.game.sensors[-1].controllers
    materials = []
    for ob in sc.objects:
        if ob.type != 'MESH':
            continue
        assert ob.data.materials
        p = next(n for n in ob.data.materials[0].node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
        assert p.outputs[0].is_linked
        materials.append({'object':ob.name,'distribution':p.distribution,
                          'roughness':p.inputs['Roughness'].default_value,
                          'coat':p.inputs['Clearcoat'].default_value,
                          'coat_normal_linked':p.inputs['Clearcoat Normal'].is_linked})
    if variant == 'furnace':
        assert not any(o.type == 'LAMP' for o in sc.objects)
    if variant == 'lightmap':
        assert sc.ae_lightmap_use
        image = bpy.data.images[sc.ae_lightmap]
        assert image.size[0] == 256 and image.packed_file
        assert all('Lightmap' in ob.data.uv_layers for ob in sc.objects if ob.type == 'MESH')
    path = os.path.join(DEST, os.path.basename(bpy.data.filepath)+'.inspect.json')
    with open(path,'w') as f:
        json.dump({'scene':sc.name,'variant':variant,'camera':sc.camera.name,
                   'materials':materials,'validated':True},f,indent=2)
    print('BSDF_INSPECTION_OK', path)


if len(ARGS) > 1 and ARGS[1] == 'inspect':
    inspect()
else:
    for variant in VARIANTS:
        build(variant)
