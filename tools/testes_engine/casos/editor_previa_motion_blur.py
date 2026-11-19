"""Prévia na 3D View, Fase 3 (docs/plano-previa-viewport.md): Directional Blur do jogo (Camera > Game FX)
na viewport com Game Preview > Camera Motion Blur. Os redesenhos da vista são os quadros: um render
depois de girar a câmera borra; o seguinte, sem mexer, volta nítido como o jogo com a câmera parada."""
from PIL import Image, ImageFilter, ImageStat
from rodar import py

L, A = 960, 540

CENA = '''
sc = bpy.context.scene
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = %d, %d, 100
bpy.ops.mesh.primitive_plane_add(radius=20)
for i in range(-3, 4):
    bpy.ops.mesh.primitive_cube_add(location=(i * 3, 6, 1))
g = sc.camera.data.game_fx
g.use_directional_blur, g.directional_blur_strength, g.directional_blur_max = True, 2.0, 0.2
''' % (L, A)

RENDER = '''
import bpy
sc = bpy.context.scene
sc.camera.rotation_euler.z += %f
sc.update()
for a in bpy.context.screen.areas:
    if a.type == 'VIEW_3D':
        sp = a.spaces.active
        sp.region_3d.view_perspective = 'CAMERA'
        sp.viewport_shade = 'SOLID'
        sp.show_only_render = True
        sp.fx_settings.use_camera_motion_blur = %s
        ov = dict(bpy.context.copy(), area=a, region=[r for r in a.regions if r.type == 'WINDOW'][0])
bpy.ops.render.opengl(ov, view_context=True)
bpy.data.images['Render Result'].save_render(r'%s')
resultado = 'ok'
'''


def nitidez(png):
    return ImageStat.Stat(Image.open(png).convert('L').filter(ImageFilter.FIND_EDGES)).mean[0]


def testar(t):
    cena = t.gerar(CENA)
    off_png, giro_png, parado_png = (str(t.pasta / n) for n in ('off.png', 'giro.png', 'parado.png'))

    e = t.editor(cena)
    py(e, RENDER % (0.0, 'False', off_png))
    py(e, RENDER % (0.0, 'True', str(t.pasta / 'base.png')))   # primeiro quadro: sem histórico
    py(e, RENDER % (0.05, 'True', giro_png))                    # girou: rastro
    py(e, RENDER % (0.0, 'True', parado_png))                   # parou: nítido

    off, giro, parado = nitidez(off_png), nitidez(giro_png), nitidez(parado_png)
    t.nota('nitidez: sem prévia %.2f, girando %.2f, parada %.2f' % (off, giro, parado))
    # renders renders a segundos de distância: fps_scale vai ao piso 0,25 do jogo, rastro curto
    assert giro < off * 0.9, 'o giro da câmera não borrou'
    assert abs(parado - off) < off * 0.05, 'a câmera parada continuou borrada'
