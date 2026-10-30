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
# Teto baixo para o "Auto" (abaixar sozinho), y=-8.
caixa('Teto2', (4, -8, 1.9), (2, 1, 0.5), (0.6, 0.6, 0.6))
# Parede para o "Gira" (girar deitado): ao lado direito (x=+1.2), ao longo de Y.
caixa('Parede', (1.6, 8, 1), (0.3, 3, 1), (0.6, 0.4, 0.3))


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
    g.crouch_speed = 1.0   # casos antigos medem distância sem redução
    g.crawl_speed = 1.0
    return o


boneco('Abaixa', 0, 0, (0.9, 0.2, 0.2))
boneco('Rasteja', 0, 4, (0.9, 0.8, 0.2))
boneco('Pula', 0, -4, (0.2, 0.3, 0.9))
sc.objects['Abaixa'].game.posture_property = 'pose'
lento = boneco('Lento', 0, 12, (0.8, 0.5, 0.9))
lento.game.crawl_speed = 0.3
auto = boneco('Auto', 0, -8, (0.3, 0.9, 0.9))
auto.game.use_auto_crouch = True
boneco('Gira', 0, 8, (0.9, 0.5, 0.2))
corre = boneco('Corre', 0, 16, (0.4, 0.9, 0.4))
corre.game.run_speed = 1.8
corre.game.posture_property = 'pose'

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

    # --- Propriedade da postura (Abaixa tem posture_property='pose')
    if f == 75:
        linhas.append('propriedade: pose=%%r (esperado CROUCH)' %% a.get('pose'))
    if f == 280:
        linhas.append('propriedade: pose=%%r (esperado STAND)' %% a.get('pose'))

    # --- Velocidade: Lento deitado (30%%) x Rasteja em pé, mesma caminhada
    lo = sc.objects['Lento']; cl = C.getCharacter(lo)
    if f == 100:
        cl.posture = 'CRAWL'
        estado['x0'] = (lo.worldPosition.x, r.worldPosition.x)
    if 110 <= f < 140:
        cl.walkDirection = (0.02, 0, 0)
        cr.walkDirection = (0.02, 0, 0)
    if f == 140:
        cl.walkDirection = (0, 0, 0); cr.walkDirection = (0, 0, 0)
    # --- Corrida: Corre (Run Speed 1.8) x Rasteja andando, mesma caminhada
    co = sc.objects['Corre']; cc = C.getCharacter(co)
    if f == 100:
        estado['xc'] = co.worldPosition.x
        cc.running = True
    if 110 <= f < 140:
        cc.walkDirection = (0.02, 0, 0)
    if f == 125:
        linhas.append('corrida: pose=%%r (esperado RUN)' %% co.get('pose'))
    if f == 140:
        cc.walkDirection = (0, 0, 0)
        cc.running = False
    if f == 150:
        dc = co.worldPosition.x - estado['xc']; dr2 = r.worldPosition.x - estado['x0'][1]
        linhas.append('corrida: %%.2f de %%.2f = %%.2f (esperado ~1.80); pose=%%r (esperado STAND)' %% (
            dc, dr2, dc / dr2 if dr2 else 0, co.get('pose')))
    if f == 150:
        dl = lo.worldPosition.x - estado['x0'][0]; dr = r.worldPosition.x - estado['x0'][1]
        linhas.append('velocidade deitado: %%.2f de %%.2f = %%.2f (esperado ~0.30)' %% (dl, dr, dl / dr if dr else 0))

    # --- Abaixar sozinho: Auto anda para baixo do Teto2 sem pedir postura
    au = sc.objects['Auto']; cau = C.getCharacter(au)
    if 60 <= f < 220:
        cau.walkDirection = (0.03, 0, 0)
        if 2.5 < au.worldPosition.x < 5.5:
            estado.setdefault('auto', set()).add(cau.posture)
    if f == 220:
        cau.walkDirection = (0, 0, 0)
    if f == 240:
        linhas.append('abaixar sozinho: sob o teto=%%s, depois x=%%.2f posture=%%s (esperado CROUCH, >6, STAND)' %% (
            sorted(estado.get('auto', [])), au.worldPosition.x, cau.posture))

    # --- Girar deitado perto da parede: virar para +X jogaria o corpo dentro dela
    gi = sc.objects['Gira']; cg = C.getCharacter(gi)
    if f == 60:
        cg.posture = 'CRAWL'
    if f == 80:
        estado['yaw0'] = gi.worldOrientation.to_euler().z
        gi.applyRotation((0, 0, -1.5708), False)
    if f == 90:
        linhas.append('girar deitado contra a parede: yaw %%.2f -> %%.2f (esperado igual, giro desfeito)' %% (
            estado['yaw0'], gi.worldOrientation.to_euler().z))
        gi.applyRotation((0, 0, 1.5708), False)   # para o outro lado: livre
    if f == 100:
        linhas.append('girar deitado para o lado livre: yaw=%%.2f (esperado ~1.57)' %% gi.worldOrientation.to_euler().z)

    # --- Escala mudando abaixado: Lento abaixa, dobra de tamanho, levanta
    if f == 200:
        cl.posture = 'CROUCH'
    if f == 210:
        lo.worldScale = (2, 2, 2)
    if f == 220:
        cl.posture = 'STAND'
    if f == 210:
        p.worldScale = (2, 2, 2)   # em pé, sem postura: referência
    if f == 270:
        linhas.append('escala em pe (referencia): base=%%.3f' %% base(p))
    if f == 270:
        m = lo.meshes[0]
        alt = 2 * max(m.getVertex(0, i).XYZ.z for i in range(m.getVertexArrayLength(0)))
        linhas.append('escala abaixado: posture=%%s base=%%.3f altura_malha=%%.1f (esperado STAND, ~0, 4.0)' %% (cl.posture, base(lo), alt))

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
