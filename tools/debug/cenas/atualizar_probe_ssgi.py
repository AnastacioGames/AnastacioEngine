"""Refresh only the probe Text of a generated SSGI test scene; never use on a user's game."""
import bpy
import os

assert 'ssgi_test_mode' in bpy.context.scene
source = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ssgi_runtime_probe.py')
with open(source, encoding='utf-8') as handle:
    code = handle.read()
text = bpy.data.texts['ssgi_runtime_probe.py']
text.clear()
text.write(code)
bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath, check_existing=False)
