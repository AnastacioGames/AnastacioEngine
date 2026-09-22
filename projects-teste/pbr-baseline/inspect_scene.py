import bpy, os
here = os.path.dirname(os.path.abspath(__file__))
bpy.ops.wm.open_mainfile(filepath=os.path.join(here, "game_lights_ibl_sun_point_ibl.blend"))
scn = bpy.context.scene
print('engine', scn.render.engine)
print('cam', scn.camera)
gs = scn.game_settings
print('ibl', gs.use_glsl_environment_lighting, 'shading_nodes', gs.use_shading_nodes, 'shadows', gs.use_glsl_shadows)
for o in scn.objects:
    if len(o.game.sensors) or len(o.game.controllers):
        print('LOGIC ON', o.name, [s.name for s in o.game.sensors], [c.name for c in o.game.controllers])
for t in bpy.data.texts:
    print('TEXT', t.name)
print('exit_key', gs.exit_key)
print('objects', [o.name for o in scn.objects])
