"""Prévia na 3D View, Fase 4 (docs/plano-previa-viewport.md): HLOD. O original (cubo vermelho) tem um nível
invisível cujo objeto é o proxy da célula (cubo verde, longe, base invisível); o jogo mede a distância do proxy.
Câmera a 12 m do original mas a 8 m do proxy, com Distance 9: o jogo mostra o original, e a viewport deve
mostrar o mesmo (medindo do proxy); com a câmera longe do proxy (Distance 5) os dois trocam: só o proxy."""
import os
import sys
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import controle
from rodar import py
from editor_previa_impostor import PREPARAR, recorte

CENA = '''
from mathutils import Vector
sc = bpy.context.scene
sc.render.engine = 'BLENDER_GAME'
sc.game_settings.use_shading_nodes = True
for ob in list(sc.objects):
    sc.objects.unlink(ob)
w = bpy.data.worlds.new('W'); w.horizon_color = (0, 0, 0); sc.world = w

def cubo(nome, loc, cor):
    bpy.ops.mesh.primitive_cube_add(radius=1, location=loc)
    ob = sc.objects.active
    ob.name = nome
    m = bpy.data.materials.new(nome); m.use_nodes = True
    m.node_tree.nodes.clear()
    e = m.node_tree.nodes.new('ShaderNodeEmission'); e.inputs['Color'].default_value = cor
    o = m.node_tree.nodes.new('ShaderNodeOutputMaterial')
    m.node_tree.links.new(e.outputs[0], o.inputs['Surface'])
    ob.data.materials.append(m)
    return ob

orig = cubo('Orig', (0, 0, 1), (1, 0, 0, 1))
proxy = cubo('Proxy', (0, -20, 1), (0, 1, 0, 1))
DIST = HLOD_DIST

sc.objects.active = orig
bpy.ops.object.lod_add()
lv = orig.lod_levels[-1]
lv.object = proxy
lv.use_mesh = False
lv.use_material = False
lv.use_invisible_mesh = True
lv.use_object_hysteresis = True
lv.object_hysteresis_percentage = 0
lv.distance = DIST

sc.objects.active = proxy
bpy.ops.object.lod_add()
base, far = proxy.lod_levels[0], proxy.lod_levels[1]
base.use_invisible_mesh = True
far.object = proxy
far.use_mesh = True
far.use_material = True
far.use_object_hysteresis = True
far.object_hysteresis_percentage = 0
far.distance = DIST

# a camera enxerga os dois cubos: fica entre eles de lado
cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
sc.objects.link(cam)
cam.location = (0, -12, 1)
cam.rotation_euler = (1.5707963, 0, 0)
cam.data.lens = 12
sc.camera = cam
for ob in sc.objects:
    ob.select = False
'''


def cores(im):
    px = list(im.getdata())
    n = len(px)
    vm = sum(1 for p in px if p[0] > 150 and p[1] < 80) / n
    vd = sum(1 for p in px if p[1] > 150 and p[0] < 80) / n
    return vm, vd


def testar(t):
    # câmera olhando para +Y: o original (0,0) fica na frente, o proxy (0,-20) atrás dela; por isso a câmera
    # gira para -Y no segundo caso. Aqui o proxy fica em (0,-20), 8 m atrás da câmera em (0,-12): o que
    # importa é a distância usada pelo nível, não o que se vê do proxy.
    for nome, dist, esperado in (('perto', 9.0, 'vermelho'), ('longe', 5.0, 'sem_vermelho')):
        cena = t.gerar(CENA.replace('HLOD_DIST', str(dist)), nome=nome)
        j = t.jogo(cena, largura=960, altura=540)
        j.esperar(frames=30)
        j.tela(arquivo=str(t.pasta / (nome + '_jogo.png')))
        j.fechar()
        e = t.editor(cena)
        caixa = py(e, PREPARAR)
        im = recorte(e, str(t.pasta / (nome + '_previa.png')), caixa)
        jv = cores(Image.open(str(t.pasta / (nome + '_jogo.png'))).convert('RGB'))
        pv = cores(im)
        t.nota('%s: jogo vermelho/verde %.3f/%.3f, prévia %.3f/%.3f' % (nome, jv[0], jv[1], pv[0], pv[1]))
        assert (jv[0] > 0.003) == (esperado == 'vermelho'), nome + ': o jogo não fez o esperado'
        assert (pv[0] > 0.003) == (jv[0] > 0.003), nome + ': a prévia não bate com o jogo'
