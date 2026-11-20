"""Prévia na 3D View, Fase 4 (docs/plano-previa-viewport.md): Probe Volume GI. Uma sala com parede vermelha
e um Empty "probe_volume" cozido pelo próprio jogo (RANGE_PROBE_VOLUME_BAKE, como o Bake Probes): na viewport
em shading Material a luz salva (<cena>.probes) tinge o chão branco de vermelho perto da parede, como no jogo;
sem o arquivo a prévia fica como antes."""
import os, time
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

caixa = bpy.data.objects.new('Sondas', None)
sc.objects.link(caixa)
caixa.empty_draw_type = 'CUBE'
caixa.location = (0, 0, 1.5)
caixa.scale = (3.9, 3.9, 1.6)
sc.objects.active = caixa
bpy.ops.object.game_property_new(type='FLOAT', name='probe_volume')
caixa.game.properties['probe_volume'].value = 1.5

cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
sc.objects.link(cam)
cam.location = (5, -7, 5)
cam.rotation_euler = (Vector((0, 0, 0.5)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
cam.data.lens = 28
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


def chao_vermelho(im):
    """Quanto o chão (pixels claros) puxa para o vermelho: média de r - g nos pixels com g alto."""
    px = [p for p in im.getdata() if p[1] > 60 and p[0] - p[1] < 120]
    return sum(r - g for r, g, b in px) / max(len(px), 1)


def testar(t):
    cena = t.gerar(CENA)
    probes = t.pasta / 'Scene.probes'
    # cozimento pelo jogo, como o Bake Probes: salva a luz e fecha sozinho
    t.jogo(cena, largura=320, altura=180,
           env_extra={'RANGE_PROBE_VOLUME_BAKE': 'all', 'RANGE_PROBE_VOLUME_FILE': str(probes)})
    pid = controle.ultimo_pid
    limite = time.time() + 90
    while controle.rodando(pid) and time.time() < limite:
        time.sleep(0.5)
    assert probes.exists() and probes.stat().st_size > 100, 'o jogo não salvou a luz das sondas'

    j = t.jogo(cena, largura=960, altura=540)
    j.esperar(frames=30)
    j.tela(arquivo=str(t.pasta / 'jogo.png'))
    j.fechar()

    e = t.editor(cena)
    caixa = py(e, PREPARAR)
    com = recorte(e, str(t.pasta / 'com.png'), caixa)
    os.replace(str(probes), str(t.pasta / 'guardado.probes'))
    caixa = py(e, PREPARAR)
    sem = recorte(e, str(t.pasta / 'sem.png'), caixa)
    os.replace(str(t.pasta / 'guardado.probes'), str(probes))
    caixa = py(e, PREPARAR)
    de_novo = recorte(e, str(t.pasta / 'de_novo.png'), caixa)

    jogo = Image.open(str(t.pasta / 'jogo.png')).convert('RGB')
    v_jogo, v_sem, v_com, v_novo = chao_vermelho(jogo), chao_vermelho(sem), chao_vermelho(com), chao_vermelho(de_novo)
    m = lambda im: sum(ImageStat.Stat(im).mean) / 3
    t.nota('chão puxando p/ vermelho (r-g): jogo %.1f, prévia sem %.1f, com %.1f (arquivo de volta %.1f); '
           'brilho jogo %.1f, sem %.1f, com %.1f' % (v_jogo, v_sem, v_com, v_novo, m(jogo), m(sem), m(com)))
    assert v_com > v_sem + 3.0, 'a luz salva das sondas não apareceu na prévia'
    assert abs(v_com - v_jogo) < 5.0, 'a luz das sondas na prévia não bate com a do jogo'
    assert abs(v_com - v_novo) < 1.0, 'recarregar o arquivo não dá o mesmo resultado'
