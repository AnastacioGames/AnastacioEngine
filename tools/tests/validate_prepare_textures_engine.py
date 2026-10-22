"""Run with AnastacioEngine -b --factory-startup --python this.py -- output_directory."""
import hashlib
import json
import os
import sys
import struct
import bpy
from bl_operators import anastacio_prepare_textures as dds

folder = os.path.abspath(sys.argv[sys.argv.index('--') + 1])
os.makedirs(folder, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(folder, 'source.range'))

def make_image(name, alpha=False, width=128, height=128):
    image = bpy.data.images.new(name, width, height, alpha=True)
    pixels = []
    for y in range(height):
        for x in range(width):
            pixels.extend((1.0 if y >= height // 2 else 0.0, 0.0,
                           0.0 if y >= height // 2 else 1.0, .25 if alpha and x < width // 2 else 1.0))
    image.pixels = pixels
    image.filepath_raw = os.path.join(folder, name + '.png')
    image.file_format = 'PNG'
    image.save()
    mat = bpy.data.materials.new(name)
    tex = bpy.data.textures.new(name, type='IMAGE')
    tex.image = image
    slot = mat.texture_slots.add()
    slot.texture = tex
    slot.use_map_color_diffuse = True
    return image, mat

results = []
for alpha in (False, True):
    image, mat = make_image('RGBA' if alpha else 'RGB', alpha)
    before = list(image.pixels[:])
    original_path = image.filepath
    path = os.path.join(folder, image.name + '.dds')
    image.save_dds(filepath=path, format='AUTO', max_size=0, quality=0)
    info = dds.dds_info(path)
    assert info[2] == ('DXT5' if alpha else 'DXT1'), info
    loaded = bpy.data.images.load(path, check_existing=False)
    pixels = list(loaded.pixels[:])
    assert pixels[2] > .8 and pixels[0] < .2, pixels[:4]
    assert pixels[-4] > .8 and pixels[-2] < .2, pixels[-4:]
    if alpha:
        assert abs(pixels[3] - .25) < .05, pixels[:4]
    bpy.data.images.remove(loaded)
    assert list(image.pixels[:]) == before and image.filepath == original_path
    reason = dds.skip_reason(image)
    assert not reason, reason
    image.pack()
    image.use_fake_user = True
    packed = bytes(image.packed_file.data)
    info = dds.prepare_image(image, 64, 0)
    assert info[:2] == (64, 64), info
    path = dds.prepared_path(image)
    mtime = os.stat(path).st_mtime_ns
    dds.prepare_image(image, 64, 0)
    assert os.stat(path).st_mtime_ns == mtime, 'Cache unexpectedly regenerated'
    with dds.export_prepared_textures():
        exported = mat.texture_slots[0].texture.image
        assert exported != image
        assert bytes(exported.packed_file.data)[:4] == b'DDS '
        assert exported.name == image.name or exported.name in ('RGB', 'RGBA')
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(folder, 'export.range'), copy=True)
    assert mat.texture_slots[0].texture.image == image
    assert image.use_fake_user
    assert image.filepath == original_path and bytes(image.packed_file.data) == packed
    try:
        with dds.export_prepared_textures():
            raise ValueError('injected save failure')
    except ValueError:
        pass
    assert mat.texture_slots[0].texture.image == image and image.name in ('RGB', 'RGBA')
    results.append({'name': image.name, 'dds': info})
# Premultiplied files are normalized to straight bytes by imbuf, exactly once.
premul, _ = make_image('Premultiplied', alpha=True)
premul.pixels = [.125, .0625, 0.0, .25] * (128 * 128)
premul.save()
premul.alpha_mode = 'PREMUL'
premul.reload()
reference = list(premul.pixels[:4])
assert .45 < reference[0] < .55, reference
premul.save_dds(filepath=os.path.join(folder, 'premul.dds'), quality=0)
loaded = bpy.data.images.load(os.path.join(folder, 'premul.dds'), check_existing=False)
assert abs(loaded.pixels[0] - reference[0]) < .06, (loaded.pixels[:4], reference)
bpy.data.images.remove(loaded)
# A half-black, half-white sRGB mip averages to ~188/255, rather than 128/255.
checker, _ = make_image('MipColor')
checker.pixels = [float((x + y) % 2) if c < 3 else 1.0
                  for y in range(128) for x in range(128) for c in range(4)]
checker.save()
checker.save_dds(filepath=os.path.join(folder, 'mipcolor.dds'), quality=0)
with open(os.path.join(folder, 'mipcolor.dds'), 'rb') as stream:
    stream.seek(-8, os.SEEK_END)
    c0, c1, selectors = struct.unpack('<HHI', stream.read(8))
assert .68 < ((c0 >> 11) & 31) / 31 < .8, c0
# External edits must not convert a stale, clean editor buffer.
external, _ = make_image('ExternalEdit')
old_pixels = list(external.pixels[:4])
changed = bpy.data.images.load(external.filepath, check_existing=False)
changed.pixels = [0.0, 1.0, 0.0, 1.0] * (128 * 128)
changed.file_format = 'PNG'
changed.save()
bpy.data.images.remove(changed)
assert list(external.pixels[:4]) == old_pixels
assert not external.is_dirty
dds.prepare_image(external, 128, 0)
converted = bpy.data.images.load(dds.prepared_path(external), check_existing=False)
assert converted.pixels[1] > .9 and converted.pixels[2] < .1, converted.pixels[:4]
bpy.data.images.remove(converted)
assert list(external.pixels[:4]) == old_pixels

# Failed publication must leave the previously usable cache and mapping intact.
image = bpy.data.images['RGB']
record, cached = image[dds.KEY], dds.prepared_path(image)
old_info = dds.dds_info
try:
    def fail_validation(path):
        raise ValueError('injected DDS validation failure')
    dds.dds_info = fail_validation
    try:
        dds.prepare_image(image, 64, 1)
        raise AssertionError('Failure injection did not run')
    except ValueError:
        pass
finally:
    dds.dds_info = old_info
assert image[dds.KEY] == record and dds.prepared_path(image) == cached
# A modified derivative is left out: the export keeps the original image.
with open(cached, 'rb') as stream:
    original_dds = stream.read()
try:
    with open(cached, 'ab') as stream:
        stream.write(b'corruption')
    kept = image.name
    with dds.export_prepared_textures():
        assert bpy.data.images[kept] == image, 'Corrupted cache accepted'
finally:
    with open(cached, 'wb') as stream:
        stream.write(original_dds)
image.pixels[0] = .25
assert image.is_dirty
try:
    dds.prepare_image(image)
    raise AssertionError('Dirty pixels accepted')
except ValueError:
    pass
image.reload()
normal, normal_mat = make_image('ColorUsedAsNormal')
normal_mat.texture_slots[0].use_map_normal = True
assert dds.skip_reason(normal)
normal_mat.texture_slots[0].use_map_normal = False
normal_mat.texture_slots[0].use_map_roughness = True
assert dds.skip_reason(normal)
normal.colorspace_settings.name = 'Non-Color'
assert dds.skip_reason(normal)
assert bpy.ops.game.prepare_textures.poll()

image, _ = make_image('npot', width=100)
assert 'power-of-two' in dds.skip_reason(image)
try:
    image.save_dds(filepath=os.path.join(folder, 'npot.dds'))
    raise AssertionError('NPOT accepted')
except RuntimeError:
    pass
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(folder, 'source.range'))
with open(os.path.join(folder, 'api-results.json'), 'w') as stream:
    json.dump(results, stream, indent=2)
print('DDS_API_VALIDATED')
