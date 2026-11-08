"""UI Tree no jogo: clique real alterna o Toggle e posiciona o Slider, gravando nas propriedades."""

CENA = '''
import range_ui_tree as ui
sc = bpy.context.scene
camera = bpy.data.objects['Camera']
sc.objects.active = camera
bpy.ops.object.game_property_new(type='BOOL', name='som')
bpy.ops.object.game_property_new(type='FLOAT', name='volume')
tree = bpy.data.node_groups.new('Menu UI', ui.UITree.bl_idname)
tree.use_fake_user = True
f = tree.nodes.new('NodeFrame')
f.name = f.label = 'Menu'
f.ui_screen, f.shrink = True, False
f.width, f.height = 640, 360
t = tree.nodes.new(ui.UIToggleNode.bl_idname)
t.parent, t.location, t.width, t.prop_name = f, (220, -100), 200, 'som'
s = tree.nodes.new(ui.UISliderNode.bl_idname)
s.parent, s.location, s.width, s.prop_name = f, (220, -220), 200, 'volume'
s.min_value, s.max_value = 0.0, 10.0
ui.write_bake(tree, sc)
ui.setup_game_logic(camera, tree)
'''

PONTO = '''
import Range, range_ui_runtime as r
u = r.get()
b = next(b for b in u.screen.focusables if b.kind == %r)
x, y, w, h = u.screen.place(b.data, Range.render.getWindowWidth(), Range.render.getWindowHeight())
resultado = [x + w * %f, Range.render.getWindowHeight() - (y + h / 2)]
'''


def valor(j, nome):
    return j.py(codigo="resultado = cena().objects['Camera'][%r]" % nome)


def clicar(j, tipo, frac):
    x, y = j.py(codigo=PONTO % (tipo, frac))
    j.mouse(x=int(x), y=int(y))
    j.esperar(frames=3)
    j.tecla(tecla='LEFTMOUSE', frames=3)
    j.esperar(frames=6)


def testar(t):
    j = t.jogo(t.gerar(CENA))
    j.esperar(frames=10)
    a = valor(j, 'som')
    clicar(j, 'TOGGLE', 0.5)
    b = valor(j, 'som')
    assert b != a, 'clique não alternou o Toggle (%s)' % a
    clicar(j, 'TOGGLE', 0.5)
    assert valor(j, 'som') == a, 'segundo clique não voltou o Toggle'

    clicar(j, 'SLIDER', 0.75)
    alto = valor(j, 'volume')
    assert 6 < alto < 9, 'Slider a 75%% de 0..10 deu %s' % alto
    clicar(j, 'SLIDER', 0.25)
    baixo = valor(j, 'volume')
    assert 1 < baixo < 4, 'Slider a 25%% de 0..10 deu %s' % baixo
    t.nota('toggle %s -> %s; slider %.2f, %.2f' % (a, b, alto, baixo))
