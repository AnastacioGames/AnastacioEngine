"""Prévia na 3D View, Fase 4 (docs/plano-previa-viewport.md): Impostor (Billboard + Atlas) e HLOD. Cenas geradas
por script, cada uma capturada no jogo e na viewport (câmera ativa) e comparada por contagem de pixels por cor:
  - atlas 2x1 (esquerda vermelha, direita azul): a câmera em +Y vê a célula 0 (vermelho), em -Y a célula 1 (azul);
  - billboard sem atlas: com a câmera em +X o quad (plano XZ) só aparece de frente se girar para a câmera;
  - HLOD: o original (vermelho, perto da câmera) some junto com o proxy aparecer (verde), porque a distância
    do original é medida a partir do proxy."""
import os
from PIL import Image
import controle
from rodar import py

BASE = '''
import math
from mathutils import Vector
sc = bpy.context.scene
sc.render.engine = 'BLENDER_GAME'
sc.game_settings.use_shading_nodes = True
for ob in list(sc.objects):
    sc.objects.unlink(ob)
w = bpy.data.worlds.new('W')
w.horizon_color = (0, 0, 0)
sc.world = w

def emissao(nome, cor, imagem=None):
    m = bpy.data.materials.new(nome)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    e = nt.nodes.new('ShaderNodeEmission')
    o = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(e.outputs[0], o.inputs['Surface'])
    if imagem:
        t = nt.nodes.new('ShaderNodeTexImage')
        t.image = imagem
        t.interpolation = 'Closest'
        nt.links.new(t.outputs['Color'], e.inputs['Color'])
    else:
        e.inputs['Color'].default_value = cor
    return m

def cubo(nome, loc, esc, m, layers=None):
    bpy.ops.mesh.primitive_cube_add(radius=1, location=loc)
    ob = sc.objects.active
    ob.name = nome
    ob.scale = esc
    ob.data.materials.append(m)
    if layers:
        ob.layers = layers
    return ob

OCULTA = [False, True] + [False] * 18

def camera(loc, alvo):
    cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
    sc.objects.link(cam)
    cam.location = loc
    cam.rotation_euler = (Vector(alvo) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = 35
    sc.camera = cam

def finalizar():
    for ob in sc.objects:
        ob.select = False
'''

IMPOSTOR = BASE + '''
# atlas 2x1: esquerda vermelha, direita azul
img = bpy.data.images.new('Atlas', 2, 1, alpha=True)
img.pixels = [1, 0, 0, 1, 0, 0, 1, 1]
img.pack(as_png=True)
img.use_fake_user = True
mat = emissao('Impostor', None, img)

verde = emissao('Verde', (0, 1, 0, 1))
arvore = cubo('Arvore', (0, 0, 1), (0.5, 0.5, 1), verde)

# o quad do impostor fica no plano XZ (normal em Y), numa layer oculta
bpy.ops.mesh.primitive_plane_add(radius=1, location=(0, 0, 0), rotation=(math.pi / 2, 0, 0))
quad = sc.objects.active
quad.name = 'Quad'
bpy.ops.object.transform_apply(rotation=True, location=True, scale=True)
quad.location = (0, 0, 1)
quad.scale = (1.5, 1.5, 1.5)
quad.data.materials.append(mat)
quad.layers = OCULTA
sc.objects.active = arvore
bpy.ops.object.lod_add()
nivel = arvore.lod_levels[1]
nivel.distance = 5
nivel.object = quad
nivel.use_mesh = True
nivel.use_material = True
nivel.use_billboard = True
nivel.use_atlas = @ATLAS@
nivel.atlas_columns = 2
nivel.atlas_rows = 1
camera(@CAM@, (0, 0, 1))
finalizar()
'''

HLOD = BASE + '''
vermelho = emissao('Vermelho', (1, 0, 0, 1))
verde = emissao('Verde', (0, 1, 0, 1))
cam_loc = (0, -8, 2)

# proxy na origem (distância da câmera 8.2): nível base invisível, malha verde a partir de 7.8
proxy = cubo('Proxy', (0, 0, 0.5), (1.2, 1.2, 1.2), verde)
malha = cubo('ProxyMalha', (0, 0, 0.5), (1.2, 1.2, 1.2), verde, OCULTA)
sc.objects.active = proxy
bpy.ops.object.lod_add()
proxy.lod_levels[0].use_invisible_mesh = True
proxy.lod_levels[1].distance = 7.8
proxy.lod_levels[1].object = malha
proxy.lod_levels[1].use_mesh = True
proxy.lod_levels[1].use_material = True

# original mais perto da câmera (4.5): sozinho ainda apareceria; o último nível invisível mede a partir do proxy
orig = cubo('Original', (0, -4, 0.5), (0.8, 0.8, 0.8), vermelho)
sc.objects.active = orig
bpy.ops.object.lod_add()
orig.lod_levels[1].distance = 7.8
orig.lod_levels[1].use_invisible_mesh = True
orig.lod_levels[1].object = proxy
camera(cam_loc, (0, 0, 0.5))
finalizar()
'''

