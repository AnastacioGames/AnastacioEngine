"""Teste da etapa 1 do personagem automatico: frente, escala e de pe.

    AnastacioEngine.exe -b <GroupFabio.range> --python tools/debug/teste_autorig_alinhar.py

Importa o Menino do Fuse em 6 posicoes erradas e confere se align_to_base acerta todas.
"""
import bpy, math
from mathutils import Matrix
import range_character_autorig as ar
OBJ=r"D:/ProjetoRolimaRacer/personagens/2 - File Exported from Fuse in (.obj)/Menino_2/Menino.obj"
arm=bpy.data.objects["Armature"]
casos={"como_vem":None,"de_costas":Matrix.Rotation(math.pi,4,'Z'),"de_lado":Matrix.Rotation(math.pi/2,4,'Z'),
       "deitado":Matrix.Rotation(-math.pi/2,4,'X'),"deitado_outro_lado":Matrix.Rotation(math.pi/2,4,'X'),"de_cabeca_para_baixo":Matrix.Rotation(math.pi,4,'X')}
ok=True
for nome,m in casos.items():
    antes=set(bpy.data.objects)
    bpy.ops.import_scene.obj(filepath=OBJ)
    objs=[o for o in bpy.data.objects if o not in antes and o.type=='MESH']
    if m:
        for o in objs: o.matrix_world=m*o.matrix_world
    bpy.context.scene.update()
    r=ar.align_to_base(objs,arm)
    f,_=ar.mesh_front(objs)
    passou = f==ar.armature_front(arm) and 1.5<r["altura"]<1.8 and ar._widest_slice(ar.world_verts(objs))>0.5
    ok&=passou
    print("ALINHAR",nome,"OK" if passou else "FALHOU",r)
    for o in objs: bpy.data.objects.remove(o,do_unlink=True)
print("ALINHAR", "PASS" if ok else "FAIL")
