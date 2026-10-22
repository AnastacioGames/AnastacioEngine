# SPDX-License-Identifier: GPL-2.0-or-later
"""Run after criar_cena_dds.py created OUTPUT/project/data/dds-source.range.
Open that source in the editor in background; pass OUTPUT after --.
"""
import bpy, json, os, sys
from bl_operators.wm import _rangearmor_write_export_preset, _RANGEARMOR_DEFAULT_FIELDS
from bl_operators import anastacio_prepare_textures as dds
folder=os.path.abspath(sys.argv[sys.argv.index('--')+1])
project=os.path.join(folder,'project')
config=dict(_RANGEARMOR_DEFAULT_FIELDS)
config['GameName']='DDS Validation'
config['ExportLinux64']=False
config_path=os.path.join(project,'launcher','config.json')
with open(config_path,'w') as stream:json.dump(config,stream,indent=2)
assert _rangearmor_write_export_preset(bpy.context)
assert all(bpy.data.images[n].packed_file.data[:8]==b'\x89PNG\r\n\x1a\n' for n in ('ColorOpaque','ColorAlpha'))
# The universal/runtime exporter must include DDS bytes without changing the source.
sys.path.insert(0, os.path.join(os.path.dirname(bpy.app.binary_path), '2.79', 'scripts', 'addons'))
import game_engine_save_as_runtime as exporter
out=os.path.join(folder,'runtime-package','DDSGame.exe')
if os.path.exists(os.path.dirname(out)):
    raise RuntimeError('Use a fresh validation output directory')
os.makedirs(os.path.dirname(out))
player=os.path.join(os.path.dirname(bpy.app.binary_path),'AnastacioRuntime.exe')
assert exporter.WriteRuntime(player,out,True,False,True,False,True)
assert os.path.isfile(os.path.join(os.path.dirname(out),'blender.crt','blender.crt.manifest'))
assert os.path.isfile(os.path.join(os.path.dirname(out),'rgbcx-license.txt'))
assert all(bpy.data.images[n].packed_file.data[:8]==b'\x89PNG\r\n\x1a\n' for n in ('ColorOpaque','ColorAlpha'))
with open(os.path.join(folder,'exporters-results.json'),'w') as stream:json.dump({'rangearmor':True,'runtime':True,'originals_restored':True},stream)
print('DDS_EXPORTERS_VALIDATED')
