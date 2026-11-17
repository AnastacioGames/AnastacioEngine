"""Cena de teste do Impostor de Caixa (docs/plano-imposter-caixa.md, Etapa 2: bake).

Suzanne suave, girada 30 graus em Z, escala (1, 1, 1.5) e dois materiais (vermelho e azul por face,
pelo lado X), para pegar erro de eixo, de escala e de espelhamento nas 6 vistas.

Uso (editor aberto, ex. por tools/testes_engine/controle.py py):
    exec(open(r"D:/AnastacioEngine/tools/debug/cenas/criar_cena_box_impostor.py").read())
    ob = montar()
    bpy.ops.object.bake_box_impostor(resolution='128')
"""
import bpy
from math import radians


def montar():
    scene = bpy.context.scene
    for ob in list(scene.objects):
        bpy.data.objects.remove(ob, do_unlink=True)

    bpy.ops.mesh.primitive_monkey_add(location=(2.0, 1.0, 1.0), rotation=(0, 0, radians(30)))
    ob = bpy.context.object
    ob.name = "Macaco"
    ob.scale = (1.0, 1.0, 1.5)
    bpy.ops.object.shade_smooth()
    mod = ob.modifiers.new("Sub", 'SUBSURF')
    mod.levels = 1

    vermelho = bpy.data.materials.new("Vermelho")
    vermelho.diffuse_color = (0.8, 0.1, 0.1)
    azul = bpy.data.materials.new("Azul")
    azul.diffuse_color = (0.1, 0.2, 0.8)
    ob.data.materials.append(vermelho)
    ob.data.materials.append(azul)
    for p in ob.data.polygons:
        p.material_index = 1 if p.center.x > 0.0 else 0

    bpy.ops.object.lamp_add(type='SUN', location=(0, 0, 5))
    scene.objects.active = ob
    ob.select = True
    return ob
