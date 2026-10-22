"""Test runtime payload and RangeArmor staged copy without launching the game.
Run in background with -- FIXTURE_OUTPUT (from validate_audio_export.py) REPO.
"""
import json
import os
import struct
import sys

import bpy
from bl_operators import anastacio_prepare_audio as audio
from bl_operators import wm

args = sys.argv[sys.argv.index('--') + 1:]
folder, repo = map(os.path.abspath, args[:2])
project = os.path.join(folder, 'source')
source = os.path.join(project, 'data', 'main.range')
library = os.path.join(project, 'data', 'levels', 'library.range')
before = {path: audio._hash(path) for path in (source, library)}
bpy.ops.wm.open_mainfile(filepath=source, use_scripts=False)
os.makedirs(os.path.join(project, 'launcher'), exist_ok=True)
config_path = os.path.join(project, 'launcher', 'config.json')
config = dict(wm._RANGEARMOR_DEFAULT_FIELDS)
config['ExportLinux64'] = False
with open(config_path, 'w') as stream:
    json.dump(config, stream)
assert wm._rangearmor_write_export_preset(bpy.context)
with open(config_path) as stream:
    config = json.load(stream)
assert 'PreparedDataSource' not in config
with open(os.path.join(project, '.anastacio-export', 'current.json')) as stream:
    pointer = json.load(stream)
tree = os.path.join(project, pointer['source'])
assert os.path.isfile(os.path.join(tree, config['MainFile']))
assert os.path.isfile(os.path.join(tree, 'levels', 'library.range'))
sys.path.insert(0, os.path.join(repo, 'tools', 'rangearmor', 'release', 'scripts'))
import common
assert common.getProjectData(config_path)['PreparedDataSource'] == pointer['source']
sys.path.insert(0, os.path.join(os.path.dirname(bpy.app.binary_path), '2.79', 'scripts', 'addons'))
import game_engine_save_as_runtime as runtime
player = os.path.join(os.path.dirname(bpy.app.binary_path), 'AnastacioRuntime.exe')
# Refuse an output that would replace the user's LibLoad files.
errors = []
assert not runtime.WriteRuntime(player, os.path.join(project, 'data', 'Unsafe.exe'),
    False, False, False, False, False, report=lambda kinds, message: errors.append(message))
assert any('separate folder' in message for message in errors), errors
assert {path: audio._hash(path) for path in before} == before
target = os.path.join(folder, 'runtime', 'Audio.exe')
os.makedirs(os.path.dirname(target), exist_ok=True)
assert runtime.WriteRuntime(player, target, False, False, False, False, False)
with open(target, 'rb') as stream:
    stream.seek(-12, os.SEEK_END)
    footer = stream.read(12)
    assert footer[4:] == b'BRUNTIME', footer
    offset = struct.unpack('>I', footer[:4])[0]
    stream.seek(offset)
    payload = stream.read(os.path.getsize(target) - offset - 12)
assert payload[:7] == b'BLENDER'
with open(os.path.join(os.path.dirname(target), 'main.range'), 'wb') as stream:
    stream.write(payload)
assert os.path.isfile(os.path.join(os.path.dirname(target), 'levels', 'library.range'))
assert {path: audio._hash(path) for path in before} == before
with open(os.path.join(folder, 'exporters-results.json'), 'w') as stream:
    json.dump(dict(ok=True, rangearmor_staged=True, schema_preserved=True,
                   runtime_payload=True, libload=True, overwrite_rejected=True), stream, indent=2)
print('AUDIO_EXPORTERS_OK')
