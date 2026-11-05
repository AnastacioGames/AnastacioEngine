# SPDX-License-Identifier: GPL-2.0-or-later
"""KTX2 runtime scene: the DDS test scene with its three textures packed as KTX2 (Basis Universal).
Run criar_cena_dds.py first, then:
  AnastacioEngine -b <dir>/dds-source.range --python this.py -- <dir>
Writes <dir>/ktx2-test.range. The player's probe (dds_probe.py from the DDS scene) records GL formats:
  ANASTACIO_KTX2_TARGET=bc|etc2|astc|rgba DDS_TEST_OUTPUT=out.json AnastacioRuntime ktx2-test.range
"""
import json
import os
import sys
import bpy

folder = os.path.abspath(sys.argv[sys.argv.index('--') + 1])
sizes = {}
for name, normal in (('ColorOpaque', False), ('ColorAlpha', False), ('BumpNormal', True)):
    image = bpy.data.images[name]
    path = os.path.join(folder, name + '.ktx2')
    image.save_ktx2(filepath=path, normal=normal, max_size=0, quality=75, srgb=not normal)
    data = open(path, 'rb').read()
    assert data[:12] == b'\xabKTX 20\xbb\r\n\x1a\n', name
    # same swap as the prepared-texture export: fresh packed image, users remapped
    ktx = bpy.data.images.load(path, check_existing=False)
    ktx.colorspace_settings.name = image.colorspace_settings.name
    ktx.alpha_mode = 'STRAIGHT'
    ktx.use_alpha = image.use_alpha
    ktx.use_clamp_x, ktx.use_clamp_y = image.use_clamp_x, image.use_clamp_y
    ktx.pack()
    image.user_remap(ktx)
    image.name = '__source_' + name
    ktx.name = name
    bpy.data.images.remove(image)
    assert bytes(bpy.data.images[name].packed_file.data[:4]) == b'\xabKTX'
    sizes[name] = len(data)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(folder, 'ktx2-test.range'), copy=True)
with open(os.path.join(folder, 'ktx2-created.json'), 'w') as stream:
    json.dump(sizes, stream)
print('KTX2_SCENE_CREATED', sizes)
