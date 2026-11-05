# SPDX-License-Identifier: GPL-2.0-or-later
"""Web load benchmark scene: 6 cubes, each with a 2048 color + 2048 tangent normal map.
Prepares the textures, then exports the Web package once per container (KTX2 and DDS).
Run: AnastacioEngine -b --factory-startup --python this.py -- output_directory
Result: output_directory/web_ktx2 and output_directory/web_dds.
"""
import os
import sys
import bpy
import numpy as np
from mathutils import Vector
from bl_operators import anastacio_prepare_textures as dds

SIZE = 2048
CUBES = 6
folder = os.path.abspath(sys.argv[sys.argv.index('--') + 1])
os.makedirs(folder, exist_ok=True)
scene = bpy.context.scene
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
for collection in (bpy.data.materials, bpy.data.textures, bpy.data.images):
    for block in list(collection):
        collection.remove(block)
scene.render.engine = 'BLENDER_GAME'
scene.world = scene.world or bpy.data.worlds.new('World')
scene.world.mist_settings.use_mist = False
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(folder, 'carga.range'))

rng = np.random.RandomState(7)
yy, xx = np.mgrid[0:SIZE, 0:SIZE] / float(SIZE)


def new_image(name, pixels, non_color):
    image = bpy.data.images.new(name, SIZE, SIZE, alpha=False)
    if non_color:
        # Before the pixels: changing it later regenerates the image and drops them.
        image.colorspace_settings.name = 'Non-Color'
    image.pixels = pixels.reshape(-1).tolist()
    image.filepath_raw = os.path.join(folder, name + '.png')
    image.file_format = 'PNG'
    image.save()
    image.pack()
    return image


for i in range(CUBES):
    # Color: stripes + grain, so the encoders have real detail to keep.
    grain = rng.rand(SIZE, SIZE).astype(np.float32) * .25
    color = np.ones((SIZE, SIZE, 4), dtype=np.float32)
    hue = np.array([(i * .37) % 1, (i * .61) % 1, (i * .83) % 1], dtype=np.float32)
    stripes = (np.sin(xx * 6.2831853 * (8 + i)) * .5 + .5).astype(np.float32)
    for c in range(3):
        color[..., c] = np.clip(hue[c] * .6 + stripes * .3 + grain, 0, 1)
    color_image = new_image('Color%d' % i, color, False)

    nx = .5 * np.sin(xx * 6.2831853 * (4 + i))
    ny = .5 * np.sin(yy * 6.2831853 * (4 + i))
    nz = np.sqrt(np.clip(1 - nx * nx - ny * ny, 0, 1))
    normal = np.ones((SIZE, SIZE, 4), dtype=np.float32)
    normal[..., 0], normal[..., 1], normal[..., 2] = nx * .5 + .5, ny * .5 + .5, nz * .5 + .5
    normal_image = new_image('Normal%d' % i, normal, True)

    mat = bpy.data.materials.new('Mat%d' % i)
    mat.diffuse_color = (.8, .8, .8)
    tex = bpy.data.textures.new('Color%d' % i, 'IMAGE')
    tex.image = color_image
    slot = mat.texture_slots.add()
    slot.texture = tex
    slot.texture_coords = 'UV'
    tex = bpy.data.textures.new('Normal%d' % i, 'IMAGE')
    tex.image = normal_image
    tex.use_normal_map = True
    slot = mat.texture_slots.add()
    slot.texture = tex
    slot.texture_coords = 'UV'
    slot.use_map_color_diffuse = False
    slot.use_map_normal = True
    slot.normal_map_space = 'TANGENT'

    bpy.ops.mesh.primitive_cube_add(radius=1, location=(-5 + (i % 3) * 5, (i // 3) * 5, 1), calc_uvs=True)
    cube = scene.objects.active
    cube.name = 'Cube%d' % i
    cube.game.physics_type = 'NO_COLLISION'
    cube.data.materials.append(mat)
    for image in (color_image, normal_image):
        assert dds.skip_reason(image) == '', dds.skip_reason(image)
        dds.prepare_image(image, SIZE, 0)
    print('CUBE', i, flush=True)

lamp = bpy.data.lamps.new('Sun', 'SUN')
obj = bpy.data.objects.new('Sun', lamp)
scene.objects.link(obj)
obj.rotation_euler = (.4, -.6, -.2)
camera = bpy.data.objects.new('Camera', bpy.data.cameras.new('Camera'))
scene.objects.link(camera)
camera.location = (0, -14, 9)
camera.rotation_euler = (Vector((0, 2.5, 1)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
scene.camera = camera
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(folder, 'carga.range'))

web = scene.range_web
for container in ('KTX2', 'DDS'):
    web.texture_format = container
    web.output_directory = os.path.join(folder, 'web_' + container.lower())
    print('WEB_EXPORT', container, bpy.ops.scene.range_web_export(), flush=True)
print('WEB_LOAD_SCENE_CREATED')
