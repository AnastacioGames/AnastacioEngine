"""Prévia na 3D View, Fase 4 (docs/plano-previa-viewport.md): sombra colorida. Um vidro vermelho com
Colored Shadows (Cast Shadows + Alpha Blend) sobre um chão branco, sol com sombra: na viewport em
shading Material a sombra dele no chão sai tingida de vermelho, como no jogo (KX_ShadowRenderer);
sem a opção ela é cinza."""
from PIL import Image, ImageStat
from rodar import py

CENA = '''
from mathutils import Vector
sc = bpy.context.scene
sc.render.engine = 'BLENDER_GAME'
for ob in list(sc.objects):
    sc.objects.unlink(ob)
w = bpy.data.worlds.new('W')
w.horizon_color = (0.05, 0.05, 0.05)
sc.world = w

bpy.ops.mesh.primitive_plane_add(radius=6, location=(0, 0, 0))
chao = sc.objects.active
m = bpy.data.materials.new('Chao')
m.diffuse_color = (0.9, 0.9, 0.9)
chao.data.materials.append(m)

bpy.ops.mesh.primitive_cube_add(radius=1, location=(0, 0, 2.0))
vidro = sc.objects.active
vidro.name = 'Vidro'
vidro.scale = (1.5, 1.5, 0.05)
v = bpy.data.materials.new('Vidro')
v.diffuse_color = (1.0, 0.05, 0.05)
v.use_transparency = True
v.alpha = 0.5
v.use_cast_shadows = True
v.use_colored_shadows = True
v.game_settings.alpha_blend = 'ALPHA'
vidro.data.materials.append(v)

lamp = bpy.data.lamps.new('Sol', 'SUN')
lamp.use_shadow = True
lamp.shadow_frustum_size = 12
sol = bpy.data.objects.new('Sol', lamp)
sc.objects.link(sol)
sol.location = (0, 0, 10)
sol.rotation_euler = (0.7, 0, 0.5)

cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
sc.objects.link(cam)
cam.location = (2, -10, 12)
cam.rotation_euler = (Vector((0, 0, 0)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
sc.camera = cam
'''

PREPARAR = '''
import bpy
bpy.data.materials['Vidro'].use_colored_shadows = %s
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


def vermelhos(im):
    """Pixels avermelhados (vidro + sombra tingida) e escuros (sombra preta)."""
    px = list(im.getdata())
    return (sum(1 for r, g, b in px if r - g > 40), sum(1 for r, g, b in px if r + g + b < 120))


def testar(t):
    cena = t.gerar(CENA)
    j = t.jogo(cena, largura=960, altura=540)
    j.esperar(frames=30)
    j.tela(arquivo=str(t.pasta / 'jogo.png'))
    j.fechar()
    e = t.editor(cena)
    # ligada desde o início (a luz nasce com o alvo de cor), depois desligada e ligada de novo
    caixa = py(e, PREPARAR % 'True')
    cor0 = recorte(e, str(t.pasta / 'colorida_inicio.png'), caixa)
    caixa = py(e, PREPARAR % 'False')
    cinza = recorte(e, str(t.pasta / 'cinza.png'), caixa)
    caixa = py(e, PREPARAR % 'True')
    cor = recorte(e, str(t.pasta / 'colorida.png'), caixa)
    w, h = cinza.size
    lado = Image.new('RGB', (w * 2, h))
    lado.paste(cinza, (0, 0))
    lado.paste(cor, (w, 0))
    lado.save(str(t.pasta / 'lado.png'))

    jogo = Image.open(str(t.pasta / 'jogo.png')).convert('RGB')
    (v_jogo, p_jogo), (v_cinza, p_cinza), (v_cor, p_cor) = vermelhos(jogo), vermelhos(cinza), vermelhos(cor)
    (v_cor0, _) = vermelhos(cor0)
    n = lambda im: im.width * im.height
    f = lambda v, im: 100.0 * v / n(im)
    t.nota('pixels vermelhos: jogo %.1f%%, prévia sem %.1f%%, com %.1f%% (ligada desde o início %.1f%%); '
           'sombra preta: jogo %.1f%%, sem %.1f%%, com %.1f%%'
           % (f(v_jogo, jogo), f(v_cinza, cinza), f(v_cor, cor), f(v_cor0, cor0),
              f(p_jogo, jogo), f(p_cinza, cinza), f(p_cor, cor)))
    assert f(p_cinza, cinza) > 0.3, 'controle: sem Colored Shadows o vidro devia fazer sombra preta'
    assert abs(f(v_cor, cor) - f(v_jogo, jogo)) < 2.0, 'a sombra tingida da prévia não bate com a do jogo'
    assert f(p_cor, cor) < 0.3, 'o vidro ainda faz sombra preta com Colored Shadows'
    assert abs(f(v_cor, cor) - f(v_cor0, cor0)) < 1.0, 'ligar a opção depois não dá o mesmo resultado'
