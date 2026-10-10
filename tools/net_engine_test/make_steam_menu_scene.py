"""Create a minimal reusable-component scene; no user game data is saved."""
import bpy
import sys
bpy.ops.wm.read_factory_settings(use_empty=True)
scene=bpy.context.scene
scene.render.engine='BLENDER_GAME'
scene.world=bpy.data.worlds.new('World')
cam=bpy.data.objects.new('Camera', bpy.data.cameras.new('Camera'))
scene.objects.link(cam)
scene.camera=cam
scene.objects.active=cam
cam.select=True
result=bpy.ops.logic.python_component_register(component_name='anastacio_network.component.AnastacioNetworkComponent')
assert result == {'FINISHED'}
component=cam.game.components[0]
assert component.name == 'AnastacioNetworkComponent'
assert len(component.properties) >= 10
bpy.ops.wm.save_as_mainfile(filepath=sys.argv[sys.argv.index('--')+1])
print('STEAMMENU author PASS',flush=True)
