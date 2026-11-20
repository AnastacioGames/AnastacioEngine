"""Prévia na 3D View, Fase 5 (docs/plano-previa-viewport.md): partículas GPU do jogo (Object.use_gpu_particles).
Um Empty emissor de nuvem amarela sobre fundo preto: o jogo mostra as partículas; a viewport em Material com
Realtime ligado também (mesmo RAS_ParticleBuffer, simulado pelo relógio real); com Realtime desligado a prévia
fica sem partículas, como antes. Compara a fração de pixels amarelos (a posição varia com o sorteio)."""
import time
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

em = bpy.data.objects.new('Emissor', None)
sc.objects.link(em)
em.location = (0, 0, 0)
em.use_gpu_particles = True
g = em.gpu_particles
g.particle_count = 400
g.lifetime = 3.0
g.gravity = (0, 0, 0)
g.velocity = (0, 0, 0.6)
g.velocity_randomness = 0.4
g.emitter_radius = 0.9
g.size = 0.35
g.end_size = 0.35
g.color = (1, 1, 0, 1)
g.end_color = (1, 1, 0, 1)

cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
sc.objects.link(cam)
cam.location = (0, -8, 1.5)
cam.rotation_euler = (Vector((0, 0, 1.5)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
cam.data.lens = 35
sc.camera = cam
for ob in sc.objects:
    ob.select = False
'''

PREPARAR = '''
import bpy, time
for a in bpy.context.screen.areas:
    if a.type == 'VIEW_3D':
        sp = a.spaces.active
        sp.region_3d.view_perspective = 'CAMERA'
        sp.viewport_shade = 'MATERIAL'
        sp.show_only_render = True
        sp.realtime_viewport_shading = %s
        r = [r for r in a.regions if r.type == 'WINDOW'][0]
        caixa = (r.x, bpy.context.window.height - r.y - r.height, r.x + r.width, bpy.context.window.height - r.y)
# 3 s de relógio real: a simulação anda pelo tempo entre os redesenhos
for i in range(60):
    time.sleep(0.05)
    bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
resultado = list(caixa)
'''


def amarelos(im):
    n = sum(1 for r, g, b in im.getdata() if r > 120 and g > 120 and b < 90)
    return n / float(im.size[0] * im.size[1])


def recorte(e, png, caixa):
    e.pedir("tela", arquivo=png)
    im = Image.open(png).convert('RGB').crop(caixa)
    w, h = im.size
    im = im.crop((w // 10, h // 10, w * 9 // 10, h * 9 // 10))
    im.save(png)
    return im


def testar(t):
    cena = t.gerar(CENA)

    j = t.jogo(cena, largura=960, altura=540)
    j.esperar(frames=90)
    j.tela(arquivo=str(t.pasta / 'jogo.png'))
    j.fechar()

    e = t.editor(cena)
    caixa = py(e, PREPARAR % 'True')
    com = recorte(e, str(t.pasta / 'com.png'), caixa)
    caixa = py(e, PREPARAR % 'False')
    sem = recorte(e, str(t.pasta / 'sem.png'), caixa)

    fj, fc, fs = amarelos(Image.open(str(t.pasta / 'jogo.png')).convert('RGB')), amarelos(com), amarelos(sem)
    t.nota('fração de pixels amarelos: jogo %.4f, prévia com Realtime %.4f, sem %.4f' % (fj, fc, fs))
    assert fj > 0.003, 'o jogo não mostrou as partículas'
    assert fc > 0.003, 'a prévia não mostrou as partículas com Realtime ligado'
    assert fs < fc * 0.1, 'sem Realtime a prévia ainda mostra partículas'
    assert 0.25 < fc / fj < 4.0, 'a quantidade de partículas da prévia não bate com a do jogo (%.2fx)' % (fc / fj)
