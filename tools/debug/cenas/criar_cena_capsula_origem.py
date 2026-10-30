# Capsula do Character com origem no centro x nos pes, em pe e rastejando: os dois devem ficar no chao.
# Uso: AnastacioEngine.exe -b --factory-startup --python este.py -- saida.range log.txt
import bpy, sys
out, log = sys.argv[sys.argv.index('--')+1:][:2]
sc=bpy.context.scene
for o in list(sc.objects): sc.objects.unlink(o)
sc.render.engine='BLENDER_GAME'
bpy.ops.mesh.primitive_cube_add(location=(0,0,-0.5)); sc.objects.active.scale=(10,10,0.5)
for i,(x,feet) in enumerate(((0,False),(3,True))):
    bpy.ops.mesh.primitive_cylinder_add(radius=0.4, depth=2, location=(x,0,1.05))
    o=sc.objects.active; o.name='C%d'%i
    if feet:
        for v in o.data.vertices: v.co.z+=1
        o.location.z=0.05
    g=o.game; g.physics_type='CHARACTER'; g.use_collision_bounds=True; g.collision_bounds_type='CAPSULE'
bpy.ops.object.camera_add(location=(0,-10,2)); sc.camera=sc.objects.active
t=bpy.data.texts.new('k.py')
t.write("""import bge
f=[0]; L=[]
def tick(cont):
    f[0]+=1
    s=bge.logic.getCurrentScene().objects
    from bge import constraints as K
    if f[0]==30:
        for n in ('C0','C1'): K.getCharacter(s[n]).posture='CRAWL'
    if f[0] in (31,35,40,50,70,89): L.append('%%d centro z=%%.3f %%s  pes z=%%.3f %%s'%%(f[0],s['C0'].worldPosition.z,K.getCharacter(s['C0']).posture,s['C1'].worldPosition.z,K.getCharacter(s['C1']).posture))
    if f[0]==90:
        s=bge.logic.getCurrentScene().objects
        open(%r,'w').write(chr(10).join(L)+chr(10)+'centro z=%%.3f (esperado 1.0)  pes z=%%.3f (esperado 0.0)'%%(s['C0'].worldPosition.z,s['C1'].worldPosition.z))
        bge.logic.endGame()
""" % log)
o=sc.objects['C0']; sc.objects.active=o
bpy.ops.logic.sensor_add(type='ALWAYS',object='C0'); s=o.game.sensors[-1]; s.use_pulse_true_level=True
bpy.ops.logic.controller_add(type='PYTHON',object='C0'); c=o.game.controllers[-1]; c.mode='MODULE'; c.module='k.tick'; s.link(c)
bpy.ops.wm.save_as_mainfile(filepath=out)
