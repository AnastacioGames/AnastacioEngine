"""Prévia na 3D View, Fase 4 (docs/plano-previa-viewport.md): impostor de LOD. Uma árvore de cubo com um nível
Billboard + Atlas (4 colunas, cada célula de uma cor): na viewport (shading Material, visão da câmera) o quadro
gira para a câmera e mostra a célula do ângulo, como no jogo."""
import os
from PIL import Image
import controle
from rodar import py

CORES = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]

CENA = '''
from mathutils import Vector
sc = bpy.context.scene
sc.render.engine = 'BLENDER_GAME'
sc.game_settings.use_shading_nodes = True
for ob in list(sc.objects):
    sc.objects.unlink(ob)
w = bpy.data.worlds.new('W'); w.horizon_color = (0, 0, 0); sc.world = w

# atlas 4x1: vermelho, verde, azul, amarelo
img = bpy.data.images.new('atlas', 64, 16)
cores = [(1, 0, 0, 1), (0, 1, 0, 1), (0, 0, 1, 1), (1, 1, 0, 1)]
px = []
for y in range(16):
    for x in range(64):
        px.extend(cores[x // 16])
img.pixels = px
img.pack(as_png=True)
img.use_fake_user = True

m = bpy.data.materials.new('Atlas')
m.use_nodes = True
nt = m.node_tree
nt.nodes.clear()
t = nt.nodes.new('ShaderNodeTexImage'); t.image = img; t.interpolation = 'Closest'
e = nt.nodes.new('ShaderNodeEmission')
o = nt.nodes.new('ShaderNodeOutputMaterial')
nt.links.new(t.outputs['Color'], e.inputs['Color'])
nt.links.new(e.outputs[0], o.inputs['Surface'])

# quadro em pe, normal +Y (a frente do billboard)
bpy.ops.mesh.primitive_plane_add(radius=1.5, location=(0, 0, 0))
card = sc.objects.active
card.rotation_euler = (-1.5707963, 0, 0)
card.data.materials.append(m)
bpy.ops.object.transform_apply(rotation=True)
card.name = 'Card'
me = card.data
uvt = me.uv_textures.new('UVMap')
for poly in me.polygons:
    for li in poly.loop_indices:
        co = me.vertices[me.loops[li].vertex_index].co
        me.uv_layers[0].data[li].uv = ((co.x + 1.5) / 3.0, (co.z + 1.5) / 3.0)
card.layers = [k == 5 for k in range(20)]

# a "arvore": um cubo cinza que cede ao quadro a partir de 3 m
bpy.ops.mesh.primitive_cube_add(radius=1, location=(0, 0, 1.5))
tree = sc.objects.active
tree.name = 'Tree'
mm = bpy.data.materials.new('Cinza'); mm.use_nodes = True
mm.node_tree.nodes.clear()
ee = mm.node_tree.nodes.new('ShaderNodeEmission'); ee.inputs['Color'].default_value = (0.3, 0.3, 0.3, 1)
oo = mm.node_tree.nodes.new('ShaderNodeOutputMaterial')
mm.node_tree.links.new(ee.outputs[0], oo.inputs['Surface'])
tree.data.materials.append(mm)
sc.objects.active = tree
bpy.ops.object.lod_add()
lv = tree.lod_levels[1]
lv.object = card
lv.distance = 3.0
lv.use_mesh = True
lv.use_billboard = True
lv.use_atlas = True
lv.atlas_columns = 4
lv.atlas_rows = 1
card.location = tree.location

cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
sc.objects.link(cam)
cam.location = (ANG_X, ANG_Y, 3)
cam.rotation_euler = (Vector((0, 0, 1.5)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
cam.data.lens = 35
sc.camera = cam
for ob in sc.objects:
    ob.select = False
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


def recorte(e, png, caixa):
    e.pedir("tela", arquivo=png)
    im = Image.open(png).convert('RGB').crop(caixa)
    w, h = im.size
    im = im.crop((w // 10, h // 10, w * 9 // 10, h * 9 // 10))
    im.save(png)
    return im



def fracoes(im):
    px = list(im.getdata())
    n = len(px)
    def perto(p, c):
        return sum(abs(a - b) for a, b in zip(p, c)) < 120
    return [sum(1 for p in px if perto(p, c)) / n for c in CORES]


def testar(t):
    # câmeras em ângulos diferentes: cada um cai numa célula diferente do atlas
    for nome, x, y in (('a', 7, -7), ('b', 9, 4), ('c', -8, 5)):
        cena = t.gerar(CENA.replace('ANG_X', str(x)).replace('ANG_Y', str(y)), nome=nome)
        j = t.jogo(cena, largura=960, altura=540)
        j.esperar(frames=30)
        j.tela(arquivo=str(t.pasta / (nome + '_jogo.png')))
        j.fechar()
        e = t.editor(cena)
        caixa = py(e, PREPARAR)
        im = recorte(e, str(t.pasta / (nome + '_previa.png')), caixa)
        e.fechar() if hasattr(e, 'fechar') else None
        fj = fracoes(Image.open(str(t.pasta / (nome + '_jogo.png'))).convert('RGB'))
        fp = fracoes(im)
        t.nota('%s: jogo %s, prévia %s' % (nome, ['%.3f' % v for v in fj], ['%.3f' % v for v in fp]))
        dj, dp = fj.index(max(fj)), fp.index(max(fp))
        assert max(fj) > 0.02, nome + ': o quadro não apareceu no jogo'
        assert dj == dp, '%s: célula do atlas diferente (jogo %d, prévia %d)' % (nome, dj, dp)
        assert sum(fp[i] for i in range(4) if i != dp) < 0.3 * fp[dp], nome + ': a prévia mostra mais de uma célula'
