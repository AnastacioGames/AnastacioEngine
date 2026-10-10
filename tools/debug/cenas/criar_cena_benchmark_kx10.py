"""KX10 static Auto Shadow benchmark (1600 casters, 16 Point lights).
Generate: AnastacioEngine.exe -b --factory-startup --python <this> -- <scene.range>
Run: set BENCH_LOG to a fresh JSON path, then AnastacioRuntime.exe <scene.range>.
Discards 3 s warmup, measures 10 s, exits automatically. Vsync off; logic 1000 Hz.
Use RANGE_PROFILE separately for render.shadows; leave it off for FPS comparisons.
"""
import bpy,sys
from mathutils import Vector
out=sys.argv[sys.argv.index('--')+1]
s=bpy.context.scene
for o in list(s.objects): bpy.data.objects.remove(o,do_unlink=True)
s.render.engine='BLENDER_GAME'; s.game_settings.use_frame_rate=False; s.game_settings.vsync='OFF'
s.render.resolution_x=640; s.render.resolution_y=360; s.render.resolution_percentage=100
m=bpy.data.materials.new('Casters'); m.diffuse_color=(0.8,0.2,0.1)
bpy.ops.mesh.primitive_cube_add(radius=.2,location=(0,0,0)); first=bpy.context.object; first.data.materials.append(m); first.game.physics_type='NO_COLLISION'
for i in range(1599):
 o=first.copy(); o.data=first.data; s.objects.link(o); o.location=((i%40-20)*.7,(i//40-20)*.7,0)
for i in range(16):
 l=bpy.data.objects.new('Shadow%d'%i,bpy.data.lamps.new('Shadow%d'%i,'POINT')); s.objects.link(l); l.location=((i%4-2)*2,(i//4-2)*2,5); l.data.distance=50; l.data.use_shadow=True; l.data.use_auto_shadow_update=True
sun=bpy.data.objects.new('Sun',bpy.data.lamps.new('Sun','SUN')); s.objects.link(sun); sun.rotation_euler=(.5,.3,0)
if s.world is None: s.world=bpy.data.worlds.new('World')
s.world.mist_settings.use_mist=False
cam=bpy.data.objects.new('Camera',bpy.data.cameras.new('Camera')); s.objects.link(cam); s.camera=cam; cam.location=(0,-32,30); cam.data.lens=16; cam.rotation_euler=(Vector((0,0,0))-cam.location).to_track_quat('-Z','Y').to_euler()
t=bpy.data.texts.new('bench.py'); t.write('''import bge,time,os,json
start=None
samples=[]
def tick(cont):
 global start
 now=time.perf_counter()
 if start is None:
  start=now
  bge.logic.setLogicTicRate(1000)
  bge.logic.setMaxLogicFrame(1)
 elapsed=now-start
 if elapsed>=3:
  st=dict(bge.logic.getRenderStats())
  samples.append((now,st['shadowPasses'],st['lightsShadowUpdated']))
 if elapsed>=13:
  with open(os.environ['BENCH_LOG'],'w') as f: json.dump(dict(samples=len(samples),seconds=samples[-1][0]-samples[0][0],fps=(len(samples)-1)/(samples[-1][0]-samples[0][0]),passes=max(x[1] for x in samples),updated=max(x[2] for x in samples)),f)
  bge.logic.endGame()
''')
s.objects.active=cam
bpy.ops.logic.sensor_add(type='ALWAYS',object=cam.name); bpy.ops.logic.controller_add(type='PYTHON',object=cam.name)
a=cam.game.sensors[0]; a.use_pulse_true_level=True; c=cam.game.controllers[0]; c.mode='MODULE'; c.module='bench.tick'; a.link(c)
bpy.ops.wm.save_as_mainfile(filepath=out)
