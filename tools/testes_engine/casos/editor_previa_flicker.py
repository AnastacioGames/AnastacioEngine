"""Prévia na 3D View, Fase 5: lâmpada com a propriedade de jogo light_flicker. Com Game Preview > Particles
ligado o brilho do chão varia no tempo (como no jogo); desligado fica constante."""
import os
import sys
import time
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rodar import py
from editor_previa_impostor import recorte
from editor_previa_particulas import PREPARAR

CENA = '''
sc = bpy.context.scene
sc.render.engine = 'BLENDER_GAME'
for ob in list(sc.objects):
    sc.objects.unlink(ob)
w = bpy.data.worlds.new('W'); w.horizon_color = (0, 0, 0); sc.world = w
bpy.ops.mesh.primitive_plane_add(radius=5, location=(0, 0, 0))
bpy.ops.object.lamp_add(type='POINT', location=(0, 0, 2.5))
lp = bpy.context.scene.objects.active
lp.data.energy = 1.0
lp.data.distance = 12
bpy.context.scene.objects.active = lp
bpy.ops.object.game_property_new(type='FLOAT', name='light_flicker')
lp.game.properties['light_flicker'].value = 2.0
cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
sc.objects.link(cam)
cam.location = (0, -6, 6)
cam.rotation_euler = (0.9, 0, 0)
sc.camera = cam
'''


def brilho(im):
    px = list(im.convert('L').getdata())
    return sum(px) / len(px)


def amostras(t, e, caixa, nome, n=14):
    v = []
    for i in range(n):
        time.sleep(0.25)
        py(e, "import bpy\nbpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)\nresultado = 1")
        v.append(brilho(recorte(e, str(t.pasta / ('%s_%d.png' % (nome, i))), caixa)))
    return v


def testar(t):
    cena = t.gerar(CENA, nome='flicker')
    e = t.editor(cena)
    caixa = py(e, PREPARAR.replace('LIGADO', 'False'))
    off = amostras(t, e, caixa, 'off')
    caixa = py(e, PREPARAR.replace('LIGADO', 'True'))
    on = amostras(t, e, caixa, 'on')
    var_off = max(off) - min(off)
    var_on = max(on) - min(on)
    t.nota('brilho off %.1f..%.1f (var %.2f); on %.1f..%.1f (var %.2f)' % (min(off), max(off), var_off, min(on), max(on), var_on))
    assert min(on) > 2, 'a viewport não mostrou a lâmpada acesa'
    assert var_off < 1.0, 'desligado o brilho não devia variar'
    assert var_on > max(3 * var_off, 2.0), 'ligado o brilho devia oscilar'
