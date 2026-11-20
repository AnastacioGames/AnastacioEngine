"""Prévia na 3D View, Fase 6: texto do jogo com caixa (Text Box). A prévia quebra as linhas pela largura da caixa
e mostra só a 1ª página, como o jogo (KX_FontObject::LayoutLines). Compara a altura do bloco de texto: sem
caixa é uma linha só; com caixa estreita são várias; com altura limitada, só as linhas da página."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rodar import py
from editor_previa_impostor import recorte
from editor_previa_particulas import PREPARAR

CENA = '''
import math
sc = bpy.context.scene
for ob in list(sc.objects):
    if ob.type != 'CAMERA':
        sc.objects.unlink(ob)
w = bpy.data.worlds.new('W'); w.horizon_color = (0, 0, 0); sc.world = w
cam = [o for o in sc.objects if o.type == 'CAMERA'][0]
sc.camera = cam
cam.location = (0, -8, 0); cam.rotation_euler = (math.pi / 2, 0, 0)
bpy.ops.object.text_add(location=(0, 0, 0))
tx = bpy.context.scene.objects.active
tx.rotation_euler = (math.pi / 2, 0, 0)
cu = tx.data
cu.body = 'um dois tres quatro cinco seis sete oito nove dez onze doze treze quatorze quinze'
cu.size = 0.5
cu.use_game_text_preview = True
tx.select = False
cu.text_boxes[0].width = BOXW
cu.text_boxes[0].height = BOXH
'''


def altura(im):
    """Altura (fração) da faixa vertical ocupada pelos pixels claros."""
    w, h = im.size
    px = im.load()
    linhas = [y for y in range(h) if any(max(px[x, y]) > 60 for x in range(0, w, 2))]
    return ((linhas[-1] - linhas[0] + 1) / h) if linhas else 0.0


def medir_caso(t, nome, largura, altura_caixa):
    cena = t.gerar(CENA.replace('BOXW', str(largura)).replace('BOXH', str(altura_caixa)), nome=nome)
    e = t.editor(cena)
    caixa = py(e, PREPARAR.replace('LIGADO', 'False'))
    caixa = py(e, "import bpy\nfor a in bpy.context.screen.areas:\n    if a.type == 'VIEW_3D':\n"
                  "        a.spaces.active.region_3d.view_perspective = 'CAMERA'\n"
                  "        a.spaces.active.show_only_render = True\n"
                  "bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=3)\nresultado = 1") and caixa
    im = recorte(e, str(t.pasta / (nome + '.png')), caixa)
    return altura(im)


def testar(t):
    livre = medir_caso(t, 'livre', 0.0, 0.0)
    larga = medir_caso(t, 'caixa', 3.0, 0.0)
    pagina = medir_caso(t, 'pagina', 3.0, 1.0)
    t.nota('altura livre %.3f, caixa %.3f, 1 pagina %.3f' % (livre, larga, pagina))
    assert livre > 0.01, 'o texto não apareceu'
    assert larga > livre * 1.8, 'a caixa não quebrou as linhas'
    assert livre * 0.9 < pagina < larga * 0.8, 'a altura da caixa não limitou a página'
