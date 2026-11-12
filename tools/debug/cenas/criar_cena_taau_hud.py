"""Cena de teste do TAAU com HUD por cima (overlay scene): texto e uma moldura de linhas finas.

    AnastacioEngine -b <taau.range> --python tools/debug/cenas/criar_cena_taau_hud.py -- saida.range

Parte da cena de tools/debug/cenas/criar_cena_taa_movimento.py e acrescenta a cena "HUD" (câmera
ortográfica, texto branco e moldura fina), aberta como overlay pelo script do carro no 1º quadro.
Com o TAAU o HUD deve sair igual ao da resolução cheia (desenhado no tamanho da janela).
Medição: tools/debug/medir_taau.py <saida.range> --hud.
"""

import sys

import bpy

out = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "taau_hud.range"
main = bpy.context.scene

hud = bpy.data.scenes.new("HUD")
hud.render.engine = 'BLENDER_GAME'
cam = bpy.data.objects.new("HudCam", bpy.data.cameras.new("HudCam"))
cam.data.type = 'ORTHO'
cam.data.ortho_scale = 10.0
cam.location = (0.0, 0.0, 10.0)
hud.objects.link(cam)
hud.camera = cam

branco = bpy.data.materials.new("HudBranco")
branco.diffuse_color = (1.0, 1.0, 0.0)
branco.use_shadeless = True

txt = bpy.data.curves.new("HudTexto", 'FONT')
txt.body = "TAAU HUD 0123456789"
txt.size = 0.45
ob = bpy.data.objects.new("HudTexto", txt)
ob.location = (-4.6, 2.2, 0.0)
ob.data.materials.append(branco)
hud.objects.link(ob)

# Moldura: quatro barras bem finas (≈ 1 px a 960 px de largura: 10 m / 960 px ≈ 0,0104 m).
me = bpy.data.meshes.new("HudMoldura")
verts, faces = [], []
for (x0, y0, x1, y1) in ((-4.0, -1.0, 4.0, -0.99), (-4.0, 1.0, 4.0, 1.01),
                         (-4.0, -1.0, -3.99, 1.01), (3.99, -1.0, 4.0, 1.01)):
    n = len(verts)
    verts += [(x0, y0, 0), (x1, y0, 0), (x1, y1, 0), (x0, y1, 0)]
    faces.append((n, n + 1, n + 2, n + 3))
me.from_pydata(verts, [], faces)
me.materials.append(branco)
moldura = bpy.data.objects.new("HudMoldura", me)
hud.objects.link(moldura)

# O carro abre o HUD por cima no primeiro quadro.
texto = bpy.data.texts["andar.py"]
texto.clear()
texto.write(
    "from Range import logic\n"
    "own = logic.getCurrentController().owner\n"
    "if 'hud' not in own:\n"
    "    own['hud'] = True\n"
    "    logic.addScene('HUD', 1)\n"
    "if own['andar']:\n"
    "    own.worldPosition.x += own['vel']\n"
)
bpy.context.screen.scene = main
bpy.ops.wm.save_as_mainfile(filepath=out)
print("CENA", out)
