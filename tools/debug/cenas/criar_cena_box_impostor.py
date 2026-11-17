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


def montar_caixa():
    """Caixote retangular (etapa 3b, modo Box): 2 x 1 x 0.6 m, girado 30 graus em Z, uma cor por face
    e uma faixa escura em cada face (pega troca de face, espelho e esticamento)."""
    scene = bpy.context.scene
    for ob in list(scene.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    bpy.ops.mesh.primitive_cube_add(location=(2.0, 1.0, 1.0), rotation=(0, 0, radians(30)))
    ob = bpy.context.object
    ob.name = "Caixa"
    ob.scale = (1.0, 0.5, 0.3)
    cores = ((0.8, 0.1, 0.1), (0.1, 0.6, 0.1), (0.1, 0.2, 0.8), (0.8, 0.7, 0.1), (0.7, 0.1, 0.7),
             (0.1, 0.7, 0.7), (0.05, 0.05, 0.05))
    for i, c in enumerate(cores):
        m = bpy.data.materials.new("Cor%d" % i)
        m.diffuse_color = c
        ob.data.materials.append(m)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.subdivide(number_cuts=3)
    bpy.ops.object.mode_set(mode='OBJECT')
    for p in ob.data.polygons:
        n = p.normal
        k = [abs(n.x), abs(n.y), abs(n.z)].index(max(abs(n.x), abs(n.y), abs(n.z)))
        face = k * 2 + (0 if n[k] > 0 else 1)
        # faixa escura: segunda fileira na direção "u" da face, deslocada para um lado
        c = p.center
        coord = c.y if k == 0 else c.x
        p.material_index = 6 if -0.6 < coord < -0.2 else face
    bpy.ops.object.lamp_add(type='SUN', location=(0, 0, 5))
    scene.objects.active = ob
    ob.select = True
    return ob
