"""Sanidade do jogo para o refactor de RAS_ParticleBuffer::Configure (Fase 5 da prévia): um emissor de
partículas por look aparece na tela do jogo (pixels fora do fundo preto)."""
from PIL import Image

CENA = '''
sc = bpy.context.scene
sc.render.engine = 'BLENDER_GAME'
for ob in list(sc.objects):
    sc.objects.unlink(ob)
w = bpy.data.worlds.new('W'); w.horizon_color = (0, 0, 0); sc.world = w
bpy.ops.mesh.primitive_cube_add(radius=0.1, location=(0, 0, 0))
em = sc.objects.active
em.use_gpu_particles = True
gp = em.gpu_particles
LOOK_LINHAS
gp.particle_count = 300
gp.size = 0.6
gp.color = (1.0, 0.3, 0.1, 1.0)
gp.lifetime = 2.0
cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
sc.objects.link(cam)
cam.location = (0, -7, 2)
cam.rotation_euler = (1.4, 0, 0)
sc.camera = cam
'''


def cobertura(im):
    px = list(im.getdata())
    return sum(1 for p in px if max(p) > 40) / len(px)


def testar(t):
    for nome, look in (('padrao', ''), ('fumaca', "gp.particle_look = 'SMOKE'"), ('fogo', "gp.particle_look = 'FIRE'")):
        cena = t.gerar(CENA.replace('LOOK_LINHAS', look), nome=nome)
        j = t.jogo(cena, largura=640, altura=360)
        j.esperar(frames=90)
        arq = str(t.pasta / (nome + '_jogo.png'))
        j.tela(arquivo=arq)
        j.fechar()
        c = cobertura(Image.open(arq).convert('RGB'))
        t.nota('%s: cobertura %.4f' % (nome, c))
        assert c > 0.003, nome + ': nenhuma partícula visível no jogo'
