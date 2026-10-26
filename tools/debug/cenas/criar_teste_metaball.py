"""Metaball vira malha estática no Play.

Família Mball (pai) + Mball.001 (filha) fundidas, com material vermelho e colisão Triangle Mesh;
um cubo dinâmico cai em cima. O script do jogo grava em METABALL_OUT: polígonos da malha do pai,
malhas da filha e a altura do cubo (deve parar em cima da bola, não atravessar).

    AnastacioEngine -b --python tools/debug/cenas/criar_teste_metaball.py -- PASTA
    set METABALL_OUT=PASTA\\res.txt && AnastacioRuntime --server PASTA/metaball.range   (sem janela)
    AnastacioRuntime PASTA/metaball.range                                               (visual)
"""
import bpy, sys, os
from mathutils import Vector

out = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = 'BLENDER_GAME'

mat = bpy.data.materials.new("Red")
mat.diffuse_color = (0.8, 0.1, 0.1)

bpy.ops.object.metaball_add(type='BALL', radius=2, location=(0, 0, 0))
mb = bpy.context.object
mb.name = "Mball"
mb.data.materials.append(mat)
mb.game.physics_type = 'STATIC'
mb.game.use_collision_bounds = True
mb.game.collision_bounds_type = 'TRIANGLE_MESH'
bpy.ops.object.metaball_add(type='BALL', radius=1.5, location=(2, 0, 0))
bpy.context.object.name = "Mball.001"

bpy.ops.mesh.primitive_cube_add(location=(0, 0, 6), radius=0.3)
cube = bpy.context.object
cube.name = "Box"
cube.game.physics_type = 'RIGID_BODY'

la = bpy.data.objects.new("Sun", bpy.data.lamps.new("Sun", 'SUN'))
sc.objects.link(la)
la.rotation_euler = (0.6, 0.2, 0.3)
cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
sc.objects.link(cam)
cam.location = (3, -10, 4)
cam.rotation_euler = (Vector((1, 0, 0.5)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
sc.camera = cam

t = bpy.data.texts.new("checa.py")
t.write('''import Range, os
own = Range.logic.getCurrentController().owner
own["f"] = own.get("f", 0) + 1
out = os.environ.get("METABALL_OUT")
if out and own["f"] == 1:
    open(out + ".hb", "w").write("started")
if out and own["f"] == 90:
  try:
    sc = Range.logic.getCurrentScene()
    o = sc.objects
    polys = sum(m.numPolygons for m in o["Mball"].meshes)
    mat = o["Mball"].meshes[0].materials[0].name if o["Mball"].meshes else ""
    with open(out, "w") as f:
        f.write("polys=%d child_meshes=%d mat=%s box_z=%.2f\\n" % (
            polys, len(o["Mball.001"].meshes), mat, o["Box"].worldPosition.z))
  except Exception:
    import traceback
    open(out, "w").write(traceback.format_exc())
  Range.logic.endGame()
''')
sc.objects.active = cam
bpy.ops.logic.sensor_add(type='ALWAYS', name="A", object=cam.name)
s = cam.game.sensors["A"]
s.use_pulse_true_level = True
bpy.ops.logic.controller_add(type='PYTHON', name="P", object=cam.name)
c = cam.game.controllers["P"]
c.text = t
s.link(c)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, "metaball.range"), check_existing=False)
