"""Force Field no modo Game: o painel da aba Physics mostra Strength, Flow, Falloff, distancias e avisa
nos tipos que o jogo ignora, sem precisar trocar o motor para Blender Render."""
import time
from rodar import py

CENA = '''
sc = bpy.context.scene
sc.render.engine = 'BLENDER_GAME'
o = bpy.data.objects.new('Vento', None)
sc.objects.link(o)
sc.objects.active = o
o.select = True
o.field.type = 'WIND'
o.field.use_game_field = True
o.field.use_max_distance = True
o.field.distance_max = 12.0
'''

ABRIR = '''
a = next(a for a in bpy.context.screen.areas if a.type == 'PROPERTIES')
sp = a.spaces.active
sp.context = 'PHYSICS'
ob = bpy.context.scene.objects['Vento']
ob.field.type = %r
resultado = [ob.field.type, sp.context]
'''


def tela(e, arquivo):
    r = e.pedir('tela', arquivo=arquivo, editor='PROPERTIES')
    assert r['ok'], r.get('traceback') or r['erro']


def testar(t):
    e = t.editor(t.gerar(CENA))
    for tipo in ('WIND', 'TURBULENCE', 'DRAG'):
        r = py(e, ABRIR % tipo)
        assert r[0] == tipo, r
        if tipo == 'WIND':
            for tp, vl in (('MOUSEMOVE', 'NOTHING'), ('LEFTMOUSE', 'PRESS'), ('LEFTMOUSE', 'RELEASE')):
                e.pedir('evento', tipo=tp, valor=vl, x=1515, y=136)
        time.sleep(1.5)
        e.pedir('evento', tipo='MOUSEMOVE', valor='NOTHING', x=1700, y=500)
        time.sleep(0.5)
        tela(e, str(t.pasta / (tipo + '.png')))
    t.nota('telas em %s' % t.pasta)
