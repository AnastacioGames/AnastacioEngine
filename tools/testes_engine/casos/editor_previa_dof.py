"""Prévia na 3D View, Fase 2 (docs/plano-previa-viewport.md): DOF do jogo (Camera > Game FX > Depth of
Field) na viewport com Game Preview > Camera DOF. Foco manual perto da câmera: os cubos ao fundo ficam
borrados. Confere que a prévia ligada perde nitidez como o jogo e que, desligada, nada muda."""
from PIL import Image, ImageFilter, ImageStat
from rodar import py

L, A = 960, 540

CENA = '''
sc = bpy.context.scene
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = %d, %d, 100
bpy.ops.mesh.primitive_plane_add(radius=20)
for i in range(-3, 4):
    bpy.ops.mesh.primitive_cube_add(location=(i * 3, 6, 1))
cam = sc.camera.data
cam.gpu_dof.focus_distance = 2.0
g = cam.game_fx
g.use_dof, g.dof_blur, g.focus_range = True, 16.0, 0.5
g.use_cat_eye, g.cat_eye_strength = True, 1.0
''' % (L, A)

RENDER = '''
import bpy
for a in bpy.context.screen.areas:
    if a.type == 'VIEW_3D':
        sp = a.spaces.active
        sp.region_3d.view_perspective = 'CAMERA'
        sp.viewport_shade = 'MATERIAL'
        sp.show_only_render = True
        sp.fx_settings.use_camera_dof = %s
        ov = dict(bpy.context.copy(), area=a, region=[r for r in a.regions if r.type == 'WINDOW'][0])
bpy.ops.render.opengl(ov, view_context=True)
bpy.data.images['Render Result'].save_render(r'%s')
resultado = 'ok'
'''


def nitidez(png):
    return ImageStat.Stat(Image.open(png).convert('L').filter(ImageFilter.FIND_EDGES)).mean[0]


def testar(t):
    cena = t.gerar(CENA)
    nitida = t.gerar(CENA + 'g.use_dof = False\n', nome='nitida')
    jogo_png, jnit_png, on_png, off_png = (str(t.pasta / n) for n in ('jogo.png', 'jogo_nitido.png', 'on.png', 'off.png'))

    for arq, png in ((cena, jogo_png), (nitida, jnit_png)):
        j = t.jogo(arq, largura=L, altura=A)
        j.esperar(frames=30)
        j.tela(arquivo=png)

    e = t.editor(cena)
    py(e, RENDER % ('False', off_png))
    py(e, RENDER % ('True', on_png))

    # largura do borrão na borda direita do cubo da frente (linha 290): pixels entre 10% e 90% do
    # degrau; o brilho de cada lado muda com o shading, a largura vem do DOF
    def largura(png):
        # do primeiro pixel que sai do escuro do cubo até chegar a 90% do valor em x=560
        im = Image.open(png).convert('L')
        v = [im.getpixel((x, 290)) for x in range(490, 561)]
        fim = v[0] + (v[-1] - v[0]) * 0.9
        ini = next(k for k, c in enumerate(v) if c > v[0] + 10)
        return next(k for k, c in enumerate(v) if c >= fim) - ini
    lj, lp, ln = largura(jogo_png), largura(on_png), largura(off_png)
    t.nota('largura da borda borrada: jogo %d px, prévia %d px, sem prévia %d px' % (lj, lp, ln))
    assert lp > ln + 10, 'a prévia não borrou'
    assert abs(lj - lp) <= max(6, lj * 0.3), 'o borrão da prévia não tem a largura do jogo'
