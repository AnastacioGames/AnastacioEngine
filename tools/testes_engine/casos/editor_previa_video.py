"""Prévia na 3D View, Fase 6: Video Player (Game Preview > Video Player). Mostra o 1º quadro do vídeo no
material do objeto ("On Material") e em tela cheia dentro do quadro da câmera; desligado, nada aparece."""
import os
import subprocess
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rodar import py
from editor_previa_impostor import recorte
from editor_previa_particulas import PREPARAR, medir

CENA = '''
import math
sc = bpy.context.scene
for ob in list(sc.objects):
    if ob.type != 'CAMERA':
        sc.objects.unlink(ob)
w = bpy.data.worlds.new('W'); w.horizon_color = (0, 0, 0); sc.world = w
cam = [o for o in sc.objects if o.type == 'CAMERA'][0]
sc.camera = cam
cam.location = (0, -6, 0); cam.rotation_euler = (math.pi / 2, 0, 0)
bpy.ops.mesh.primitive_plane_add(radius=1.5, location=(0, 0, 0))
pl = bpy.context.scene.objects.active
pl.rotation_euler = (math.pi / 2, 0, 0)
pl.data.uv_textures.new()
mt = bpy.data.materials.new('Tela'); mt.use_shadeless = True; mt.diffuse_color = (0, 0, 0)
pl.data.materials.append(mt)
bpy.ops.object.video_player_add()
p = pl.game.components[0].properties
p['File'].value = r'VIDEO'
FULL
'''

LIGAR = '''
import bpy
bpy.context.scene.range_video_preview = LIGADO
bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=3)
resultado = 1
'''


def caso(t, nome, extra):
    cena = t.gerar(CENA.replace('VIDEO', str(t.pasta / 'v.mp4')).replace('FULL', extra), nome=nome)
    e = t.editor(cena)
    caixa = py(e, PREPARAR.replace('LIGADO', 'False'))
    py(e, LIGAR.replace('LIGADO', 'False'))
    off = medir(recorte(e, str(t.pasta / (nome + '_off.png')), caixa))[0]
    py(e, LIGAR.replace('LIGADO', 'True'))
    on = medir(recorte(e, str(t.pasta / (nome + '_on.png')), caixa))[0]
    t.nota('%s: desligado %.3f, ligado %.3f' % (nome, off, on))
    return off, on


def testar(t):
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'lavfi', '-i', 'testsrc2=size=320x180:rate=10:duration=1',
                    '-pix_fmt', 'yuv420p', str(t.pasta / 'v.mp4')], check=True)
    off, on = caso(t, 'material', "p['Material'].value = 'Tela'")
    assert on > off + 0.1, 'o vídeo não apareceu no material'
    off, on = caso(t, 'tela_cheia', "p['Fullscreen'].value = True")
    assert on > off + 0.2, 'o vídeo não apareceu em tela cheia'
