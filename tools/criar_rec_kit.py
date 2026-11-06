# Gera o kit inicial do Rec Studio: personagens e acoes (characters.range) e cenarios (scenery.range).
# Tudo feito aqui, em caixas low poly. Objetos com nome ".x" nao aparecem no Asset Browser; soltar a
# malha do personagem traz a armature pelo modificador, por isso a armature pode ficar escondida.
#   AnastacioEngine.exe -b --factory-startup --python tools/criar_rec_kit.py -- pasta_de_saida
import bmesh
import bpy
import math
import os
import sys

saida = sys.argv[sys.argv.index('--') + 1]
scene = bpy.context.scene


def limpar():
    for ob in list(scene.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for lista in (bpy.data.meshes, bpy.data.materials, bpy.data.armatures, bpy.data.actions, bpy.data.groups):
        for item in list(lista):
            lista.remove(item)
    scene.render.engine = 'BLENDER_GAME'
    scene.world = None


def material(nome, cor):
    mat = bpy.data.materials.get(nome) or bpy.data.materials.new(nome)
    mat.diffuse_color = cor
    mat.specular_intensity = 0.05
    return mat


def caixa(bm, centro, tamanho, indice, grupo=None, camada=None):
    """Caixa no bmesh; grupo = indice do grupo de vertices que ela segue."""
    r = bmesh.ops.create_cube(bm, size=1.0)
    for v in r['verts']:
        v.co.x = v.co.x * tamanho[0] + centro[0]
        v.co.y = v.co.y * tamanho[1] + centro[1]
        v.co.z = v.co.z * tamanho[2] + centro[2]
        if grupo is not None:
            v[camada][grupo] = 1.0
    for f in {f for v in r['verts'] for f in v.link_faces}:
        f.material_index = indice


OSSOS = (  # nome, cabeca, cauda, pai
    ('hips', (0, 0, 0.85), (0, 0, 1.05), None),
    ('chest', (0, 0, 1.05), (0, 0, 1.45), 'hips'),
    ('head', (0, 0, 1.5), (0, 0, 1.95), 'chest'),
    ('arm.L', (0.3, 0, 1.42), (0.3, 0, 0.85), 'chest'),
    ('arm.R', (-0.3, 0, 1.42), (-0.3, 0, 0.85), 'chest'),
    ('leg.L', (0.12, 0, 0.85), (0.12, 0, 0.05), 'hips'),
    ('leg.R', (-0.12, 0, 0.85), (-0.12, 0, 0.05), 'hips'),
)


def personagem(nome, pele, roupa, calca, largura=1.0, chapeu=None):
    arm = bpy.data.armatures.new('.' + nome)
    rig = bpy.data.objects.new('.' + nome + ' Rig', arm)
    scene.objects.link(rig)
    scene.objects.active = rig
    bpy.ops.object.mode_set(mode='EDIT')
    for osso, cabeca, cauda, pai in OSSOS:
        b = arm.edit_bones.new(osso)
        b.head, b.tail = cabeca, cauda
        b.roll = 0.0
        if pai:
            b.parent = arm.edit_bones[pai]
    bpy.ops.object.mode_set(mode='OBJECT')
    for pb in rig.pose.bones:
        pb.rotation_mode = 'XYZ'
    rig.game.physics_type = 'NO_COLLISION'

    malha = bpy.data.meshes.new(nome)
    ob = bpy.data.objects.new(nome, malha)
    scene.objects.link(ob)
    for mat in (material(nome + ' pele', pele), material(nome + ' roupa', roupa), material(nome + ' calca', calca),
                material('olho', (0.03, 0.03, 0.05))):
        malha.materials.append(mat)
    grupos = {osso[0]: ob.vertex_groups.new(osso[0]).index for osso in OSSOS}

    bm = bmesh.new()
    camada = bm.verts.layers.deform.verify()
    w = largura

    def peca(osso, centro, tamanho, indice):
        caixa(bm, centro, tamanho, indice, grupos[osso], camada)

    peca('hips', (0, 0, 0.95), (0.42 * w, 0.26, 0.2), 2)
    peca('chest', (0, 0, 1.27), (0.46 * w, 0.28, 0.45), 1)
    peca('head', (0, 0, 1.72), (0.4, 0.38, 0.4), 0)
    peca('head', (0.09, 0.2, 1.76), (0.07, 0.03, 0.08), 3)  # A frente do boneco e +Y.
    peca('head', (-0.09, 0.2, 1.76), (0.07, 0.03, 0.08), 3)
    if chapeu:
        peca('head', (0, 0, 1.96), (0.46, 0.44, 0.08), 1)
        peca('head', (0, 0, 2.06), (0.32, 0.32, 0.16), 1)
    for lado, x in (('L', 1), ('R', -1)):
        peca('arm.' + lado, (x * (0.26 * w + 0.07), 0, 1.2), (0.14, 0.16, 0.46), 1)
        peca('arm.' + lado, (x * (0.26 * w + 0.07), 0, 0.9), (0.13, 0.15, 0.13), 0)
        peca('leg.' + lado, (x * 0.12, 0, 0.5), (0.17, 0.2, 0.72), 2)
        peca('leg.' + lado, (x * 0.12, 0.05, 0.07), (0.18, 0.32, 0.14), 3)
    bm.to_mesh(malha)
    bm.free()

    mod = ob.modifiers.new('Armature', 'ARMATURE')
    mod.object = rig
    ob.parent = rig
    ob.game.physics_type = 'NO_COLLISION'
    return rig


def acao(rig, nome, ultimo, chaves):
    """chaves: {osso: {quadro: (x, y, z) em graus}}; 'hips_z' sobe o quadril."""
    act = bpy.data.actions.new(nome)
    act.use_fake_user = True
    rig.animation_data_create().action = act
    for osso, quadros in chaves.items():
        if osso == 'hips_z':
            pb = rig.pose.bones['hips']
            for quadro, z in quadros.items():
                pb.location = (0, z, 0)  # O Y do osso aponta para cima.
                pb.keyframe_insert('location', frame=quadro, group='hips')
            pb.location = (0, 0, 0)
            continue
        pb = rig.pose.bones[osso]
        for quadro, graus in quadros.items():
            pb.rotation_euler = [math.radians(g) for g in graus]
            pb.keyframe_insert('rotation_euler', frame=quadro, group=osso)
        pb.rotation_euler = (0, 0, 0)
    # O ultimo quadro repete o primeiro nas acoes em ciclo, entao a volta nao pula.
    rig.animation_data.action = None
    assert act.frame_range[1] == ultimo, nome


def passo(a, f):
    return {1: (a, 0, 0), f // 2 + 1: (-a, 0, 0), f + 1: (a, 0, 0)}


def contra(a, f):
    return passo(-a, f)


def criar_personagens():
    limpar()
    rig = personagem('Hero', (0.9, 0.68, 0.5), (0.1, 0.35, 0.8), (0.15, 0.15, 0.25))
    personagem('Pip', (0.55, 0.36, 0.22), (0.95, 0.65, 0.1), (0.5, 0.15, 0.15), 0.85)
    personagem('Captain', (0.85, 0.6, 0.45), (0.75, 0.1, 0.15), (0.1, 0.1, 0.1), 1.15, chapeu=True)

    acao(rig, 'Idle', 49, {'chest': {1: (0, 0, 0), 25: (3, 0, 0), 49: (0, 0, 0)},
                           'arm.L': {1: (0, 0, 2), 25: (0, 0, 5), 49: (0, 0, 2)},
                           'arm.R': {1: (0, 0, -2), 25: (0, 0, -5), 49: (0, 0, -2)}})
    acao(rig, 'Walk', 25, {'leg.L': passo(30, 24), 'leg.R': contra(30, 24),
                           'arm.L': contra(28, 24), 'arm.R': passo(28, 24),
                           'hips_z': {1: 0.0, 7: 0.03, 13: 0.0, 19: 0.03, 25: 0.0}})
    acao(rig, 'Run', 17, {'leg.L': passo(55, 16), 'leg.R': contra(55, 16),
                          'arm.L': contra(60, 16), 'arm.R': passo(60, 16),
                          'chest': {1: (12, 0, 0), 17: (12, 0, 0)},
                          'hips_z': {1: 0.0, 5: 0.08, 9: 0.0, 13: 0.08, 17: 0.0}})
    acao(rig, 'Wave', 41, {'arm.R': {1: (0, 0, 0), 9: (170, 0, 20), 17: (170, 0, -15), 25: (170, 0, 20),
                                     33: (170, 0, -15), 41: (0, 0, 0)}})
    acao(rig, 'Jump', 31, {'hips_z': {1: 0.0, 7: -0.2, 14: 0.7, 22: 0.3, 27: -0.15, 31: 0.0},
                           'leg.L': {1: (0, 0, 0), 7: (35, 0, 0), 14: (-10, 0, 0), 27: (35, 0, 0), 31: (0, 0, 0)},
                           'leg.R': {1: (0, 0, 0), 7: (35, 0, 0), 14: (-10, 0, 0), 27: (35, 0, 0), 31: (0, 0, 0)},
                           'arm.L': {1: (0, 0, 0), 14: (170, 0, 0), 31: (0, 0, 0)},
                           'arm.R': {1: (0, 0, 0), 14: (170, 0, 0), 31: (0, 0, 0)}})
    acao(rig, 'Dance', 33, {'hips': {1: (0, 0, 15), 17: (0, 0, -15), 33: (0, 0, 15)},
                            'chest': {1: (0, 12, 0), 17: (0, -12, 0), 33: (0, 12, 0)},
                            'arm.L': {1: (120, 0, 0), 9: (170, 0, 0), 17: (120, 0, 0), 25: (170, 0, 0), 33: (120, 0, 0)},
                            'arm.R': {1: (170, 0, 0), 9: (120, 0, 0), 17: (170, 0, 0), 25: (120, 0, 0), 33: (170, 0, 0)},
                            'hips_z': {1: 0.0, 9: -0.06, 17: 0.0, 25: -0.06, 33: 0.0}})
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(saida, 'characters.range'), compress=True)


def pecas(nome, grupo, lista):
    """lista: (centro, tamanho, cor). Uma malha estatica por grupo de pecas com a mesma cor."""
    malha = bpy.data.meshes.new(nome)
    ob = bpy.data.objects.new('.' + nome, malha)
    scene.objects.link(ob)
    cores = []
    bm = bmesh.new()
    for centro, tamanho, cor in lista:
        if cor not in cores:
            cores.append(cor)
            malha.materials.append(material('%s %d' % (grupo.name, len(cores)), cor))
        caixa(bm, centro, tamanho, cores.index(cor))
    bm.to_mesh(malha)
    bm.free()
    ob.game.physics_type = 'STATIC'
    grupo.objects.link(ob)


GRAMA, TRONCO, FOLHA = (0.3, 0.55, 0.25), (0.4, 0.26, 0.14), (0.12, 0.42, 0.18)
CINZA, ASFALTO, FAIXA = (0.55, 0.55, 0.58), (0.16, 0.16, 0.18), (0.9, 0.85, 0.3)


def arvore(x, y, alto=1.0):
    return [((x, y, 1.2 * alto), (0.4, 0.4, 2.4 * alto), TRONCO),
            ((x, y, 3.0 * alto), (2.4, 2.4, 1.6 * alto), FOLHA),
            ((x, y, 4.1 * alto), (1.4, 1.4, 1.0 * alto), FOLHA)]


def criar_cenarios():
    limpar()
    park = bpy.data.groups.new('Park')
    park.use_fake_user = True
    lista = [((0, 0, -0.1), (40, 40, 0.2), GRAMA), ((0, 0, 0.01), (3, 40, 0.02), (0.75, 0.68, 0.5))]
    for x, y, alto in ((-6, 5, 1.0), (7, 9, 1.3), (-9, -4, 1.2), (8, -7, 0.9), (-5, 14, 1.4), (10, 15, 1.1)):
        lista += arvore(x, y, alto)
    lista += [((3.2, 2, 0.45), (2.4, 0.6, 0.12), TRONCO), ((3.2, 2.25, 0.8), (2.4, 0.1, 0.6), TRONCO)]
    pecas('Park', park, lista)

    street = bpy.data.groups.new('Street')
    street.use_fake_user = True
    lista = [((0, 0, -0.1), (40, 60, 0.2), CINZA), ((0, 0, 0.01), (10, 60, 0.02), ASFALTO)]
    for y in range(-26, 28, 6):
        lista.append(((0, y, 0.03), (0.3, 3, 0.02), FAIXA))
    cores = ((0.7, 0.35, 0.25), (0.3, 0.45, 0.65), (0.75, 0.68, 0.45), (0.45, 0.6, 0.45))
    for i, y in enumerate(range(-24, 30, 12)):
        lista.append(((-12, y, 5 + i % 3), (8, 10, 10 + 2 * (i % 3)), cores[i % 4]))
        lista.append(((12, y + 4, 4 + (i + 1) % 3), (8, 10, 8 + 2 * ((i + 1) % 3)), cores[(i + 2) % 4]))
    pecas('Street', street, lista)

    room = bpy.data.groups.new('Room')
    room.use_fake_user = True
    piso, parede, movel = (0.6, 0.42, 0.26), (0.85, 0.8, 0.68), (0.35, 0.2, 0.12)
    pecas('Room', room, [((0, 0, -0.1), (14, 14, 0.2), piso), ((0, 7.1, 2), (14, 0.2, 4), parede),
                         ((-7.1, 0, 2), (0.2, 14, 4), parede), ((7.1, 0, 2), (0.2, 14, 4), parede),
                         ((3, 4, 0.8), (3, 1.6, 0.12), movel), ((1.8, 3.5, 0.4), (0.15, 0.15, 0.8), movel),
                         ((4.2, 3.5, 0.4), (0.15, 0.15, 0.8), movel), ((1.8, 4.5, 0.4), (0.15, 0.15, 0.8), movel),
                         ((4.2, 4.5, 0.4), (0.15, 0.15, 0.8), movel),
                         ((-4.5, 5.5, 0.5), (4, 1.6, 1), (0.25, 0.4, 0.6)),
                         ((-4.5, 6.2, 1.2), (4, 0.3, 1.4), (0.25, 0.4, 0.6))])

    stage = bpy.data.groups.new('Stage')
    stage.use_fake_user = True
    vermelho, tabua = (0.6, 0.08, 0.1), (0.5, 0.33, 0.18)
    pecas('Stage', stage, [((0, 0, -0.1), (30, 30, 0.2), (0.12, 0.12, 0.14)), ((0, 2, 0.4), (16, 10, 0.8), tabua),
                           ((-7, 7.2, 4), (2, 0.4, 8), vermelho), ((7, 7.2, 4), (2, 0.4, 8), vermelho),
                           ((0, 7.4, 8.2), (16, 0.4, 1.6), vermelho), ((0, 7.5, 4), (14, 0.1, 8), (0.1, 0.05, 0.08))])
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(saida, 'scenery.range'), compress=True)


criar_personagens()
criar_cenarios()
