"""PrÃ©via na 3D View, Fase 0 (docs/plano-previa-viewport.md): lente da cÃ¢mera (aberraÃ§Ã£o,
vinheta, fisheye) com a mesma lib GLSL do jogo. Compara o jogo com o OpenGL Render da cÃ¢mera,
com e sem Game Preview > Camera Lens, e confere que a visÃ£o livre nÃ£o muda."""
from PIL import Image
from rodar import py

L, A = 960, 540

CENA = '''
sc = bpy.context.scene
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = %d, %d, 100
bpy.ops.mesh.primitive_plane_add(radius=20)
for i in range(-3, 4):
    bpy.ops.mesh.primitive_cube_add(location=(i * 3, 6, 1))
g = sc.camera.data.game_fx
g.use_chromatic, g.chromatic_strength = True, 5.0
g.use_vignette, g.vignette_strength, g.vignette_radius, g.fisheye_strength = True, 1.0, 1.0, 0.5
''' % (L, A)

RENDER = '''
import bpy
sc = bpy.context.scene
for a in bpy.context.screen.areas:
    if a.type == 'VIEW_3D':
        sp = a.spaces.active
        sp.region_3d.view_perspective = 'CAMERA'
        sp.viewport_shade = 'SOLID'
        sp.show_only_render = True
        sp.fx_settings.use_camera_lens = %s
        ov = dict(bpy.context.copy(), area=a, region=[r for r in a.regions if r.type == 'WINDOW'][0])
bpy.ops.render.opengl(ov, view_context=True)
bpy.data.images['Render Result'].save_render(r'%s')
resultado = 'ok'
'''


def preto(png):
    """MÃ¡scara dos pixels quase pretos: a borda do fisheye com a vinheta forte."""
    im = Image.open(png).convert('L').resize((L, A))
    return {i for i, v in enumerate(im.getdata()) if v < 12}


def iou(a, b):
    return len(a & b) / max(len(a | b), 1)


def testar(t):
    cena = t.gerar(CENA)
    jogo_png, on_png, off_png = (str(t.pasta / n) for n in ('jogo.png', 'on.png', 'off.png'))

    j = t.jogo(cena, largura=L, altura=A)
    j.esperar(frames=30)
    j.tela(arquivo=jogo_png)

    e = t.editor(cena)
    py(e, RENDER % ('False', off_png))
    py(e, RENDER % ('True', on_png))

    jogo, on, off = preto(jogo_png), preto(on_png), preto(off_png)
    t.nota('borda preta: jogo %d px, prÃ©via %d px, sem prÃ©via %d px; IoU jogo x prÃ©via %.2f'
           % (len(jogo), len(on), len(off), iou(jogo, on)))
    assert len(jogo) > L * A * 0.05, 'o jogo nÃ£o mostrou a borda do fisheye'
    assert len(off) < len(jogo) * 0.1, 'borda preta sem a prÃ©via ligada'
    assert iou(jogo, on) > 0.8, 'a borda do fisheye/vinheta da prÃ©via nÃ£o bate com o jogo'
