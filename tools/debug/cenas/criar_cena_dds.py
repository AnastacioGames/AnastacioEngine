# SPDX-License-Identifier: GPL-2.0-or-later
"""Controlled DDS scene, desktop export and runtime texture-storage inspection.
Run: AnastacioEngine -b --factory-startup --python this.py -- output_directory
"""
import json
import os
import sys
import bpy
import numpy as np
from mathutils import Vector
from bl_operators import anastacio_prepare_textures as dds

folder = os.path.abspath(sys.argv[sys.argv.index('--') + 1])
os.makedirs(folder, exist_ok=True)
scene = bpy.context.scene
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
for collection in (bpy.data.materials, bpy.data.textures, bpy.data.images):
    for block in list(collection):
        collection.remove(block)
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.resolution_x = 640
scene.game_settings.resolution_y = 480
scene.world = scene.world or bpy.data.worlds.new('World')
scene.world.mist_settings.use_mist = False
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(folder, 'dds-source.range'))
for idx, alpha in enumerate((False, True)):
    name = 'ColorAlpha' if alpha else 'ColorOpaque'
    image = bpy.data.images.new(name, 128, 128, alpha=True)
    pixels = np.ones((128, 128, 4), dtype=np.float32)
    pixels[:64, :, :3] = (.05, .1, 1.0)
    pixels[64:, :, :3] = (1.0, .1, .05)
    if alpha:
        pixels[:, :64, 3] = .3
    image.pixels = pixels.reshape(-1).tolist()
    image.filepath_raw = os.path.join(folder, name + '.png')
    image.file_format = 'PNG'
    image.save()
    image.pack()
    image.use_clamp_x = True
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (.8, .8, .8)
    mat.game_settings.alpha_blend = 'ALPHA' if alpha else 'OPAQUE'
    tex = bpy.data.textures.new(name, 'IMAGE')
    tex.image = image
    slot = mat.texture_slots.add()
    slot.texture = tex
    slot.texture_coords = 'UV'
    bpy.ops.mesh.primitive_cube_add(radius=1, location=(-1.6 + idx * 3.2, 0, 1))
    cube = scene.objects.active
    cube.name = name
    cube.game.physics_type = 'NO_COLLISION'
    cube.data.materials.append(mat)
    dds.prepare_image(image, 128, 0)

# White floor distinguishes transparent edges from the colored faces.
mat = bpy.data.materials.new('Floor')
mat.diffuse_color = (.65, .65, .65)
bpy.ops.mesh.primitive_plane_add(radius=8, location=(0, 0, -.05))
scene.objects.active.data.materials.append(mat)
scene.objects.active.game.physics_type = 'NO_COLLISION'
lamp = bpy.data.lamps.new('Sun', 'SUN')
obj = bpy.data.objects.new('Sun', lamp)
scene.objects.link(obj)
obj.rotation_euler = (.4, -.6, -.2)
camera_data = bpy.data.cameras.new('Camera')
camera = bpy.data.objects.new('Camera', camera_data)
scene.objects.link(camera)
camera.location = (4, -8, 5)
camera.rotation_euler = (Vector((0, 0, 1)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
camera.data.lens = 28
scene.camera = camera
scene.objects.active = camera
camera.select = True
text = bpy.data.texts.new('dds_probe.py')
text.write('''import bge, bgl, json, os
frames = 0
def tick(cont):
    global frames
    frames += 1
    if frames < 12:
        return
    rows = []
    for name in ('ColorOpaque', 'ColorAlpha'):
        obj = bge.logic.getCurrentScene().objects[name]
        texture = obj.meshes[0].materials[0].textures[0]
        previous = bgl.Buffer(bgl.GL_INT, 1)
        bgl.glGetIntegerv(bgl.GL_TEXTURE_BINDING_2D, previous)
        bgl.glBindTexture(bgl.GL_TEXTURE_2D, texture.bindCode)
        data = {}
        for key, enum in [('compressed', 0x86a1), ('internal_format', 0x1003), ('width', 0x1000)]:
            buf = bgl.Buffer(bgl.GL_INT, 1)
            bgl.glGetTexLevelParameteriv(bgl.GL_TEXTURE_2D, 0, enum, buf)
            data[key] = int(buf[0])
        # Read mip 1 to prove the file's stored chain is complete and sampleable.
        buf = bgl.Buffer(bgl.GL_INT, 1)
        bgl.glGetTexLevelParameteriv(bgl.GL_TEXTURE_2D, 1, 0x1000, buf)
        data['mip1_width'] = int(buf[0])
        data['name'] = name
        data['gl_error'] = int(bgl.glGetError())
        bgl.glBindTexture(bgl.GL_TEXTURE_2D, previous[0])
        rows.append(data)
    with open(os.environ['DDS_TEST_OUTPUT'], 'w') as stream:
        json.dump(rows, stream, indent=2)
    bge.logic.endGame()
''')
bpy.ops.logic.sensor_add(type='ALWAYS', object=camera.name)
sensor = camera.game.sensors[-1]
sensor.use_pulse_true_level = True
bpy.ops.logic.controller_add(type='PYTHON', object=camera.name)
controller = camera.game.controllers[-1]
controller.mode = 'MODULE'
controller.module = 'dds_probe.tick'
sensor.link(controller)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(folder, 'dds-source.range'))
with dds.export_prepared_textures():
    for image in bpy.data.images:
        if image.name in ('ColorAlpha', 'ColorOpaque'):
            assert image.packed_file.data[:4] == b'DDS '
            assert image.use_clamp_x
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(folder, 'dds-export.range'), copy=True)
    bpy.ops.wm.save_as_mainfile_protected(filepath=os.path.join(folder, 'dds-export.rasec'), copy=True)
with open(os.path.join(folder, 'scene-created.json'), 'w') as stream:
    json.dump({'objects': len(scene.objects), 'camera': scene.camera.name,
               'originals_restored': all(bpy.data.images[n].packed_file.data[:8] == b'\x89PNG\r\n\x1a\n'
                                         for n in ('ColorAlpha', 'ColorOpaque'))}, stream)
print('DDS_SCENE_CREATED')
