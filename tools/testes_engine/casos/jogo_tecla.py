"""Tecla simulada chega aos logic bricks: W segurado move o cubo; print do jogo não sai preto."""

CENA = '''
cube = bpy.data.objects['Cube']
bpy.context.scene.objects.active = cube
bpy.ops.logic.sensor_add(type='KEYBOARD', object=cube.name)
s = cube.game.sensors[-1]; s.key = 'W'
bpy.ops.logic.actuator_add(type='MOTION', object=cube.name)
a = cube.game.actuators[-1]; a.offset_location = (0, 0.1, 0)
bpy.ops.logic.controller_add(type='LOGIC_AND', object=cube.name)
cube.game.controllers[-1].link(sensor=s, actuator=a)
'''


def testar(t):
    j = t.jogo(t.gerar(CENA))
    y = "resultado = cena().objects['Cube'].worldPosition.y"
    y0 = j.py(codigo=y)
    j.esperar(frames=10)
    assert j.py(codigo=y) == y0, 'cubo andou sem tecla'
    j.tecla(tecla='W', segurar=True)
    j.esperar(frames=30)
    j.soltar(tecla='W')
    j.esperar(frames=5)
    y1 = j.py(codigo=y)
    assert y1 - y0 > 1.0, 'W não moveu o cubo (%s -> %s)' % (y0, y1)
    j.esperar(frames=10)
    assert j.py(codigo=y) == y1, 'cubo continuou andando depois de soltar W'
    t.nota('y %.2f -> %.2f' % (y0, y1))

    png = str(t.pasta / 'tela.png')
    j.tela(arquivo=png)
    from PIL import Image
    img = Image.open(png).convert('L')
    claro = sum(1 for p in img.getdata() if p > 30) / (img.width * img.height)
    assert claro > 0.5, 'print do jogo quase todo preto (%.0f%% claro)' % (claro * 100)
