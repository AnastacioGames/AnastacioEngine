"""Verify legacy native runtime export with optional Steam and engine component."""
import bpy
import importlib.util
from pathlib import Path
root=Path(__file__).resolve().parents[2]
bpy.ops.wm.open_mainfile(filepath=str(root/'build-steam/steam_menu.range'))
path=root/'source/release/scripts/addons/game_engine_save_as_runtime.py'
spec=importlib.util.spec_from_file_location('anastacio_export_smoke',str(path))
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
out=root/'build-steam/export-test'
out.mkdir(exist_ok=True)
if (out/'steam_appid.txt').exists(): (out/'steam_appid.txt').unlink()
assert module.WriteRuntime(str(root/'build/bin/RangeRuntime.exe'),str(out/'Game.exe'),True,True,True,False,False,
                    steam_complement_dir=str(root/'build-steam'))
assert (out/'Game.exe').is_file()
assert (out/'blender.crt/blender.crt.manifest').is_file()
assert (out/'python311.dll').is_file()
assert (out/'2.79/python/lib/encodings/__init__.py').is_file()
assert (out/'2.79/scripts/modules/anastacio_network/component.py').is_file()
assert (out/'complements/steam/AnastacioSteam.dll').is_file()
assert not (out/'steam_appid.txt').exists()
# Add the development AppID explicitly for this local smoke test only.
(out/'steam_appid.txt').write_text('480\n',encoding='ascii')

lan=root/'build-steam/export-lan'
lan.mkdir(exist_ok=True)
assert module.WriteRuntime(str(root/'build/bin/RangeRuntime.exe'),str(lan/'Game.exe'),True,True,True,False,False)
assert not (lan/'complements/steam/AnastacioSteam.dll').exists()
print('STEAMEXPORT author PASS (Steam selected and LAN without Steam)',flush=True)

