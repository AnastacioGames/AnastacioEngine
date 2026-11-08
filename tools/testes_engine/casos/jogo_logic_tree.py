"""Logic Tree compilada roda no jogo: Frames de Estado, Wait (Then) e Go To State."""

CENA = '''
import range_logic_tree as lt
cube = bpy.data.objects['Cube']
cube.game.physics_type = 'NO_COLLISION'
sc = bpy.context.scene
sc.objects.active = cube
for n in ('indo', 'voltando'):
    bpy.ops.object.game_property_new(type='INT', name=n)

tree = bpy.data.node_groups.new('Teste', lt.TREE_ID)


def no(tipo, frame=None, **campos):
    n = tree.nodes.new(tipo)
    for k, v in campos.items():
        setattr(n, k, v)
    if frame is not None:
        n.parent = frame
    return n


def estado(nome, x, inicial=False):
    f = tree.nodes.new('NodeFrame')
    f.label, f.range_logic_state, f.range_logic_initial = nome, True, inicial
    f.location = (x, 0)
    return f


indo, voltando = estado('Indo', 0, True), estado('Voltando', 800)
for f, prop in ((indo, 'indo'), (voltando, 'voltando')):
    tick = no('RangeLogicAlways', f, label='Tick ' + prop, use_pulse_true_level=True)
    soma = no('RangeLogicAddProperty', f, label='Soma ' + prop, property=prop, value='1')
    tree.links.new(tick.outputs[0], soma.inputs[0])
inicio = no('RangeLogicAlways', indo, label='Entrou')
espera = no('RangeLogicWait', indo, label='Espera', duration=0.2)
vai = no('RangeLogicGoToState', indo, label='Vai', state='Voltando')
tree.links.new(inicio.outputs[0], espera.inputs[0])
tree.links.new(espera.outputs[0], vai.inputs[0])

cube.logic_tree = tree
erros = lt.compile_object(cube)
assert not erros, erros
'''

LER = "o = cena().objects['Cube']; resultado = [o['indo'], o['voltando']]"


def testar(t):
    j = t.jogo(t.gerar(CENA))
    for _ in range(30):
        j.esperar(frames=30)
        indo, voltando = j.py(codigo=LER)
        if voltando > 0:
            break
    assert indo > 0, 'estado inicial não rodou: %s' % [indo, voltando]
    assert voltando > 0, 'Go To State não trocou de estado: %s' % [indo, voltando]
    j.esperar(frames=20)
    indo2, voltando2 = j.py(codigo=LER)
    assert indo2 == indo, 'estado antigo continuou rodando (%s -> %s)' % (indo, indo2)
    assert voltando2 > voltando, 'estado novo parou (%s -> %s)' % (voltando, voltando2)
    t.nota('indo %d, voltando %d' % (indo2, voltando2))
