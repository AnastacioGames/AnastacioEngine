# Cena p/ comparar a fisica serial x paralela (RANGE_PHYSICS_MT).
# Uso: AnastacioEngine.exe -b --factory-startup --python este.py -- saida.range
# No jogo: grava posicoes de todos os corpos no frame 400 em $DET_OUT e sai.
import bpy, sys, math
from mathutils import Vector
out = sys.argv[sys.argv.index('--') + 1]
sc = bpy.context.scene
for o in list(sc.objects): sc.objects.unlink(o); bpy.data.objects.remove(o)
sc.render.engine = 'BLENDER_GAME'
gs = sc.game_settings
gs.use_frame_rate = False
def mat(n, c):
    m = bpy.data.materials.new(n); m.diffuse_color = c; return m
# chao trimesh irregular
bpy.ops.mesh.primitive_grid_add(x_subdivisions=30, y_subdivisions=30, radius=30, location=(0, 0, 0))
g = bpy.context.object; g.name = 'Chao'
for v in g.data.vertices: v.co.z = 1.5 * math.sin(v.co.x * .3) * math.cos(v.co.y * .25)
g.data.materials.append(mat('chao', (.3, .6, .3)))
g.game.physics_type = 'STATIC'; g.game.collision_bounds_type = 'TRIANGLE_MESH'
# corpos: caixas convexas + "carros" compound
cor = mat('corpo', (.9, .3, .1)); cor2 = mat('carro', (.1, .3, .9))
n = 0
for i in range(8):
    for j in range(8):
        loc = (i * 3 - 10.5, j * 3 - 10.5, 6 + ((i + j) % 4) * 2)
        if (i + j) % 2 == 0:
            bpy.ops.mesh.primitive_cube_add(location=loc); o = bpy.context.object
            o.game.collision_bounds_type = 'CONVEX_HULL'; o.data.materials.append(cor)
        else:
            bpy.ops.mesh.primitive_cube_add(location=loc); o = bpy.context.object
            o.scale = (1.2, .6, .3); o.data.materials.append(cor2)
            bpy.ops.mesh.primitive_cylinder_add(radius=.3, depth=.2, location=(loc[0] + .9, loc[1], loc[2] - .3))
            r = bpy.context.object; r.data.materials.append(cor2)
            sc.update(); r.parent = o; r.matrix_parent_inverse = o.matrix_world.inverted()
            r.game.use_collision_compound = True
            o.game.use_collision_compound = True; o.game.collision_bounds_type = 'BOX'
        o.name = 'Corpo%02d' % n; n += 1
        o.game.physics_type = 'RIGID_BODY'
        o.rotation_euler = (.3 * i, .2 * j, .1 * (i + j))
# luz e camera
bpy.ops.object.lamp_add(type='SUN', location=(0, 0, 20)); bpy.context.object.rotation_euler = (.6, .3, 0)
bpy.ops.object.camera_add(location=(30, -30, 25)); cam = bpy.context.object
cam.rotation_euler = (Vector((0, 0, 0)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
sc.camera = cam
txt = bpy.data.texts.new('det.py')
txt.write('''import os, bge
def tick(cont):
    o = cont.owner
    o['f'] = o.get('f', 0) + 1
    if o['f'] == 400:
        with open(os.environ['DET_OUT'], 'w') as fh:
            for ob in sorted(bge.logic.getCurrentScene().objects, key=lambda x: x.name):
                if ob.name.startswith('Corpo'):
                    fh.write('%s %r %r %r' % (ob.name, *ob.worldPosition) + chr(10))
        bge.logic.endGame()
''')
ctrl = bpy.data.objects.new('controle', None); sc.objects.link(ctrl); sc.objects.active = ctrl
bpy.ops.logic.sensor_add(type='ALWAYS', name='always', object='controle')
bpy.ops.logic.controller_add(type='PYTHON', name='py', object='controle')
ctrl.game.sensors['always'].use_pulse_true_level = True
c = ctrl.game.controllers['py']; c.mode = 'MODULE'; c.module = 'det.tick'
ctrl.game.sensors['always'].link(c)
if sc.world is None: sc.world = bpy.data.worlds.new('mundo')
sc.world.mist_settings.use_mist = False
bpy.ops.wm.save_as_mainfile(filepath=out)
