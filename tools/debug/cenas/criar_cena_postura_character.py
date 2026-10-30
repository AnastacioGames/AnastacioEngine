# Cena de teste da postura do Character (abaixar / rastejar / pulo com pernas recolhidas).
# Uso: AnastacioEngine.exe -b --factory-startup --python este.py -- saida.range log.txt
# O jogo grava o resultado de cada caso em log.txt e fecha sozinho.
import bpy, sys
from mathutils import Vector

out, log = sys.argv[sys.argv.index('--') + 1:][:2]
sc = bpy.context.scene
for o in list(sc.objects):
    sc.objects.unlink(o)
sc.render.engine = 'BLENDER_GAME'


def mat(n, c):
    m = bpy.data.materials.new(n)
    m.diffuse_color = c
    return m


def caixa(nome, loc, escala, cor):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    o = sc.objects.active
    o.name = nome
    o.scale = escala
    o.data.materials.append(mat(nome, cor))
    o.game.physics_type = 'STATIC'
    return o


caixa('Chao', (0, 0, -0.5), (20, 20, 0.5), (0.3, 0.6, 0.3))
# Teto baixo (base em z=1.4) de x=2 a x=6, só na faixa do boneco "Abaixa" (y=0).
caixa('Teto', (4, 0, 1.9), (2, 1, 0.5), (0.6, 0.6, 0.6))


def boneco(nome, x, y, cor):
    # Cilindro de 2 m com a origem nos pés.
    bpy.ops.mesh.primitive_cylinder_add(radius=0.4, depth=2.0, location=(x, y, 0))
    o = sc.objects.active
    o.name = nome
    for v in o.data.vertices:
        v.co.z += 1.0
    o.location.z = 0.05
    o.data.materials.append(mat(nome, cor))
    g = o.game
    g.physics_type = 'CHARACTER'
    g.use_collision_bounds = True
    g.collision_bounds_type = 'CAPSULE'
    g.crouch_height = 0.5
    g.crawl_height = 0.3
    g.use_jump_tuck = True
    g.jump_tuck = 0.3
    g.jump_speed = 8.0
    return o


boneco('Abaixa', 0, 0, (0.9, 0.2, 0.2))
boneco('Rasteja', 0, 4, (0.9, 0.8, 0.2))
boneco('Pula', 0, -4, (0.2, 0.3, 0.9))

t = bpy.data.texts.new('postura.py')
t.write('''import bge
from bge import constraints as C
LOG = %r
linhas = []
estado = {}

def base(o):
    m = o.meshes[0]
    return o.worldPosition.z + min(m.getVertex(0, i).XYZ.z for i in range(m.getVertexArrayLength(0)))

def tick(cont):
    sc = bge.logic.getCurrentScene()
    f = estado.get('f', 0) + 1
    estado['f'] = f
    a, r, p = sc.objects['Abaixa'], sc.objects['Rasteja'], sc.objects['Pula']
    ca, cr, cp = C.getCharacter(a), C.getCharacter(r), C.getCharacter(p)

    # --- Abaixa: abaixa, entra embaixo do teto, tenta levantar, sai e levanta sozinho
    if f == 60:
        ca.posture = 'CROUCH'
    if f == 70:
        linhas.append('abaixar: posture=%%s (esperado CROUCH)' %% ca.posture)
    if 70 <= f < 110:
        ca.walkDirection = (0.05, 0, 0)   # ~0.1 m/frame: anda até x~4, embaixo do teto
    if f == 110:
        ca.walkDirection = (0, 0, 0)
    if f == 150:
        ca.walkDirection = (0, 0, 0)
        ca.posture = 'STAND'
    if f == 170:
        linhas.append('sob o teto: x=%%.2f posture=%%s canStand=%%s (esperado CROUCH, False)' %% (a.worldPosition.x, ca.posture, ca.canStand))
        linhas.append('sob o teto: base_malha=%%.3f (esperado ~0, não empurrado p/ baixo)' %% base(a))
    if 170 <= f < 210:
        ca.walkDirection = (0.05, 0, 0)   # sai pelo outro lado
    if f == 210:
        ca.walkDirection = (0, 0, 0)
    if f == 280:
        linhas.append('fora do teto: x=%%.2f posture=%%s (esperado STAND, levantou sozinho)' %% (a.worldPosition.x, ca.posture))

    # --- Rasteja: deita, tenta pular (não deve), levanta
    if f == 60:
        cr.posture = 'CRAWL'
    if f == 70:
        linhas.append('rastejar: posture=%%s (esperado CRAWL)' %% cr.posture)
        cr.jump()
    if f == 80:
        linhas.append('rastejar+pulo: jumpCount=%%d base=%%.3f (esperado 0, ~0)' %% (cr.jumpCount, base(r)))
        cr.posture = 'STAND'
    if f == 95:
        linhas.append('levantar: posture=%%s base=%%.3f (esperado STAND, ~0)' %% (cr.posture, base(r)))

    # --- Pula: recolhe as pernas subindo, estica descendo, pousa sem afundar
    if f == 60:
        cp.jump()
    if 61 <= f < 140:
        estado.setdefault('posturas', set()).add(cp.posture)
    if f == 140:
        linhas.append('pulo: posturas vistas=%%s (esperado JUMP_TUCK e STAND)' %% sorted(estado['posturas']))
        linhas.append('pouso: posture=%%s base=%%.3f onGround=%%s (esperado STAND, ~0, True)' %% (cp.posture, base(p), cp.onGround))

    if f == 300:
        with open(LOG, 'w') as fh:
            fh.write('\\n'.join(linhas) + '\\n# fim\\n')
        bge.logic.endGame()
''' % log)

bpy.ops.object.camera_add(location=(-6, -12, 6))
cam = sc.objects.active
cam.data.lens = 16
cam.rotation_euler = (Vector((2, 0, 1)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
sc.camera = cam
bpy.ops.logic.sensor_add(type='ALWAYS', object=cam.name)
bpy.ops.logic.controller_add(type='PYTHON', object=cam.name)
s = cam.game.sensors[-1]
s.use_pulse_true_level = True
c = cam.game.controllers[-1]
c.mode = 'MODULE'
c.module = 'postura.tick'
s.link(c)
bpy.ops.object.lamp_add(type='SUN', location=(0, 0, 8), rotation=(0.6, 0.3, 0))
sc.game_settings.use_frame_rate = True
bpy.ops.wm.save_as_mainfile(filepath=out)
