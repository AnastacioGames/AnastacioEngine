"""Compara cabeça real x Impostor de Caixa no editor invisível (viewport GLSL), em 3 poses da cabeça."""
import json
import sys
sys.path.insert(0, r"d:/AnastacioEngine/tools/testes_engine")
import controle

PASTA = r"D:/ProjetoRolimaRacer/personagens/6 - Personagem v2/Enzo"
CENA = PASTA + "/08_impostor.range"

SETUP = r'''
import bpy, math
from mathutils import Vector, Euler
sc = bpy.context.scene
sc.layers = [i in (0, 1) for i in range(20)]   # sem a camada 20 (cartão solto do bake)
for o in sc.objects:
    o.layers = [i in (0, 1) for i in range(20)] if o.name != "Cabeca_box_impostor" else o.layers
if "_cmp_sun" not in bpy.data.objects:
    l = bpy.data.lamps.new("_cmp_sun", 'SUN'); l.energy = 1.0
    s = bpy.data.objects.new("_cmp_sun", l); sc.objects.link(s)
    s.rotation_euler = (Vector((0, 0, 0)) - Vector((0.6, 1.0, 1.2))).to_track_quat('-Z', 'Y').to_euler()
    s.layers = [i == 0 for i in range(20)]
    h = bpy.data.lamps.new("_cmp_hemi", 'HEMI'); h.energy = 0.4
    ho = bpy.data.objects.new("_cmp_hemi", h); sc.objects.link(ho); ho.layers = [i == 0 for i in range(20)]
    cd = bpy.data.cameras.new("_cmp_cam"); cd.lens = 50
    cam = bpy.data.objects.new("_cmp_cam", cd); sc.objects.link(cam); cam.layers = [i == 0 for i in range(20)]
    sc.camera = cam
ctx = contexto('VIEW_3D')
sp = ctx['area'].spaces.active
sp.viewport_shade = 'MATERIAL'
sp.region_3d.view_perspective = 'CAMERA'
sp.show_only_render = True
sc.render.resolution_x = sc.render.resolution_y = 600
sc.render.resolution_percentage = 100
sc.render.alpha_mode = 'SKY'
resultado = [o.name for o in sc.objects]
'''

SHOT = r'''
import bpy
from mathutils import Vector, Euler
sc = bpy.context.scene
arm = next(o for o in sc.objects if o.type == 'ARMATURE')
head = bpy.data.objects["Cabeca"]
card = bpy.data.objects["Cabeca_box_impostor"]
real_me = bpy.data.meshes[head.data.name] if head.get("_real") is None else bpy.data.meshes[head["_real"]]
head["_real"] = real_me.name
pb = arm.pose.bones["mixamorig:Head"]; pb.rotation_mode = 'XYZ'
pb.rotation_euler = POSE
sc.update()
c = head.matrix_world.to_translation()
d = Vector(DIR).normalized()
cam = bpy.data.objects["_cmp_cam"]
cam.location = c + d * 0.75
cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
ctx = contexto('VIEW_3D')
for tag, me in (("real", real_me), ("impostor", card.data)):
    head.data = me
    sc.update()
    sc.render.filepath = PATH + "_" + tag + ".png"
    bpy.ops.render.opengl(ctx, write_still=True, view_context=True)
head.data = real_me
resultado = sc.render.filepath
'''

POSES = (
    ("repouso", (0.0, 0.0, 0.0), (0.0, 1.0, 0.05)),
    ("virada40", (0.0, 0.0, 0.7), (0.0, 1.0, 0.05)),
    ("lado_baixo", (0.35, 0.0, -0.9), (1.0, 0.6, 0.35)),
)

controle.abrir(CENA)
ed = controle.Editor()
try:
    r = ed.pedir('py', codigo=SETUP)
    if not r.get('ok', True) and 'resultado' not in r:
        print(r)
    r = ed.pedir('py', codigo=SETUP)   # 2ª vez: contexto('VIEW_3D') pode ter trocado a área no 1º
    print("SETUP", str(r)[:300])
    for name, pose, d in POSES:
        code = SHOT.replace("POSE", repr(pose)).replace("DIR", repr(d)).replace(
            "PATH", repr(PASTA + "/08_cmp_" + name))
        r = ed.pedir('py', codigo=code)
        print("SHOT", name, str(r)[:300])
finally:
    try:
        ed.pedir('fechar')
    except Exception:
        pass
