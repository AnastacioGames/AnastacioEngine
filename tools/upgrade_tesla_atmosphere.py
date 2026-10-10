"""Add native accumulating camera shake and a packed background to TeslaPiano_PBR.

Run in RangeEngine -b <scene.range> --python <this script> -- <background.png>.
Writes TeslaPiano_Cinematic.range beside the input without replacing it.
"""
import bpy
import math
import os
import sys
from mathutils import Vector

args = sys.argv[sys.argv.index('--') + 1:]
source = bpy.data.filepath
scene = bpy.context.scene
cam = scene.camera
if not cam:
    raise RuntimeError('Scene has no active camera')
fx = cam.data.game_fx
fx.shake_amplitude = 0.012
fx.shake_frequency = 14.0
fx.shake_decay = 0.85
fx.use_shake_roll = False

text = bpy.data.texts.get('piano_tesla.py')
if not text:
    raise RuntimeError('piano_tesla.py not found')
script = text.as_string()
if '# ANASTACIO_MUSICAL_SHAKE' not in script:
    note_trigger = '        device.play(som)'
    chord_trigger = '    device.play(som_trovao)'
    if script.count(note_trigger) != 1 or script.count(chord_trigger) != 1:
        raise RuntimeError('Unexpected piano script; refusing ambiguous replacements')
    script = script.replace(note_trigger, note_trigger + '''
        # ANASTACIO_MUSICAL_SHAKE: native trauma accumulates and decays in seconds.
        logic.getCurrentScene().active_camera.shake(0.18)''')
    script = script.replace(chord_trigger, chord_trigger + '''
    logic.getCurrentScene().active_camera.shake(0.85)''')
    compile(script, 'piano_tesla.py', 'exec')
    text.from_string(script)

image = bpy.data.images.load(os.path.abspath(args[0]), check_existing=True)
image.name = 'Anastacio_Tesla_Paisagem_Noturna'
image.pack(as_png=True)
image.filepath = '//textures/tesla_background.png'
mat = bpy.data.materials.new('Anastacio_Fundo_Industrial')
mat.use_nodes = True
mat.use_shadeless = False
mat.use_cast_shadows = False
mat.game_settings.use_backface_culling = False
tree = mat.node_tree
tree.nodes.clear()
tex = tree.nodes.new('ShaderNodeTexImage')
tex.image = image
tex.label = 'Paisagem noturna (imagem empacotada)'
tex.location = (-300, 0)
em = tree.nodes.new('ShaderNodeEmission')
em.inputs['Strength'].default_value = 0.7
em.location = (0, 0)
out = tree.nodes.new('ShaderNodeOutputMaterial')
out.location = (230, 0)
tree.links.new(tex.outputs['Color'], em.inputs['Color'])
tree.links.new(em.outputs[0], out.inputs['Surface'])

distance = 100.0
width = 2 * distance * math.tan(cam.data.angle_x / 2) * 1.12
height = width * image.size[1] / image.size[0]
bpy.ops.mesh.primitive_plane_add(radius=1)
backdrop = bpy.context.object
backdrop.name = 'Anastacio_Fundo_Industrial'
backdrop.location = cam.matrix_world * Vector((0, 0, -distance))
backdrop.rotation_euler = cam.rotation_euler.copy()
backdrop.scale = (width / 2, height / 2, 1)
backdrop.data.materials.append(mat)
if not backdrop.data.uv_layers.active:
    backdrop.data.uv_textures.new(name='Anastacio_Background_UV')
uv = backdrop.data.uv_layers.active
for poly in backdrop.data.polygons:
    for li in poly.loop_indices:
        co = backdrop.data.vertices[backdrop.data.loops[li].vertex_index].co
        uv.data[li].uv = ((co.x + 1) * 0.5, (co.y + 1) * 0.5)
uv_node = tree.nodes.new('ShaderNodeUVMap')
uv_node.uv_map = uv.name
uv_node.location = (-550, 0)
tree.links.new(uv_node.outputs['UV'], tex.inputs['Vector'])
backdrop.game.physics_type = 'NO_COLLISION'
cam.data.clip_end = max(cam.data.clip_end, 250)
notes = bpy.data.texts.get('LEIA-ME')
if notes:
    notes.write('\nVisual cinematico: Camera > Camera Shake controla amplitude, frequencia e decay.\n'
                'Nota soma trauma 0.18; ESPACO soma 0.85; Camera.shake reduz suavemente com o tempo.\n'
                'Fundo: plano Anastacio_Fundo_Industrial com imagem empacotada.\n')
output = os.path.join(os.path.dirname(source), 'TeslaPiano_Cinematic.range')
bpy.ops.wm.save_as_mainfile(filepath=output)
print('TESLA_CINEMATIC_SAVED', output, flush=True)
