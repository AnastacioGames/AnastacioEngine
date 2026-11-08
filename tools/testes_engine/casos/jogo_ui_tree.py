"""UI Tree no jogo: clique real do mouse troca de tela; clique fora e botão desligado não fazem nada."""

CENA = '''
import range_ui_tree as ui
sc = bpy.context.scene
camera = bpy.data.objects['Camera']
tree = bpy.data.node_groups.new('Menu UI', ui.UITree.bl_idname)
tree.use_fake_user = True


def tela(nome, y):
    f = tree.nodes.new('NodeFrame')
    f.name = f.label = nome
    f.ui_screen, f.shrink = True, False
    f.location = (0, y)
    f.width, f.height = 640, 360
    return f


def botao(frame, texto, x, y):
    n = tree.nodes.new(ui.UIButtonNode.bl_idname)
    n.text, n.parent, n.location, n.width = texto, frame, (x, y), 200
    return n


def trocar(origem, destino, y):
    a = tree.nodes.new(ui.UIScreenNode.bl_idname)
    a.value, a.location = destino, (800, y)
    tree.links.new(origem.outputs['On Click'], a.inputs[0])


menu, opcoes = tela('Menu', 0), tela('Opcoes', -500)
abrir = botao(menu, 'Abrir', 220, -120)
travado = botao(menu, 'Travado', 220, -220)
travado.enabled_prop = 'liberado'
voltar = botao(opcoes, 'Voltar', 220, -120)
trocar(abrir, 'Opcoes', 0)
trocar(travado, 'Opcoes', -100)
trocar(voltar, 'Menu', -200)
ui.write_bake(tree, sc)
ui.setup_game_logic(camera, tree)
'''

TELA = "resultado = cena().objects['Camera']['ui_screen']"
CENTRO = '''
import Range, range_ui_runtime as r
u = r.get()
b = next(b for b in u.screen.focusables if b.data['name'] == %r)
x, y, w, h = u.screen.place(b.data, Range.render.getWindowWidth(), Range.render.getWindowHeight())
resultado = [x + w / 2, Range.render.getWindowHeight() - (y + h / 2)]
'''


def clicar(j, x, y):
    j.mouse(x=int(x), y=int(y))
    j.esperar(frames=3)
    j.tecla(tecla='LEFTMOUSE', frames=3)
    j.esperar(frames=45)  # cobre o fade entre telas


def centro(j, nome):
    return j.py(codigo=CENTRO % nome)


def testar(t):
    j = t.jogo(t.gerar(CENA))
    j.esperar(frames=10)
    assert j.py(codigo=TELA) == 'Menu', 'não começou no Menu: %s' % j.py(codigo=TELA)
    clicar(j, 5, 5)
    assert j.py(codigo=TELA) == 'Menu', 'clique fora dos botões trocou de tela'
    clicar(j, *centro(j, 'Travado'))
    assert j.py(codigo=TELA) == 'Menu', 'botão desligado reagiu ao clique'
    clicar(j, *centro(j, 'Abrir'))
    assert j.py(codigo=TELA) == 'Opcoes', 'clique em Abrir não trocou: %s' % j.py(codigo=TELA)
    clicar(j, *centro(j, 'Voltar'))
    assert j.py(codigo=TELA) == 'Menu', 'clique em Voltar não trocou: %s' % j.py(codigo=TELA)
