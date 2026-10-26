"""Sombra do sol com cascatas (CSM) no material Principled.

Chão e cubo da esquerda em Principled, cubo da direita em material clássico: as duas sombras devem
aparecer iguais no chão, perto e longe (as cascatas de fora cobrem os cubos distantes ao fundo).

    AnastacioEngine -b --python tools/debug/cenas/criar_teste_csm_principled.py -- PASTA
    AnastacioRuntime --server PASTA/csm_principled.range   (sem janela: só confere se os shaders compilam)
    AnastacioRuntime PASTA/csm_principled.range            (visual)
"""
import bpy, sys, os
from mathutils import Vector

out = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = 'BLENDER_GAME'
sc.game_settings.use_shading_nodes = True


def principled(name, color):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = color
    outn = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(bsdf.outputs[0], outn.inputs[0])
    return m


def add(prim, name, loc, mat, **kw):
    getattr(bpy.ops.mesh, prim)(location=loc, **kw)
    ob = bpy.context.object
    ob.name = name
    ob.data.materials.append(mat)
    return ob


add('primitive_plane_add', "Ground", (0, 20, 0), principled("GroundPBR", (0.8, 0.8, 0.8, 1)), radius=40)
add('primitive_cube_add', "CubePBR", (-2, 0, 1), principled("CubePBR", (0.8, 0.2, 0.1, 1)))
classic = bpy.data.materials.new("CubeClassic")
classic.diffuse_color = (0.1, 0.3, 0.8)
add('primitive_cube_add', "CubeClassic", (2, 0, 1), classic)
far = principled("FarPBR", (0.2, 0.7, 0.2, 1))
for i, y in enumerate((15, 30, 50)):
    add('primitive_cube_add', "Far%d" % i, (0, y, 1.5), far, radius=1.5)

la = bpy.data.lamps.new("Sun", 'SUN')
la.use_shadow = True
la.use_csm_shadow = True
sun = bpy.data.objects.new("Sun", la)
sc.objects.link(sun)
sun.location = (0, 0, 20)
sun.rotation_euler = (0.7, 0.3, 0.4)

cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
sc.objects.link(cam)
cam.location = (0, -12, 6)
cam.rotation_euler = (Vector((0, 8, 0)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
sc.camera = cam

# Ends after a few frames when CSM_SECONDS is set (automatic check); otherwise it keeps running.
t = bpy.data.texts.new("fim.py")
t.write('''import Range, os
own = Range.logic.getCurrentController().owner
own["f"] = own.get("f", 0) + 1
if os.environ.get("CSM_FRAMES") and own["f"] >= int(os.environ["CSM_FRAMES"]):
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
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, "csm_principled.range"), check_existing=False)
