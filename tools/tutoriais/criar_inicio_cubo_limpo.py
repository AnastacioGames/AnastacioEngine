"""Cena inicial com o cubo padrão sem lógica (tutoriais que dão lógica ao cubo).

    AnastacioEngine.exe -b --factory-startup --python tools/tutoriais/criar_inicio_cubo_limpo.py -- saida.range [opções]

O cubo da cena padrão já anda com WASD (componente JogadorCelular): aqui ele sai sem componentes, ativo e
selecionado, e a 3D View olha pela câmera para o P mostrar o jogo como ele vai ficar.

Opções (para o tutorial não começar com o passo já feito):
  --sem-chao        apaga o Plane (o tutorial cria o chão)
  --estatico        o cubo sai Static (o tutorial liga o Rigid Body)
  --sem-textura     o material do cubo sai só com cor (o Palette Atlas pula material com textura)
  --baixo=TIPO      editor da área de baixo (ex.: TIMELINE, quando o tutorial pede para trocar)
  --aba=CONTEXTO    aba do Properties (ex.: OBJECT, quando o tutorial pede outra aba)
  --vista-livre     a 3D View não olha pela câmera
  --sem-selecao     nada selecionado (o primeiro passo pede para clicar no cubo)
"""
import sys

import bpy

args = sys.argv[sys.argv.index("--") + 1:]
saida = args[0]
opcoes = {a.split("=")[0]: (a.split("=", 1)[1] if "=" in a else True) for a in args[1:]}

cena = bpy.context.scene
cubo = bpy.data.objects["Cube"]
if opcoes.get("--sem-chao") and "Plane" in bpy.data.objects:
    bpy.data.objects.remove(bpy.data.objects["Plane"], do_unlink=True)
for ob in cena.objects:
    ob.select = ob is cubo and not opcoes.get("--sem-selecao")
cena.objects.active = cubo  # o componente sai pelo operador, que age no ativo
while len(cubo.game.components):
    bpy.ops.logic.python_component_remove(index=0)
texto = bpy.data.texts.get("03_jogador_celular.py")
if texto is not None:
    bpy.data.texts.remove(texto)
if opcoes.get("--estatico"):
    cubo.game.physics_type = 'STATIC'
if opcoes.get("--sem-textura"):
    for mat in cubo.data.materials:
        for i in range(len(mat.texture_slots)):
            mat.texture_slots.clear(i)
for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D' and not opcoes.get("--vista-livre"):
        area.spaces.active.region_3d.view_perspective = 'CAMERA'
    if area.type == 'PROPERTIES' and opcoes.get("--aba"):
        area.spaces.active.context = opcoes["--aba"]
if opcoes.get("--baixo"):
    min(bpy.context.screen.areas, key=lambda a: (a.y, a.x)).type = opcoes["--baixo"]
if opcoes.get("--sem-selecao"):
    cubo.select = False
    cena.objects.active = None
bpy.ops.wm.save_as_mainfile(filepath=saida)
