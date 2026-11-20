"""Prévia na 3D View, Fase 4 (docs/plano-previa-viewport.md): Baked Lighting. Um plano com a UV "Lightmap" e um
atlas gerado por script (metade esquerda laranja, direita azul, RGBM como o bake) mais um plano SEM a UV: no
jogo o primeiro se acende com as cores do atlas, nas posições certas, e o segundo fica escuro (sem luz).
A viewport em Material deve mostrar o mesmo; com Use Lightmap desligado volta a ficar escura. Compara por
cor, não por posição (a viewport e o jogo não têm o mesmo enquadramento)."""
import os
from PIL import Image
import controle
from rodar import py

CENA = '''
from mathutils import Vector
sc = bpy.context.scene
sc.render.engine = 'BLENDER_GAME'
sc.game_settings.use_shading_nodes = True
for ob in list(sc.objects):
    sc.objects.unlink(ob)
w = bpy.data.worlds.new('W')
w.horizon_color = (0, 0, 0)
sc.world = w

m = bpy.data.materials.new('Branco')
m.use_nodes = True
m.node_tree.nodes.clear()
s = m.node_tree.nodes.new('ShaderNodeBsdfPrincipled')
s.inputs['Base Color'].default_value = (0.8, 0.8, 0.8, 1)
s.inputs['Roughness'].default_value = 1.0
s.inputs['Specular'].default_value = 0.0
o = m.node_tree.nodes.new('ShaderNodeOutputMaterial')
m.node_tree.links.new(s.outputs[0], o.inputs['Surface'])

def plano(nome, x, com_lightmap):
    bpy.ops.mesh.primitive_plane_add(radius=1, location=(x, 0, 0))
    ob = sc.objects.active
    ob.name = nome
    ob.scale = (1.4, 1.4, 1)
    ob.data.materials.append(m)
    if com_lightmap:
        ob.data.uv_textures.new('Lightmap')
    return ob

plano('ComAtlas', -1.7, True)
plano('SemAtlas', 1.7, False)

# atlas RGBM (rgb = sqrt(E) / 8, a = 1; ver lightmap_sample): esquerda laranja, direita azul
N = 16
img = bpy.data.images.new('AE_Lightmap', N, N, alpha=True)
img.colorspace_settings.name = 'Non-Color'
img.alpha_mode = 'STRAIGHT'
px = []
for y in range(N):
    for x in range(N):
        E = (1.5, 0.5, 0.15) if x < N // 2 else (0.15, 0.5, 1.5)
        px += [E[0] ** 0.5 / 8, E[1] ** 0.5 / 8, E[2] ** 0.5 / 8, 1.0]
img.pixels = px
img.pack(as_png=True)
img.use_fake_user = True
sc.ae_lightmap = img.name
sc.ae_lightmap_use = True

cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
sc.objects.link(cam)
cam.location = (0, 0, 9)
cam.data.type = 'ORTHO'
cam.data.ortho_scale = 8
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

USAR = '''
import bpy
sc = bpy.context.scene
sc.ae_lightmap_use = %s
for a in bpy.context.screen.areas:
    if a.type == 'VIEW_3D':
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


def grupos(im):
    """Pixels laranja (r > 2b), azuis (b > 2r) e acesos no total (brilho > 25): contagem, cor média e x médio."""
    w, h = im.size
    px = im.load()
    laranja, azul, acesos = [], [], 0
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            if max(r, g, b) > 25:
                acesos += 1
            if r > 2 * b and r > 40:
                laranja.append((r, g, b, x))
            elif b > 2 * r and b > 40:
                azul.append((r, g, b, x))

    def resumo(lista):
        n = max(len(lista), 1)
        return {'n': len(lista), 'cor': tuple(sum(p[i] for p in lista) / n for i in range(3)),
                'x': sum(p[3] for p in lista) / n / w}
    return resumo(laranja), resumo(azul), acesos


def testar(t):
    cena = t.gerar(CENA)

    j = t.jogo(cena, largura=960, altura=540)
    j.esperar(frames=30)
    j.tela(arquivo=str(t.pasta / 'jogo.png'))
    j.fechar()

    e = t.editor(cena)
    caixa = py(e, USAR % 'True')
    com = recorte(e, str(t.pasta / 'com.png'), caixa)
    caixa = py(e, USAR % 'False')
    sem = recorte(e, str(t.pasta / 'sem.png'), caixa)
    caixa = py(e, USAR % 'True')
    de_novo = recorte(e, str(t.pasta / 'de_novo.png'), caixa)

    jogo = Image.open(str(t.pasta / 'jogo.png')).convert('RGB')
    gj, gc, gs, gn = grupos(jogo), grupos(com), grupos(sem), grupos(de_novo)
    t.nota('jogo laranja %s azul %s; prévia com %s %s; sem acesos %d; de novo %s %s' %
           (gj[0], gj[1], gc[0], gc[1], gs[2], gn[0], gn[1]))

    for nome, g in (('jogo', gj), ('prévia', gc)):
        assert g[0]['n'] > 500 and g[1]['n'] > 500, 'o atlas não acendeu o plano no %s' % nome
        assert g[0]['x'] < g[1]['x'], 'UV Lightmap invertida no %s (laranja deveria ficar à esquerda)' % nome
        ratio = g[0]['n'] / max(g[1]['n'], 1)
        assert 0.7 < ratio < 1.4, 'metades do atlas com áreas diferentes no %s (%.2f)' % (nome, ratio)
    # o plano sem a UV Lightmap fica escuro: só o plano com atlas acende (a área acesa é a de uma metade só)
    assert gc[2] < (gc[0]['n'] + gc[1]['n']) * 1.15, 'o plano sem UV Lightmap acendeu na prévia'
    # cores: a razão r/b do laranja e b/r do azul bate com a do jogo
    rb = lambda g: g[0]['cor'][0] / max(g[0]['cor'][2], 1)
    br = lambda g: g[1]['cor'][2] / max(g[1]['cor'][0], 1)
    assert abs(rb(gc) - rb(gj)) < 0.25 * rb(gj), 'cor do laranja difere do jogo (%.1f x %.1f)' % (rb(gc), rb(gj))
    assert abs(br(gc) - br(gj)) < 0.25 * br(gj), 'cor do azul difere do jogo (%.1f x %.1f)' % (br(gc), br(gj))
    assert abs(gc[0]['cor'][0] - gj[0]['cor'][0]) < 0.2 * gj[0]['cor'][0] + 8, 'brilho do laranja difere do jogo'
    # desligar o Use Lightmap apaga a prévia, ligar de volta restaura
    assert gs[0]['n'] + gs[1]['n'] < 50, 'Use Lightmap desligado ainda acende a prévia'
    assert abs(gn[0]['n'] - gc[0]['n']) < 0.05 * gc[0]['n'] + 20, 'religar o Use Lightmap não restaura a prévia'
