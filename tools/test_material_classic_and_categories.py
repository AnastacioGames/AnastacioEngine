"""Regression test for PBR -> Classic conversion and Material-tab filters.

Run with:
    build/bin/AnastacioEngine.exe -b --python tools/test_material_classic_and_categories.py
"""

import inspect
import os
import sys
from types import SimpleNamespace

import bpy
import bl_ui.properties_material as material_ui


bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.use_shading_nodes = True

mesh = bpy.data.meshes.new("ClassicConversionMesh")
mesh.from_pydata(((-1, -1, 0), (1, -1, 0), (1, 1, 0), (-1, 1, 0)), (), ((0, 1, 2, 3),))
mesh.update()
mesh.uv_textures.new(name="UVMain")
ob = bpy.data.objects.new("ClassicConversionObject", mesh)
scene.objects.link(ob)
scene.objects.active = ob
ob.select = True

mat = bpy.data.materials.new("PBRToClassic")
mesh.materials.append(mat)
mat.use_nodes = True
tree = mat.node_tree
tree.nodes.clear()

uv = tree.nodes.new("ShaderNodeUVMap")
uv.uv_map = "UVMain"


def image_node(name):
    image = bpy.data.images.new(name, 2, 2)
    node = tree.nodes.new("ShaderNodeTexImage")
    node.image = image
    tree.links.new(uv.outputs["UV"], node.inputs["Vector"])
    return node


color = image_node("ClassicColor")
rough = image_node("ClassicRoughness")
normal = image_node("ClassicNormal")
alpha = image_node("ClassicAlpha")
emit_color = image_node("ClassicEmission")

principled = tree.nodes.new("ShaderNodeBsdfPrincipled")
principled.inputs["Metallic"].default_value = 0.7
principled.inputs["Roughness"].default_value = 0.32
principled.inputs["Specular"].default_value = 0.65
tree.links.new(color.outputs["Color"], principled.inputs["Base Color"])
tree.links.new(rough.outputs["Color"], principled.inputs["Roughness"])

bump = tree.nodes.new("ShaderNodeBump")
bump.inputs["Strength"].default_value = 0.4
tree.links.new(normal.outputs["Color"], bump.inputs["Height"])
tree.links.new(bump.outputs["Normal"], principled.inputs["Normal"])

transparent = tree.nodes.new("ShaderNodeBsdfTransparent")
alpha_mix = tree.nodes.new("ShaderNodeMixShader")
tree.links.new(alpha.outputs["Alpha"], alpha_mix.inputs[0])
tree.links.new(transparent.outputs["BSDF"], alpha_mix.inputs[1])
tree.links.new(principled.outputs["BSDF"], alpha_mix.inputs[2])

emission = tree.nodes.new("ShaderNodeEmission")
emission.inputs["Strength"].default_value = 2.5
tree.links.new(emit_color.outputs["Color"], emission.inputs["Color"])
add = tree.nodes.new("ShaderNodeAddShader")
tree.links.new(alpha_mix.outputs["Shader"], add.inputs[0])
tree.links.new(emission.outputs["Emission"], add.inputs[1])
output = tree.nodes.new("ShaderNodeOutputMaterial")
tree.links.new(add.outputs["Shader"], output.inputs["Surface"])

vert = bpy.data.texts.new("KeepVertex")
vert.write("void vertex() {}")
geom = bpy.data.texts.new("KeepGeometry")
geom.write("void geometry() { geom_emit(0); geom_emit(1); geom_emit(2); }")
frag = bpy.data.texts.new("KeepFragment")
frag.write("void fragment() {}")
mat.script_vert = vert
mat.script_geom = geom
mat.script_frag = frag

result = bpy.ops.material.to_classic_nodes()
assert result == {'FINISHED'}, result
assert not bpy.ops.material.to_classic_nodes.poll()
assert not scene.game_settings.use_shading_nodes
assert mat.script_vert == vert and mat.script_geom == geom and mat.script_frag == frag
assert not any(node.bl_idname == "ShaderNodeBsdfPrincipled" for node in mat.node_tree.nodes)

material_nodes = [node for node in mat.node_tree.nodes
                  if node.bl_idname == "ShaderNodeExtendedMaterial"]
assert len(material_nodes) == 1
base = material_nodes[0].material
assert abs(base.specular_metallic_bsdf - 0.7) < 1e-6
assert abs(base.specular_roughness_bsdf - 0.32) < 1e-6
assert abs(base.emit - 2.5) < 1e-6
assert base.use_transparency

