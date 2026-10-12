"""Native SSGI integration scene. Usage: editor -b --factory-startup --python this.py -- out.range [mode].
mode: standard (default), filmic, baked, disabled, emissive. Runtime logs go to SSGI_TEST_LOG.
No screenshots: numerical buffer checks and shader errors only; appearance needs real-game validation.
"""
import bpy
import sys
import os
from mathutils import Vector

args = sys.argv[sys.argv.index('--') + 1:]
destination = os.path.abspath(args[0])
mode = args[1] if len(args) > 1 else 'standard'
scene = bpy.context.scene
for ob in list(scene.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.use_shading_nodes = True
scene.game_settings.resolution_x = 640
scene.game_settings.resolution_y = 480
scene.game_settings.vsync = 'OFF'
scene.game_settings.use_frame_rate = False
scene['ae_ssgi_use'] = mode != 'disabled'
scene['ae_ssgi_rays'] = 16 if mode == 'emissive' else 8
scene['ae_ssgi_steps'] = 24 if mode == 'emissive' else 16
scene['ae_ssgi_radius'] = 3.0 if mode == 'emissive' else 5.0
scene['ae_ssgi_divisor'] = 2
scene['ae_ssgi_thickness'] = 0.15
scene['ae_ssgi_strength'] = 1.0
scene['ssgi_test_mode'] = mode
view_names = scene.view_settings.bl_rna.properties['view_transform'].enum_items.keys()
scene.view_settings.view_transform = 'Filmic' if mode == 'filmic' else ('Standard' if 'Standard' in view_names else 'Default')
scene.view_settings.exposure = 0
scene.view_settings.gamma = 1
world = bpy.data.worlds.new('SSGI Test World')
world.horizon_color = (0, 0, 0)
world.mist_settings.use_mist = False
world.light_settings.use_environment_light = False
scene.world = world


def material(name, rgba, metal=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    for node in list(mat.node_tree.nodes):
        mat.node_tree.nodes.remove(node)
    shader = mat.node_tree.nodes.new('ShaderNodeBsdfPrincipled')
    shader.inputs['Base Color'].default_value = rgba
    shader.inputs['Metallic'].default_value = metal
    output = mat.node_tree.nodes.new('ShaderNodeOutputMaterial')
    mat.node_tree.links.new(shader.outputs[0], output.inputs['Surface'])
    return mat


def diffuse_material(name, rgba):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    for node in list(mat.node_tree.nodes):
        mat.node_tree.nodes.remove(node)
    shader = mat.node_tree.nodes.new('ShaderNodeBsdfDiffuse')
    shader.inputs['Color'].default_value = rgba
    output = mat.node_tree.nodes.new('ShaderNodeOutputMaterial')
    mat.node_tree.links.new(shader.outputs[0], output.inputs['Surface'])
    return mat


def legacy_material(name, rgba):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = False
    mat.diffuse_color = rgba[:3]
    return mat


def cube(name, loc, scale, mat):
    bpy.ops.mesh.primitive_cube_add(radius=1, location=loc)
    ob = scene.objects.active
    ob.name = name
    ob.scale = scale
    ob.data.materials.append(mat)
    ob.game.physics_type = 'STATIC'
    return ob


green = material('GreenGround', (0.05, 0.7, 0.05, 1))
red = material('RedWall', (0.8, 0.02, 0.02, 1))
white = diffuse_material('WhiteWallDiffuse', (0.7, 0.7, 0.7, 1))
metal = material('Metal', (0.7, 0.7, 0.7, 1), 1.0)
legacy = legacy_material('LegacyOrange', (0.8, 0.25, 0.03, 1))
cube('Ground', (0, 0, -0.1), (4, 4, 0.1), green)
cube('RedWall', (-1.5, 0, 1.5), (0.1, 2.5, 1.5), red)
cube('WhiteWall', (0, 2.6, 1.5), (3, 0.1, 1.5), white)
cube('MetalCube', (1.5, 0, 0.6), (0.6, 0.6, 0.6), metal)
cube('LegacyCube', (-0.5, -1.5, 0.45), (0.45, 0.45, 0.45), legacy)
unsupported = bpy.data.materials.new('UnsupportedEmission')
unsupported.use_nodes = True
for node in list(unsupported.node_tree.nodes):
    unsupported.node_tree.nodes.remove(node)
emission = unsupported.node_tree.nodes.new('ShaderNodeEmission')
emission.inputs['Color'].default_value = (0.02, 0.05, 0.8, 1)
out = unsupported.node_tree.nodes.new('ShaderNodeOutputMaterial')
unsupported.node_tree.links.new(emission.outputs[0], out.inputs[0])
cube('UnsupportedCube', (1, -2, 0.4), (0.4, 0.4, 0.4), unsupported)
if mode == 'emissive':
    # The blue panel is the only light source.  It is placed beside, not in front
    # of, the eligible white wall so the probe can isolate bounced blue light.
    panel = bpy.data.materials.new('BlueEmissionPanel')
    panel.use_nodes = True
    for node in list(panel.node_tree.nodes):
        panel.node_tree.nodes.remove(node)
    panel_emission = panel.node_tree.nodes.new('ShaderNodeEmission')
    panel_emission.inputs['Color'].default_value = (0.01, 0.08, 1.0, 1.0)
    panel_emission.inputs['Strength'].default_value = 8.0
    panel_output = panel.node_tree.nodes.new('ShaderNodeOutputMaterial')
    panel.node_tree.links.new(panel_emission.outputs[0], panel_output.inputs['Surface'])
    cube('BlueEmissionPanel', (1.8, 1.8, 1.5), (0.55, 0.05, 1.0), panel)
else:
    lamp = bpy.data.lamps.new('Sun', 'SUN')
    lamp.energy = 1.0
    sun = bpy.data.objects.new('Sun', lamp)
    scene.objects.link(sun)
    sun.rotation_euler = Vector((-1, 0.5, -2)).to_track_quat('-Z', 'Y').to_euler()
for name, kind in (('Camera', 'PERSP'), ('OrthoCamera', 'ORTHO')):
    cam = bpy.data.objects.new(name, bpy.data.cameras.new(name))
    scene.objects.link(cam)
    cam.location = (7, -9, 6)
    cam.rotation_euler = (Vector((0, 0, 1)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    cam.data.type = kind
    cam.data.lens = 28
    cam.data.ortho_scale = 12
    cam.data.clip_end = 100
scene.camera = scene.objects['Camera']

if mode == 'baked':
    # Deterministic contract fixture (not a Cycles quality benchmark): every Lightmap texel is valid.
    image = bpy.data.images.new('SSGI Synthetic Lightmap', 8, 8, alpha=True)
    image.use_fake_user = True  # Scene stores the image name; a string does not keep an orphan datablock alive.
    image.pixels[:] = [0.1, 0.1, 0.1, 1.0] * 64
    image.pack(as_png=True)
    scene['ae_lightmap'] = image.name
    scene['ae_lightmap_use'] = True
    for ob in scene.objects:
        if ob.type == 'MESH':
            ob.data.uv_textures.new(name='Lightmap')
            uv = ob.data.uv_layers['Lightmap']
            for loop in uv.data:
                loop.uv = (0.5, 0.5)

script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ssgi_runtime_probe.py')
with open(script_path, encoding='utf-8') as handle:
    runtime = handle.read()
text = bpy.data.texts.new('ssgi_runtime_probe.py')
text.write(runtime)
camera = scene.camera
scene.objects.active = camera
bpy.ops.logic.sensor_add(type='ALWAYS', name='SSGI Probe', object=camera.name)
bpy.ops.logic.controller_add(type='PYTHON', name='SSGI Probe', object=camera.name)
sensor = camera.game.sensors[-1]
sensor.use_pulse_true_level = True
controller = camera.game.controllers[-1]
controller.mode = 'MODULE'
controller.module = 'ssgi_runtime_probe.tick'
sensor.link(controller)
bpy.ops.wm.save_as_mainfile(filepath=destination, check_existing=False)
print('SSGI scene saved:', destination, mode)
