# Cena da postura do Character feita SÓ com logic bricks (sem Python no jogo).
# Uso: AnastacioEngine.exe -b --factory-startup --python este.py -- saida.range
# Teclas: W/A/S/D andar (vira p/ onde anda), Shift correr, C abaixar, Z rastejar, Espaço pular.
import bpy, sys, math
from mathutils import Vector

out = sys.argv[sys.argv.index('--') + 1]
sc = bpy.context.scene
for o in list(sc.objects):
    sc.objects.unlink(o)
sc.render.engine = 'BLENDER_GAME'
sc.game_settings.show_debug_properties = True


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


caixa('Chao', (0, 0, -0.5), (30, 30, 0.5), (0.3, 0.6, 0.3))
caixa('TetoBaixo', (0, 8, 1.9), (2, 2, 0.5), (0.7, 0.7, 0.7))        # passa abaixado
caixa('TuneloRasteja', (0, 16, 1.2), (2, 2, 0.5), (0.5, 0.5, 0.8))   # só rastejando
caixa('Degrau', (6, 4, 0.4), (1.5, 1.5, 0.4), (0.8, 0.5, 0.3))       # pular em cima

bpy.ops.mesh.primitive_cylinder_add(radius=0.4, depth=2.0, location=(0, 0, 0))
p = sc.objects.active
p.name = 'Jogador'
for v in p.data.vertices:
    v.co.z += 1.0
p.location.z = 0.05
p.data.materials.append(mat('Jogador', (0.9, 0.2, 0.2)))
bpy.ops.mesh.primitive_cube_add(location=(0, 0.45, 1.6))  # "nariz" mostra a frente (+Y)
n = sc.objects.active
n.name = 'Frente'
n.scale = (0.1, 0.1, 0.1)
n.data.materials.append(mat('Frente', (1, 1, 0)))
n.game.physics_type = 'NO_COLLISION'
n.parent = p
n.matrix_parent_inverse = p.matrix_world.inverted()

g = p.game
g.physics_type = 'CHARACTER'
g.use_collision_bounds = True
g.collision_bounds_type = 'CAPSULE'
g.crouch_height = 0.5
g.crawl_height = 0.3
g.crawl_axis = 'POS_Y'
g.use_jump_tuck = True
g.jump_speed = 8.0
g.run_speed = 1.8
g.posture_property = 'pose'
g.use_face_movement = True
sc.objects.active = p
bpy.ops.object.game_property_new(type='STRING', name='pose')
p.game.properties['pose'].show_debug = True

# Câmera em terceira pessoa: pivô preso só na POSIÇÃO do jogador (vertex parent),
# assim o jogador gira sozinho sem girar a câmera. O mouse gira o pivô e a câmera.
bpy.ops.object.empty_add(location=(0, 0, 1.5))
piv = sc.objects.active
piv.name = 'Pivo'
piv.parent = p
piv.parent_type = 'VERTEX'
piv.parent_vertices = (0, 0, 0)
bpy.ops.object.camera_add(location=(0, -7, 4))
cam = sc.objects.active
cam.data.lens = 16
cam.rotation_euler = (Vector((0, 0, 1.5)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
cam.parent = piv
cam.matrix_parent_inverse = piv.matrix_world.inverted()
sc.camera = cam


def mouse(obj, eixo_x, eixo_y):
    sc.objects.active = obj
    bpy.ops.logic.sensor_add(type='ALWAYS', name='Mouse', object=obj.name)
    se = obj.game.sensors[-1]
    se.use_pulse_true_level = True
    bpy.ops.logic.controller_add(type='LOGIC_AND', name='Mouse', object=obj.name)
    co = obj.game.controllers[-1]
    bpy.ops.logic.actuator_add(type='MOUSE', name='Mouse', object=obj.name)
    ac = obj.game.actuators[-1]
    ac.mode = 'LOOK'
    ac.use_axis_x = eixo_x
    ac.use_axis_y = eixo_y
    se.link(co)
    ac.link(co)
    return ac


mouse(piv, True, False)
cy = mouse(cam, False, True)
cy.local_y = True
cy.reset_y = True
cy.sensitivity_y = 0.3
cy.min_y = math.radians(-15)
cy.max_y = math.radians(15)

bpy.ops.object.lamp_add(type='SUN', location=(0, 0, 10))
sc.objects.active.rotation_euler = (math.radians(40), 0, math.radians(30))
sc.objects.active = p


def tecla(nome, key, act_cfg, shift=False):
    bpy.ops.logic.sensor_add(type='KEYBOARD', name=nome, object=p.name)
    s = p.game.sensors[-1]
    s.key = key
    s.use_pulse_true_level = True
    bpy.ops.logic.controller_add(type='LOGIC_AND', name=nome, object=p.name)
    c = p.game.controllers[-1]
    bpy.ops.logic.actuator_add(type='MOTION', name=nome, object=p.name)
    a = p.game.actuators[-1]
    a.mode = 'OBJECT_CHARACTER'
    for k, v in act_cfg.items():
        setattr(a, k, v)
    s.link(c)
    a.link(c)


# VR Gaze = andar relativo à câmera (W vai para onde a câmera olha); Ad soma as teclas.
mov = {'use_vr_gaze': True, 'use_add_character_location': True}
tecla('Frente', 'W', dict(mov, offset_location=(0, 0.08, 0)))
tecla('Tras', 'S', dict(mov, offset_location=(0, -0.06, 0)))
tecla('Esq', 'A', dict(mov, offset_location=(-0.07, 0, 0)))
tecla('Dir', 'D', dict(mov, offset_location=(0.07, 0, 0)))
tecla('Correr', 'LEFT_SHIFT', {'use_character_run': True})
tecla('Abaixar', 'C', {'character_posture': 'CROUCH'})
tecla('Rastejar', 'Z', {'character_posture': 'CRAWL'})
tecla('Pular', 'SPACE', {'use_character_jump': True})

bpy.ops.wm.save_as_mainfile(filepath=out)
print('SALVO', out)
