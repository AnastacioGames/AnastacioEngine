"""Prévia na 3D View, Fase 1 (docs/plano-previa-viewport.md): compositor de nós do jogo
(Use Nodes) na viewport com Game Preview > Compositing. Árvore Render Layers > Blur (estágio de
cache) > Invert > Composite. Confere que a prévia ligada inverte a imagem como o jogo e que,
desligada, nada muda."""
from PIL import Image, ImageStat
from rodar import py

L, A = 960, 540

CENA = '''
sc = bpy.context.scene
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = %d, %d, 100
bpy.ops.mesh.primitive_plane_add(radius=20)
for i in range(-3, 4):
    bpy.ops.mesh.primitive_cube_add(location=(i * 3, 6, 1))
sc.use_nodes = True
nt = sc.node_tree
rl = nt.nodes['Render Layers']
comp = nt.nodes['Composite']
blur = nt.nodes.new('CompositorNodeBlur')
blur.size_x = blur.size_y = 6
inv = nt.nodes.new('CompositorNodeInvert')
nt.links.new(rl.outputs['Image'], blur.inputs['Image'])
nt.links.new(blur.outputs['Image'], inv.inputs['Color'])
nt.links.new(inv.outputs['Color'], comp.inputs['Image'])
''' % (L, A)

RENDER = '''
import bpy
for a in bpy.context.screen.areas:
    if a.type == 'VIEW_3D':
        sp = a.spaces.active
        sp.region_3d.view_perspective = 'CAMERA'
        sp.viewport_shade = 'SOLID'
        sp.show_only_render = True
        sp.fx_settings.use_game_compositor = %s
        ov = dict(bpy.context.copy(), area=a, region=[r for r in a.regions if r.type == 'WINDOW'][0])
bpy.ops.render.opengl(ov, view_context=True)
bpy.data.images['Render Result'].save_render(r'%s')
resultado = 'ok'
'''


def media(png):
    return ImageStat.Stat(Image.open(png).convert('L')).mean[0]


def testar(t):
    cena = t.gerar(CENA)
    jogo_png, on_png, off_png = (str(t.pasta / n) for n in ('jogo.png', 'on.png', 'off.png'))

    j = t.jogo(cena, largura=L, altura=A)
    j.esperar(frames=30)
    j.tela(arquivo=jogo_png)

    e = t.editor(cena)
    py(e, RENDER % ('False', off_png))
    py(e, RENDER % ('True', on_png))

    jogo, on, off = media(jogo_png), media(on_png), media(off_png)
    t.nota('luminância média: jogo %.1f, prévia %.1f, sem prévia %.1f (invertida esperada %.1f)'
           % (jogo, on, off, 255 - off))
    assert abs(on - (255 - off)) < 12, 'a prévia não inverteu a imagem'
    # o jogo também sai invertido: mais perto da prévia que da imagem sem prévia
    assert abs(jogo - on) < abs(jogo - off), 'o jogo não bate com a prévia'
