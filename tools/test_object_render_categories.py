from types import SimpleNamespace

import bpy
import inspect
import bl_ui
from bl_ui import properties_game as game_ui
from bl_ui import properties_object as object_ui
from bl_ui import properties_render_engine as render_engine_ui
from bl_ui import properties_render as render_ui


scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'

module_names = list(bl_ui._modules)
assert module_names.index('properties_render_engine') < module_names.index('properties_game')
assert module_names.index('properties_game') < module_names.index('properties_object')
assert object_ui.classes[-2:] == (object_ui.OBJECT_PT_context_object,
                                  object_ui.OBJECT_PT_game_context_object)

mesh = bpy.data.meshes.new("AE_CategoryTestMesh")
ob = bpy.data.objects.new("AE_CategoryTestObject", mesh)
scene.objects.link(ob)
scene.objects.active = ob
ob.select = True

wm = bpy.context.window_manager
context = SimpleNamespace(scene=scene, object=ob, active_object=ob,
                          window_manager=wm, space_data=SimpleNamespace(use_pin_id=False))

object_items = bpy.types.WindowManager.bl_rna.properties[
    "ae_object_panel_category"].enum_items
assert [item.identifier for item in object_items] == ['OBJECT', 'GAME', 'TRANSFORM']
assert wm.ae_object_panel_category == 'OBJECT'
context_draw = inspect.getsource(object_ui.OBJECT_PT_game_context_object.draw)
assert 'use_fake_user' not in context_draw
assert 'ae_object_panel_category' in context_draw
assert not object_ui.OBJECT_PT_context_object.poll(context)
assert object_ui.OBJECT_PT_game_context_object.poll(context)
assert object_ui.OBJECT_PT_game_context_object.bl_options == {'PIN_TO_TOP'}
for panel in (game_ui.OBJECT_PT_game_object_tasks,
              game_ui.OBJECT_MT_culling,
              game_ui.OBJECT_PT_levels_of_detail,
              game_ui.OBJECT_PT_animation_events):
    assert panel.bl_context == 'object'
# Network e Activity Culling ficam na aba Game (Physics), por preferencia do usuario.
for panel in (game_ui.OBJECT_PT_game_network, game_ui.OBJECT_PT_activity_culling):
    assert panel.bl_context == 'game'
assert not object_ui.OBJECT_PT_transform.poll(context)
assert object_ui.OBJECT_PT_relations.poll(context)
assert object_ui.OBJECT_PT_display.poll(context)
assert not game_ui.OBJECT_PT_game_object_tasks.poll(context)

wm.ae_object_panel_category = 'GAME'
assert not object_ui.OBJECT_PT_relations.poll(context)
assert not object_ui.OBJECT_PT_display.poll(context)
assert game_ui.OBJECT_PT_game_object_tasks.poll(context)
assert game_ui.OBJECT_MT_culling.poll(context)
assert game_ui.OBJECT_PT_levels_of_detail.poll(context)
assert game_ui.OBJECT_PT_animation_events.poll(context)

wm.ae_object_panel_category = 'TRANSFORM'
assert object_ui.OBJECT_PT_transform.poll(context)
assert not object_ui.OBJECT_PT_relations.poll(context)
assert not object_ui.OBJECT_PT_display.poll(context)
assert not game_ui.OBJECT_PT_game_object_tasks.poll(context)

render_items = bpy.types.WindowManager.bl_rna.properties[
    "ae_render_panel_category"].enum_items
assert [item.identifier for item in render_items] == ['SYSTEM', 'GRAPHICS']
assert wm.ae_render_panel_category == 'SYSTEM'
assert render_engine_ui.RENDER_PT_render.poll(context)
assert game_ui.RENDER_PT_game_cook.poll(context)
assert game_ui.RENDER_PT_embedded.poll(context)
assert game_ui.RENDER_PT_game_animations.poll(context)
assert not game_ui.RENDER_PT_game_shading.poll(context)
assert game_ui.RENDER_PT_game_system.poll(context)
assert game_ui.RENDER_PT_game_display.poll(context)
assert game_ui.RENDER_PT_game_vr.poll(context)
assert not render_ui.RENDER_PT_bake.poll(context)

wm.ae_render_panel_category = 'GRAPHICS'
assert game_ui.RENDER_PT_game_shading.poll(context)
assert not game_ui.RENDER_PT_game_cook.poll(context)
assert not game_ui.RENDER_PT_game_system.poll(context)
assert render_ui.RENDER_PT_bake.poll(context)

print("OBJECT_RENDER_CATEGORIES_TEST ok")