PREPARAR = '''
import bpy
for a in bpy.context.screen.areas:
    if a.type == 'VIEW_3D':
        sp = a.spaces.active
        sp.region_3d.view_perspective = 'CAMERA'
        sp.viewport_shade = 'MATERIAL'
        sp.show_only_render = True
        r = [r for r in a.regions if r.type == 'WINDOW'][0]
        caixa = (r.x, bpy.context.window.height - r.y - r.height, r.x + r.width, bpy.context.window.height - r.y)
bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=3)
resultado = list(caixa)
'''


def contar(im):
    """Pixels vermelhos, azuis e verdes (canal dominante > 120 e o dobro dos outros)."""
    vermelho = azul = verde = 0
    for r, g, b in im.getdata():
        if r > 120 and r > 2 * g and r > 2 * b:
            vermelho += 1
        elif b > 120 and b > 2 * r and b > 2 * g:
            azul += 1
        elif g > 120 and g > 2 * r and g > 2 * b:
            verde += 1
    return {'vermelho': vermelho, 'azul': azul, 'verde': verde}


def captura(t, cena, nome):
    j = t.jogo(cena, largura=960, altura=540)
    j.esperar(frames=30)
    j.tela(arquivo=str(t.pasta / (nome + '_jogo.png')))
    j.fechar()
    e = t.editor(cena)
    caixa = py(e, PREPARAR)
    png = str(t.pasta / (nome + '_previa.png'))
    e.pedir("tela", arquivo=png)
    im = Image.open(png).convert('RGB').crop(caixa)
    w, h = im.size
    im = im.crop((w // 10, h // 10, w * 9 // 10, h * 9 // 10))
    im.save(png)
    jogo = Image.open(str(t.pasta / (nome + '_jogo.png'))).convert('RGB')
    return contar(jogo), contar(im)


def gerar(t, codigo, nome, **troca):
    for k, v in troca.items():
        codigo = codigo.replace('@%s@' % k, str(v))
    return t.gerar(codigo, nome=nome)


def testar(t):
    # atlas: câmera em +Y -> célula 0 (vermelho); em -Y -> célula 1 (azul)
    for nome, cam, cor, outra in (('atlas_mais_y', '(0, 8, 2)', 'vermelho', 'azul'),
                                  ('atlas_menos_y', '(0, -8, 2)', 'azul', 'vermelho')):
        jogo, previa = captura(t, gerar(t, IMPOSTOR, nome, ATLAS='True', CAM=cam), nome)
        t.nota('%s: jogo %s, prévia %s' % (nome, jogo, previa))
        assert jogo[cor] > 300 and jogo[cor] > 4 * jogo[outra], 'o jogo não mostrou a célula esperada (%s)' % nome
        assert previa[cor] > 300 and previa[cor] > 4 * previa[outra], 'a prévia não mostrou a célula %s (%s)' % (cor, nome)
        assert abs(previa[cor] - jogo[cor]) < 0.35 * jogo[cor], 'área do impostor difere do jogo (%s)' % nome

    # billboard sem atlas, câmera em +X: o quad do plano XZ só aparece se girar para a câmera
    jogo, previa = captura(t, gerar(t, IMPOSTOR, 'billboard', ATLAS='False', CAM='(8, 0, 2)'), 'billboard')
    cobre = lambda c: c['vermelho'] + c['azul']
    t.nota('billboard: jogo %s, prévia %s' % (jogo, previa))
    assert cobre(jogo) > 800, 'o jogo não girou o impostor para a câmera'
    assert cobre(previa) > 800, 'a prévia não girou o impostor para a câmera (quad de perfil)'
    assert abs(cobre(previa) - cobre(jogo)) < 0.35 * cobre(jogo), 'área do billboard difere do jogo'

    # HLOD: o original (vermelho) some e o proxy (verde) aparece, nos dois
    jogo, previa = captura(t, gerar(t, HLOD, 'hlod'), 'hlod')
    t.nota('hlod: jogo %s, prévia %s' % (jogo, previa))
    assert jogo['verde'] > 300 and jogo['vermelho'] < 50, 'o jogo não trocou o original pelo proxy'
    assert previa['verde'] > 300, 'a prévia não mostrou o proxy do HLOD'
    assert previa['vermelho'] < 50, 'a prévia ainda mostra o original (distância não medida a partir do proxy)'
    assert abs(previa['verde'] - jogo['verde']) < 0.35 * jogo['verde'], 'área do proxy difere do jogo'
