# Cena de teste: Explosive > Light Flash. Bomba com pavio de 1 s diante de uma parede, sol fraco.
# Uso: AnastacioEngine.exe -b --factory-startup --python criar_cena_light_flash.py -- <saida.range> <1|0 = clarao> <pasta das fotos>
# No jogo grava shot_0..4.png (antes, 0.06, 0.15, 0.35 e 0.8 s depois da explosao) e fecha.
import bpy, bmesh, sys
from math import radians
from mathutils import Vector
args = sys.argv[sys.argv.index('--')+1:]
out, flash, shots = args[0], args[1] == '1', args[2].replace(chr(92), '/')
sc = bpy.context.scene
for o in list(sc.objects): sc.objects.unlink(o)
sc.render.engine = 'BLENDER_GAME'
def box(name, loc, size, color):
    me = bpy.data.meshes.new(name); bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1); bm.to_mesh(me)
    ob = bpy.data.objects.new(name, me); sc.objects.link(ob); ob.location = loc; ob.scale = size
    ma = bpy.data.materials.new(name); ma.diffuse_color = color; me.materials.append(ma)
    return ob
box("Floor", (0, 0, -0.5), (30, 30, 1), (0.5, 0.5, 0.5))
box("Wall", (0, 3, 2), (12, 0.4, 4), (0.6, 0.6, 0.6))
sun = bpy.data.objects.new('sun', bpy.data.lamps.new('sun', 'SUN')); sun.data.energy = 0.15
sun.rotation_euler = (radians(50), 0, radians(30)); sc.objects.link(sun)
bomb = box("Bomb", (0, 0, 0.4), (0.8, 0.8, 0.8), (0.6, 0.1, 0.05))
bomb.game.use_explosive = True
ex = bomb.game.explosive
ex.fuse = 1.0; ex.use_explode_on_impact = False; ex.use_chain_reaction = False
ex.use_particle_explosion = True; ex.particle_size = 'MEDIUM'
ex.use_light_flash = flash
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); cam.data.lens = 22
cam.location = (0, -14, 5)
cam.rotation_euler = (Vector((0, 0, 1)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
sc.objects.link(cam); sc.camera = cam
SCRIPT = '''import bge
FOTOS = (0.5, 1.06, 1.15, 1.35, 1.8)
def tick(cont):
    own = cont.owner
    t = bge.logic.getRealTime()
    if 'ini' not in own: own['ini'] = t
    dt = t - own['ini']
    k = own.get('k', 0)
    if k < len(FOTOS) and dt > FOTOS[k]:
        own['k'] = k + 1
        bge.render.makeScreenshot('%s/shot_%%d.png' %% k)
    if dt > 2.3: bge.logic.endGame()
''' % shots
txt = bpy.data.texts.new('t.py'); txt.write(SCRIPT)
sc.objects.active = cam
bpy.ops.logic.sensor_add(type='ALWAYS', name='s', object=cam.name)
s = cam.game.sensors['s']; s.use_pulse_true_level = True
bpy.ops.logic.controller_add(type='PYTHON', name='c', object=cam.name)
c = cam.game.controllers['c']; c.mode = 'MODULE'; c.module = 't.tick'; s.link(c)
bpy.ops.wm.save_as_mainfile(filepath=out)
print("SAVED")
