"""Reopen test scene and check saved data. editor -b scene.range --python this.py -- report.json."""
import bpy
import sys
import json

scene = bpy.context.scene
names = {ob.name for ob in scene.objects}
assert {'Camera', 'OrthoCamera', 'Ground', 'RedWall', 'WhiteWall', 'MetalCube', 'LegacyCube', 'UnsupportedCube', 'Sun'} <= names
assert scene.camera.name == 'Camera'
assert scene.game_settings.use_shading_nodes
assert all(ob.data.materials for ob in scene.objects if ob.type == 'MESH')
assert not bpy.data.materials['LegacyOrange'].use_nodes
controllers = scene.camera.game.controllers
assert any(ctrl.mode == 'MODULE' and ctrl.module == 'ssgi_runtime_probe.tick' for ctrl in controllers)
assert 'def tick(cont):' in bpy.data.texts['ssgi_runtime_probe.py'].as_string()
if scene['ssgi_test_mode'] == 'baked':
    image = bpy.data.images.get(scene['ae_lightmap'])
    assert image and image.use_fake_user and image.pixels[3] > 0.99
    assert scene['ae_lightmap_use']
    assert all('Lightmap' in ob.data.uv_layers for ob in scene.objects if ob.type == 'MESH')
report = dict(scene=scene.name, camera=scene.camera.name, objects=sorted(names),
              mode=scene['ssgi_test_mode'], enabled=bool(scene['ae_ssgi_use']),
              rays=scene['ae_ssgi_rays'], steps=scene['ae_ssgi_steps'])
path = sys.argv[sys.argv.index('--') + 1]
with open(path, 'w') as handle:
    json.dump(report, handle, indent=2)
print('SSGI saved data verified', path)
