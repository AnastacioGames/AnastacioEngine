"""Prévia na 3D View, Fase 3 (docs/plano-previa-viewport.md): TAA do jogo (Scene > Post-process > TAA) na
viewport com Game Preview > TAA. Os redesenhos da vista são os quadros: com a vista parada o jitter
converge e as bordas inclinadas ganham tons intermediários; convergido, dois quadros seguidos quase
não mudam (sem tremer)."""
from PIL import Image, ImageChops, ImageStat
from rodar import py

CENA = '''
sc = bpy.context.scene
sc.scenefx_settings.use_taa = True
bpy.ops.mesh.primitive_plane_add(radius=20)
for i in range(-3, 4):
    bpy.ops.mesh.primitive_cube_add(location=(i * 3, 6, 1), rotation=(0.3, 0.2, 0.35))
'''

PREPARAR = '''
import bpy
for a in bpy.context.screen.areas:
    if a.type == 'VIEW_3D':
        sp = a.spaces.active
        sp.region_3d.view_perspective = 'CAMERA'
        sp.viewport_shade = 'SOLID'
        sp.show_only_render = True
        sp.fx_settings.use_game_taa = %s
        r = [r for r in a.regions if r.type == 'WINDOW'][0]
        caixa = (r.x, bpy.context.window.height - r.y - r.height, r.x + r.width, bpy.context.window.height - r.y)
bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=40)
resultado = list(caixa)
'''


def recorte(e, png, caixa):
    e.pedir("tela", arquivo=png)
    im = Image.open(png).convert('L').crop(caixa)
    im.save(png)
    return im


def meio_tom(im):
    """Pixels de borda em meio-tom no miolo da vista (longe da UI): entre dois vizinhos opostos bem
    diferentes, com valor longe dos dois. Borda serrilhada quase não tem; com TAA ganha muitos."""
    w, h = im.size
    im = im.crop((w // 10, h // 10, w * 9 // 10, h * 8 // 10))
    w, h = im.size
    px = im.load()
    n = 0
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            p = px[x, y]
            for a, c in ((px[x - 1, y], px[x + 1, y]), (px[x, y - 1], px[x, y + 1])):
                lo, hi = min(a, c), max(a, c)
                if hi - lo > 80 and lo + 15 < p < hi - 15:
                    n += 1
                    break
    return n


def testar(t):
    cena = t.gerar(CENA)
    e = t.editor(cena)

    caixa = py(e, PREPARAR % 'False')
    off = recorte(e, str(t.pasta / 'off.png'), caixa)
    caixa = py(e, PREPARAR % 'True')
    on = recorte(e, str(t.pasta / 'on.png'), caixa)
    on2 = recorte(e, str(t.pasta / 'on2.png'), caixa)

    tremor = ImageStat.Stat(ImageChops.difference(on, on2)).mean[0]
    d_off, d_on = meio_tom(off), meio_tom(on)
    t.nota('pixels de borda em meio-tom: sem TAA %d, com TAA %d; diferença entre quadros convergidos %.3f'
           % (d_off, d_on, tremor))
    assert d_on > d_off * 2, 'o TAA não suavizou as bordas'
    assert tremor < 1.0, 'a imagem convergida ainda treme'
