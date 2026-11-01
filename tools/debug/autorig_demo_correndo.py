"""Personagem automatico: cena de comparacao com o rig do Mixamo.

    AnastacioEngine.exe -b --factory-startup --python tools/debug/autorig_demo_correndo.py -- <saida.range>

Gabarito (Enzo rigado no Mixamo), Enzo e Patty feitos pela ferramenta, todos com a animacao Running.
"""
import sys
SAIDA = sys.argv[sys.argv.index("--") + 1]
import bpy, glob
from mathutils import Vector
import range_character_autorig as ar
P=r"D:/ProjetoRolimaRacer/personagens/"
bpy.ops.wm.read_factory_settings(use_empty=True)
sc=bpy.context.scene
def novos(): return set(sc.objects)
# animacao
a=novos(); bpy.ops.import_scene.fbx(filepath=P+"Animacao - Mixano/Running.fbx")
anim=[o for o in sc.objects if o not in a]
acao=next(o for o in anim if o.type=='ARMATURE').animation_data.action
acao.use_fake_user=True; acao.name="Running"
fim=int(acao.frame_range[1])
for o in anim: bpy.data.objects.remove(o,do_unlink=True)
# acao para rig com transformacoes aplicadas (escala 0.01): localizacao em metros
ac=acao.copy(); ac.name="Running_m"
for fc in ac.fcurves:
    if fc.data_path.endswith("location"):
        for k in fc.keyframe_points:
            k.co.y*=0.01; k.handle_left.y*=0.01; k.handle_right.y*=0.01
# 1) gabarito Mixamo
a=novos(); bpy.ops.import_scene.fbx(filepath=P+"3 - Blender Import(.obj) Export(.fbx) to Mixano/_novos/Enzo_dois_dedos.fbx")
g=[o for o in sc.objects if o not in a]; garm=next(o for o in g if o.type=='ARMATURE')
garm.name="Gabarito_Mixamo"; garm.location.x=-1.2
garm.animation_data_create(); garm.animation_data.action=acao
# base
arm,src=ar.load_base(P+"3 - Blender Import(.obj) Export(.fbx) to Mixano/_novos/Enzo_dois_dedos.fbx")
for nome,x in (("Enzo",0.0),("Patty",1.2)):
    obj=glob.glob(P+"2 - File Exported from Fuse in (.obj)/_novos/%s/*.obj"%nome)[0]
    a=novos(); bpy.ops.import_scene.obj(filepath=obj)
    objs=[o for o in sc.objects if o not in a and o.type=='MESH']; sc.update()
    ar.align_to_base(objs,arm,report=print)
    n=ar.fit_skeleton(arm,src,objs); ar.transfer_weights(src,objs,n)
    n.name="Ferramenta_"+nome; n.location.x=x
    n.animation_data_create(); n.animation_data.action=ac
bpy.data.objects.remove(arm,do_unlink=True); bpy.data.objects.remove(src,do_unlink=True)
sc.frame_start=1; sc.frame_end=fim
cam=bpy.data.objects.new("Camera",bpy.data.cameras.new("Camera")); sc.objects.link(cam)
cam.location=(0,-6,1.1); cam.rotation_euler=(1.5708,0,0); sc.camera=cam
lamp=bpy.data.objects.new("Sol",bpy.data.lamps.new("Sol",'SUN')); sc.objects.link(lamp); lamp.rotation_euler=(0.8,0.2,0.3)
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=SAIDA)
print("DEMO ok frames",fim)
