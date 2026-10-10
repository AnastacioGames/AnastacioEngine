"""Repair backdrop UV mapping and soften musical camera shake in-place."""
import bpy
import os
import shutil

scene = bpy.context.scene
ob = scene.objects['Anastacio_Fundo_Industrial']
mesh = ob.data
if not mesh.uv_layers.active:
    mesh.uv_textures.new(name='Anastacio_Background_UV')
uv = mesh.uv_layers.active
for poly in mesh.polygons:
    for loop_index in poly.loop_indices:
        co = mesh.vertices[mesh.loops[loop_index].vertex_index].co
        uv.data[loop_index].uv = ((co.x + 1) * 0.5, (co.y + 1) * 0.5)
mat = ob.active_material
tree = mat.node_tree
image_node = next(n for n in tree.nodes if n.bl_idname == 'ShaderNodeTexImage')
uv_node = next((n for n in tree.nodes if n.bl_idname == 'ShaderNodeUVMap'), None)
if uv_node is None:
    uv_node = tree.nodes.new('ShaderNodeUVMap')
uv_node.uv_map = uv.name
uv_node.label = 'UV explicito do fundo (Game PBR)'
uv_node.location = (-550, 0)
tree.links.new(uv_node.outputs['UV'], image_node.inputs['Vector'])
image_node.extension = 'EXTEND'
mat.use_shadeless = False  # PBR uses the connected Emission shader.
mat.emit = 1.0
# Conventional texture slot supplies a fallback for the legacy Game renderer.
tex = bpy.data.textures.get('Anastacio_Fundo_Image_Legacy')
if tex is None:
    tex = bpy.data.textures.new('Anastacio_Fundo_Image_Legacy', type='IMAGE')
tex.image = image_node.image
slot = next((s for s in mat.texture_slots if s and s.texture == tex), None)
if slot is None:
    slot = mat.texture_slots.add()
slot.texture = tex
slot.texture_coords = 'UV'
slot.uv_layer = uv.name
slot.use_map_color_diffuse = True
mat.diffuse_color = (1, 1, 1)
scene.game_settings.use_shading_nodes = True
fx = scene.camera.data.game_fx
fx.shake_amplitude = 0.012
fx.shake_frequency = 14
fx.shake_decay = 0.85
fx.use_shake_roll = False
text = bpy.data.texts['piano_tesla.py']
script = text.as_string().replace('active_camera.shake(0.24)', 'active_camera.shake(0.18)')
script = script.replace('active_camera.shake(1.0)', 'active_camera.shake(0.85)')
script = script.replace('camera.speedBlurMaxSpeed * 0.75', 'camera.speedBlurMaxSpeed * 0.35')
compile(script, text.name, 'exec')
text.from_string(script)
source = bpy.data.filepath
backup = os.path.splitext(source)[0] + '_before_background_fix.range'
if not os.path.exists(backup):
    shutil.copy2(source, backup)
bpy.ops.wm.save_as_mainfile(filepath=source)
print('TESLA_FIX_SAVED', source, 'UV', len(uv.data), 'amplitude', fx.shake_amplitude, flush=True)
