import inspect
from types import SimpleNamespace

import bpy
from bl_ui import properties_texture as texture_ui


scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
texture = bpy.data.textures.new("AE_TexturePreviewTest", type='IMAGE')
context = SimpleNamespace(scene=scene, texture=texture)
wm = bpy.context.window_manager

assert not wm.ae_texture_preview_visible
wm.ae_texture_preview_visible = True
assert wm.ae_texture_preview_visible
wm.ae_texture_preview_visible = False

draw_source = inspect.getsource(texture_ui.TEXTURE_PT_texture_slots.draw)
assert "ae_texture_preview_visible" in draw_source
assert "split(factor=0.58)" in draw_source
assert "split(factor=0.94)" in draw_source
assert "preview.template_preview" in draw_source
assert "slot_actions" in draw_source
assert not texture_ui.TEXTURE_PT_preview.poll(context)

print("TEXTURE_PREVIEW_LAYOUT_TEST ok")
