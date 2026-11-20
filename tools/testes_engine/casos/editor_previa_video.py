"""Prévia na 3D View, Fase 6 (docs/plano-previa-viewport.md): Video Player (quadro de pôster). Plano com o
componente VideoPlayer e uma textura de imagem: com Scene.range_video_poster_preview ligado a textura passa a
mostrar o filme (primeiro quadro); desligar devolve a imagem original; salvar desliga o toggle e nunca grava o
vídeo no lugar da textura."""
import os, shutil
from rodar import py

CENA = '''
import os
sc = bpy.context.scene
sc.render.engine = 'BLENDER_GAME'
for ob in list(sc.objects):
    sc.objects.unlink(ob)
bpy.ops.mesh.primitive_plane_add(radius=1)
ob = sc.objects.active
img = bpy.data.images.new('Original', 16, 16)
tex = bpy.data.textures.new('Tela', 'IMAGE')
tex.image = img
mat = bpy.data.materials.new('Tela')
slot = mat.texture_slots.add()
slot.texture = tex
slot.texture_coords = 'UV'
ob.data.materials.append(mat)
bpy.ops.object.video_player_add()
comp = [c for c in ob.game.components if c.name == 'VideoPlayer'][0]
comp.properties['File'].value = '//teste.mp4'
'''

TESTE = '''
import bpy
sc = bpy.context.scene
tex = bpy.data.textures['Tela']
antes = (tex.image.name, tex.image.source)
sc.range_video_poster_preview = True
ligado = (tex.image.name, tex.image.source, 'range_video_orig' in tex)
sc.range_video_poster_preview = False
desligado = (tex.image.name, 'range_video_orig' in tex)
sc.range_video_poster_preview = True
bpy.ops.wm.save_mainfile()
depois_de_salvar = (tex.image.name, sc.range_video_poster_preview)
resultado = [list(antes), list(ligado), list(desligado), list(depois_de_salvar)]
'''


def testar(t):
    cena = t.gerar(CENA)
    shutil.copy(os.path.join(os.path.dirname(__file__), '..', '..', 'debug', 'cenas', 'video_player', 'teste.mp4'),
                str(t.pasta / 'teste.mp4'))
    e = t.editor(cena)
    antes, ligado, desligado, salvo = py(e, TESTE)
    t.nota('antes %s, ligado %s, desligado %s, salvo %s' % (antes, ligado, desligado, salvo))
    assert antes == ['Original', 'GENERATED']
    assert ligado[1] == 'MOVIE' and ligado[2], 'o toggle não trocou a textura pelo filme'
    assert desligado == ['Original', False], 'desligar não devolveu a imagem original'
    assert salvo == ['Original', False], 'salvar deixou o vídeo na textura ou o toggle ligado'
