# Cena: personagens (Character + Capsule) com origem fora do centro da malha.
# Uso: AnastacioEngine.exe -b --factory-startup --python este.py -- saida.range log.txt
import bpy, sys
from mathutils import Vector
out, log = sys.argv[sys.argv.index('--')+1:][:2]
sc = bpy.context.scene
for o in list(sc.objects): sc.objects.unlink(o)
sc.render.engine = 'BLENDER_GAME'
def mat(n, c):
    m = bpy.data.materials.new(n); m.diffuse_color = c; return m
bpy.ops.mesh.primitive_plane_add(radius=10, location=(0,0,0))
chao = sc.objects.active; chao.data.materials.append(mat('chao',(0.3,0.6,0.3)))
chao.game.physics_type = 'STATIC'
def boneco(nome, x, desloc, cor):
    bpy.ops.mesh.primitive_cylinder_add(radius=0.4, depth=2.0, location=(x,0,0))
    o = sc.objects.active; o.name = nome
    for v in o.data.vertices: v.co.z += desloc   # origem fora do centro
    o.location.z = 3.0
    o.data.materials.append(mat(nome, cor))
    o.game.physics_type = 'CHARACTER'
    o.game.use_collision_bounds = True
    o.game.collision_bounds_type = 'CAPSULE'
    o.game.collision_margin = 0.0
boneco('Pes', -1.5, 1.0, (0.9,0.2,0.2))      # origem nos pés
boneco('Cabeca', 1.5, -1.0, (0.2,0.3,0.9))  # origem na cabeça
boneco('Centro', 0.0, 0.0, (0.9,0.8,0.2))   # controle
t = bpy.data.texts.new('medir.py')
t.write('''import bge, time
def tick(cont):
    sc = bge.logic.getCurrentScene(); own = cont.owner
    own['n'] = own.get('n', 0) + 1
    if own['n'] < 180: return
    with open(%r, 'w') as f:
        for o in sc.objects:
            if o.name in ('Pes','Cabeca','Centro'):
                zs = [o.meshes[0].getVertex(0,i).XYZ.z for i in range(o.meshes[0].getVertexArrayLength(0))]
                f.write('%%s base_malha=%%.3f\n' %% (o.name, o.worldPosition.z + min(zs)))
        f.write('# fim\n')
    bge.logic.endGame()
''' % log)
bpy.ops.object.camera_add(location=(0,-9,3)); cam = sc.objects.active
cam.rotation_euler = (Vector((0,0,1)) - cam.location).to_track_quat('-Z','Y').to_euler()
sc.camera = cam
bpy.ops.logic.sensor_add(type='ALWAYS', object=cam.name)
bpy.ops.logic.controller_add(type='PYTHON', object=cam.name)
s = cam.game.sensors[-1]; s.use_pulse_true_level = True
c = cam.game.controllers[-1]; c.mode = 'MODULE'; c.module = 'medir.tick'
s.link(c)
bpy.ops.object.lamp_add(type='SUN', location=(0,0,5), rotation=(0.6,0.3,0))
bpy.ops.wm.save_as_mainfile(filepath=out)
