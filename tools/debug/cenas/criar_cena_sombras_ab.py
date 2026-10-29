"""Cena estatica para A/B visual do envio de sombras do Principled (GPU_material_bind_shadow_lamps):
Sun com cascatas (csm) ou Sun simples com vidros de sombra colorida (colored), mais Spot e dois Point
com sombra espalhados (cada objeto recebe um conjunto diferente de luzes nos 4 slots), materiais por
nos de cores diferentes e cubos com material classico. Sem fog/SSGI, camera fixa.
Espera os shaders compilarem, salva a tela em RANGE_SHOT_PATH e fecha.

    AnastacioEngine.exe -b --factory-startup --python criar_cena_sombras_ab.py -- saida.range csm|colored
"""
import bpy
import os
import sys
from mathutils import Vector

args = sys.argv[sys.argv.index('--') + 1:]
destination = os.path.abspath(args[0])
mode = args[1] if len(args) > 1 else 'csm'

scene = bpy.context.scene
for ob in list(scene.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.use_shading_nodes = True
scene.game_settings.resolution_x = 1280
scene.game_settings.resolution_y = 720
world = bpy.data.worlds.new('World')
world.horizon_color = (0.05, 0.05, 0.07)
world.ambient_color = (0.05, 0.05, 0.06)
world.mist_settings.use_mist = False
scene.world = world


def node_material(name, rgba, glass=False):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    tree = mat.node_tree
    for node in list(tree.nodes):
        tree.nodes.remove(node)
    shader = tree.nodes.new('ShaderNodeBsdfPrincipled')
    shader.inputs['Base Color'].default_value = rgba
    shader.inputs['Roughness'].default_value = 0.4
    out = tree.nodes.new('ShaderNodeOutputMaterial')
    if glass:
        transparent = tree.nodes.new('ShaderNodeBsdfTransparent')
        mix = tree.nodes.new('ShaderNodeMixShader')
        mix.inputs['Fac'].default_value = 0.45
        tree.links.new(shader.outputs[0], mix.inputs[1])
        tree.links.new(transparent.outputs[0], mix.inputs[2])
        tree.links.new(mix.outputs[0], out.inputs['Surface'])
        mat.use_transparency = True
        mat.alpha = 0.5
        mat.game_settings.alpha_blend = 'ALPHA'
        mat.game_settings.use_backface_culling = False
        mat.use_cast_shadows = True
        mat.use_colored_shadows = True
        mat.colored_shadow_glow = 1.5
    else:
        tree.links.new(shader.outputs[0], out.inputs['Surface'])
    return mat


def legacy_material(name, rgb):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = rgb
    return mat


def box(name, loc, scale, mat):
    bpy.ops.mesh.primitive_cube_add(radius=1, location=loc)
    ob = scene.objects.active
    ob.name = name
    ob.scale = scale
    ob.data.materials.append(mat)
    ob.game.physics_type = 'STATIC'
    return ob


box('Floor', (0, 0, -0.05), (16, 16, 0.05), node_material('Floor', (0.7, 0.7, 0.7, 1)))
box('BackWall', (0, 9, 3), (16, 0.1, 3), node_material('Wall', (0.55, 0.6, 0.7, 1)))
# Grade de pilares: cores diferentes (um material cada) e, a cada 4, material classico.
for i in range(30):
    x, y = (i % 6) * 4.0 - 10.0, (i // 6) * 3.0 - 6.0
    if i % 4 == 3:
        mat = legacy_material('Legacy%02d' % i, ((i * 0.37) % 1.0, 0.5, (i * 0.61) % 1.0))
    else:
        mat = node_material('Node%02d' % i, ((i * 0.37) % 1.0, (i * 0.61) % 1.0, (i * 0.83) % 1.0, 1))
    box('Pillar%02d' % i, (x, y, 1.2), (0.45, 0.45, 1.2), mat)
if mode == 'colored':
    for i, rgba in enumerate(((1.0, 0.05, 0.02, 1), (0.05, 1.0, 0.1, 1), (0.05, 0.2, 1.0, 1))):
        box('Glass%d' % i, (-4 + i * 4, -9, 1.6), (1.2, 0.04, 1.4), node_material('Glass%d' % i, rgba, glass=True))


def lamp(name, kind, loc, target, energy, **kw):
    la = bpy.data.lamps.new(name, kind)
    la.energy = energy
    la.use_shadow = True
    la.shadow_buffer_size = 1024
    for k, v in kw.items():
        setattr(la, k, v)
    ob = bpy.data.objects.new(name, la)
    ob.location = loc
    scene.objects.link(ob)
    ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    return la


lamp('Sun', 'SUN', (9, -12, 12), (0, 0, 0), 1.0, use_csm_shadow=(mode == 'csm'), shadow_frustum_size=30)
lamp('Spot', 'SPOT', (-12, -4, 9), (-6, 0, 0), 2.0, spot_size=1.2, distance=40)
lamp('PointA', 'POINT', (6, 4, 4), (6, 4, 0), 1.5, distance=12)
lamp('PointB', 'POINT', (-6, 6, 4), (-6, 6, 0), 1.5, distance=12)

cam = bpy.data.objects.new('Camera', bpy.data.cameras.new('Camera'))
scene.objects.link(cam)
cam.location = (0, -24, 14)
cam.rotation_euler = (Vector((0, 1, 0)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
cam.data.lens = 22
scene.camera = cam

text = bpy.data.texts.new('shot.py')
text.write('''import Range, os
g = Range.logic.globalDict
now = Range.logic.getClockTime()
st = g.setdefault("_shot", {"prev": now, "stable": 0, "n": 0, "at": None})
d = (now - st["prev"]) * 1000.0
st["prev"] = now
st["n"] += 1
if st["at"] is None:
    st["stable"] = st["stable"] + 1 if d <= 120.0 else 0
    if st["stable"] >= 60:
        st["at"] = st["n"]
        Range.render.makeScreenshot(os.environ["RANGE_SHOT_PATH"])
elif st["n"] >= st["at"] + 20:
    Range.logic.endGame()
''')
scene.objects.active = cam
bpy.ops.logic.sensor_add(type='ALWAYS', name='Shot', object=cam.name)
bpy.ops.logic.controller_add(type='PYTHON', name='Shot', object=cam.name)
cam.game.sensors['Shot'].use_pulse_true_level = True
cam.game.controllers['Shot'].text = text
cam.game.sensors['Shot'].link(cam.game.controllers['Shot'])

bpy.ops.wm.save_as_mainfile(filepath=destination, check_existing=False)
print('SOMBRAS_AB salvo:', destination, mode)