slots = [slot for slot in base.texture_slots if slot and slot.texture]
assert len(slots) == 5, [(slot.texture.name, slot.uv_layer) for slot in slots]
assert all(slot.uv_layer == "UVMain" for slot in slots)
assert any(slot.use_map_color_diffuse for slot in slots)
assert any(slot.use_map_normal and abs(slot.normal_factor - 0.4) < 1e-6 for slot in slots)
assert any(slot.use_map_hardness and slot.invert for slot in slots)
assert any(slot.use_map_alpha for slot in slots)
assert any(slot.use_map_emit for slot in slots)

wm = bpy.context.window_manager
ui_context = SimpleNamespace(scene=scene, object=ob, material=mat, window_manager=wm)
category_items = bpy.types.WindowManager.bl_rna.properties[
    "ae_material_panel_category"].enum_items
assert [item.identifier for item in category_items] == ['SURFACE', 'GAME', 'SETUP']
assert not wm.ae_material_preview_visible
wm.ae_material_preview_visible = True
assert wm.ae_material_preview_visible
wm.ae_material_preview_visible = False
wm.ae_material_panel_category = 'SETUP'
assert material_ui.MATERIAL_PT_game_pbr_shading.poll(ui_context)
assert material_ui.MATERIAL_PT_recipes.poll(ui_context)
assert material_ui.MATERIAL_PT_convert_pbr.poll(ui_context)
assert not material_ui.MATERIAL_PT_diffuse.poll(ui_context)
assert not material_ui.MATERIAL_PT_game_settings.poll(ui_context)
wm.ae_material_panel_category = 'SURFACE'
assert not material_ui.MATERIAL_PT_game_pbr_shading.poll(ui_context)
assert not material_ui.MATERIAL_PT_recipes.poll(ui_context)
assert material_ui.MATERIAL_PT_diffuse.poll(ui_context)
assert material_ui.MATERIAL_PT_node_shader_sources.poll(ui_context)
assert not material_ui.MATERIAL_PT_game_settings.poll(ui_context)
wm.ae_material_panel_category = 'GAME'
assert not material_ui.MATERIAL_PT_recipes.poll(ui_context)
assert not material_ui.MATERIAL_PT_diffuse.poll(ui_context)
assert material_ui.MATERIAL_PT_game_settings.poll(ui_context)

convert_draw = inspect.getsource(material_ui.MATERIAL_PT_convert_pbr.draw)
assert "material.to_pbr_nodes" in convert_draw
assert "material.to_classic_nodes" in convert_draw
material_slot_draw = inspect.getsource(material_ui.MATERIAL_PT_context_material.draw)
assert "ae_material_panel_category" in material_slot_draw
assert "split(factor=0.58)" in material_slot_draw
assert "slot_layout = split.column()" in material_slot_draw
assert "preview_area = split.row()" in material_slot_draw
assert "slot_actions = preview_area.column(align=True)" in material_slot_draw
assert "template_preview(mat, show_buttons=False)" in material_slot_draw
assert '"preview_render_type"' in material_slot_draw
assert 'text="Material Preview"' not in material_slot_draw
assert "ae_material_preview_visible" in material_slot_draw
assert "split(factor=0.94)" in material_slot_draw
assert "col = slot_actions if slot_actions is not None else row.column(align=True)" in material_slot_draw
assert "split = layout.split(factor=0.65)" in material_slot_draw
assert not material_ui.MATERIAL_PT_preview.poll(ui_context)

if "--" in sys.argv:
    args = sys.argv[sys.argv.index("--") + 1:]
    output = os.path.abspath(args[0])
    bpy.ops.object.camera_add(location=(0.0, -4.0, 3.0), rotation=(1.0, 0.0, 0.0))
    camera = scene.objects.active
    scene.camera = camera
    bpy.ops.logic.sensor_add(type='ALWAYS', object=camera.name)
    bpy.ops.logic.controller_add(type='PYTHON', object=camera.name)
    camera.game.sensors[-1].use_pulse_true_level = True
    exit_text = bpy.data.texts.new("material_classic_test_exit.py")
    exit_text.write(
        "from Range import logic\n"
        "cont = logic.getCurrentController()\n"
        "own = cont.owner\n"
        "own['frames'] = own.get('frames', 0) + 1\n"
        "if own['frames'] >= 5:\n"
        "    open(logic.expandPath('//material_classic_runtime.ok'), 'w').write('ok\\n')\n"
        "    print('MATERIAL_CLASSIC_RUNTIME ok')\n"
        "    logic.endGame()\n"
    )
    camera.game.controllers[-1].text = exit_text
    camera.game.sensors[-1].link(camera.game.controllers[-1])
    bpy.ops.wm.save_as_mainfile(filepath=output)
    print("MATERIAL_CLASSIC_SCENE saved", output)

print("MATERIAL_CLASSIC_AND_CATEGORIES_TEST ok")
