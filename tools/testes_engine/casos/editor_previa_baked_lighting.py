"""Prévia na 3D View, Fase 4 (docs/plano-previa-viewport.md): Baked Lighting. Sala com parede vermelha cozida
pelo Cycles (modo Indirect); na viewport em shading Material a luz rebatida do atlas tinge o chão de vermelho
perto da parede, como no jogo. Desligar Render > Baked Lighting (ae_lightmap_use) tira o efeito na prévia."""
import os
from PIL import Image, ImageStat
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
# a grade troca a luz ambiente do World (env_probe_mirror): só entra com Environment Lighting
w.light_settings.use_environment_light = True
sc.world = w

def mat(nome, cor):
    m = bpy.data.materials.new(nome)
    m.use_nodes = True
    m.node_tree.nodes.clear()
    # Principled: a Diffuse BSDF não lê a luz ambiente (node_shader_gpu_world_env), onde a grade entra
    s = m.node_tree.nodes.new('ShaderNodeBsdfPrincipled')
    s.inputs['Base Color'].default_value = cor
    s.inputs['Roughness'].default_value = 1.0
    s.inputs['Specular'].default_value = 0.0
    o = m.node_tree.nodes.new('ShaderNodeOutputMaterial')
    m.node_tree.links.new(s.outputs[0], o.inputs['Surface'])
    return m

def cubo(loc, esc, m):
    bpy.ops.mesh.primitive_cube_add(radius=1, location=loc)
    ob = sc.objects.active
    ob.scale = esc
    ob.data.materials.append(m)

cubo((0, 0, -0.1), (4, 4, 0.1), mat('Chao', (0.8, 0.8, 0.8, 1)))
cubo((-2.1, 0, 2), (0.1, 4, 2), mat('Vermelha', (0.9, 0.02, 0.02, 1)))
sol = bpy.data.objects.new('Sol', bpy.data.lamps.new('Sol', 'SUN'))
sc.objects.link(sol)
# sol rasante: a parede leva luz cheia, o chão quase nada, e a luz rebatida (sondas) aparece nele
sol.rotation_euler = Vector((-1, 0.1, -0.12)).to_track_quat('-Z', 'Y').to_euler()

cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
sc.objects.link(cam)
cam.location = (5, -7, 5)
cam.rotation_euler = (Vector((0, 0, 0.5)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
cam.data.lens = 28
sc.camera = cam
for ob in sc.objects:
    ob.select = False

# cozimento Cycles em background: só indireta, pequeno e rápido; a imagem sai empacotada no .range
st = sc.ae_lightmap_settings
st.mode = __import__('os').environ.get('MODO_BAKE', 'INDIRECT')
st.resolution = '256'
st.samples = 16
st.use_gpu = False
st.use_volume = False
st.use_denoise = False
sc.update()
bpy.ops.scene.ae_lightmap_bake()
assert sc.ae_lightmap_use and sc.ae_lightmap in bpy.data.images, 'bake nao gerou o atlas'
bpy.ops.wm.save_as_mainfile(filepath=saida)
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


def chao_vermelho(im):
    """Quanto o chão (pixels claros) puxa para o vermelho: média de r - g nos pixels com g alto."""
    px = [p for p in im.getdata() if p[1] > 60 and p[0] - p[1] < 120]
    return sum(r - g for r, g, b in px) / max(len(px), 1)


def recorte(e, png, caixa):
    e.pedir("tela", arquivo=png)
    im = Image.open(png).convert('RGB').crop(caixa)
    w, h = im.size
    im = im.crop((w // 10, h // 10, w * 9 // 10, h * 9 // 10))
    im.save(png)
    return im


def chao_vermelho(im):
    """Quanto o chão (pixels claros) puxa para o vermelho: média de r - g nos pixels com g alto."""
    px = [p for p in im.getdata() if p[1] > 60 and p[0] - p[1] < 120]
    return sum(r - g for r, g, b in px) / max(len(px), 1)



DESLIGAR = """
import bpy
bpy.context.scene.ae_lightmap_use = %s
"""


def testar(t):
    cena = t.gerar(CENA, limite=600)
    j = t.jogo(cena, largura=960, altura=540)
    j.esperar(frames=30)
    j.tela(arquivo=str(t.pasta / 'jogo.png'))
    j.fechar()

    e = t.editor(cena)
    caixa = py(e, PREPARAR)
    com = recorte(e, str(t.pasta / 'com.png'), caixa)
    py(e, DESLIGAR % 'False')
    caixa = py(e, PREPARAR)
    sem = recorte(e, str(t.pasta / 'sem.png'), caixa)
    py(e, DESLIGAR % 'True')
    caixa = py(e, PREPARAR)
    de_novo = recorte(e, str(t.pasta / 'de_novo.png'), caixa)

    jogo = Image.open(str(t.pasta / 'jogo.png')).convert('RGB')
    v = chao_vermelho
    m = lambda im: sum(ImageStat.Stat(im).mean) / 3
    t.nota('chão p/ vermelho (r-g): jogo %.1f, prévia sem %.1f, com %.1f (religado %.1f); brilho jogo %.1f, sem %.1f, com %.1f'
           % (v(jogo), v(sem), v(com), v(de_novo), m(jogo), m(sem), m(com)))
    assert v(com) > v(sem) + 3.0, 'a luz cozida não apareceu na prévia'
    assert abs(v(com) - v(jogo)) < 5.0, 'a luz cozida na prévia não bate com a do jogo'
    assert abs(v(com) - v(de_novo)) < 1.0, 'religar o Baked Lighting não volta ao mesmo resultado'
