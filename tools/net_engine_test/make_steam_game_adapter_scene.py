import bpy
from pathlib import Path
root=Path(__file__).resolve().parents[2]/'build-steam/game-adapter-probe'
bpy.ops.wm.read_factory_settings(use_empty=True)
# Component validation resolves the actual copied game adapters without changing the game asset.
bpy.ops.wm.save_as_mainfile(filepath=str(root/'adapter.range'))
scene=bpy.context.scene
scene.name='0_SCN_System';scene.render.engine='BLENDER_GAME'
scene.world=bpy.data.worlds.new('World')
cam=bpy.data.objects.new('Camera',bpy.data.cameras.new('Camera'))
scene.objects.link(cam);scene.camera=cam;scene.objects.active=cam;cam.select=True
for name in ('scripts.SteamComponent.SteamComponent','scripts.NetworkManager.NetworkManager','scripts.net_menu.NetworkMenu'):
    assert bpy.ops.logic.python_component_register(component_name=name)=={'FINISHED'}
import sys
assert 'anastacio_network.component' not in sys.modules, 'fake Range helper cached'
track=bpy.data.scenes.new('Pista_1');track.render.engine='BLENDER_GAME';track.world=scene.world
track.objects.link(cam.copy());track.camera=track.objects[0]
bpy.ops.wm.save_as_mainfile(filepath=str(root/'adapter.range'))
print('STEAMGAME author PASS',flush=True)
