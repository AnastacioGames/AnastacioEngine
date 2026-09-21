"""Gera m3-dynamic-resolution-no-timer.range para a sonda Web sem timer GPU.

Uso: RangeEngine.exe -b --python criar_m3_dynamic_resolution_no_timer.py
"""
import os
import bpy


out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "m3-dynamic-resolution-no-timer.range")
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
settings = scene.game_settings
settings.resolution_x = 640
settings.resolution_y = 360
settings.use_dynamic_resolution = True
settings.dynamic_resolution_target_fps = 60
settings.dynamic_resolution_min_scale = 50
settings.dynamic_resolution_max_scale = 100
settings.dynamic_resolution_step = 5
empty = bpy.data.objects.new("DynamicResolutionProbe", None)
scene.objects.link(empty)
scene.objects.active = empty
bpy.ops.logic.sensor_add(type='ALWAYS', name='Always', object=empty.name)
bpy.ops.logic.controller_add(type='PYTHON', name='M3 no timer', object=empty.name)
empty.game.sensors[0].use_pulse_true_level = True
controller = empty.game.controllers[0]
controller.mode = 'MODULE'
controller.module = 'm3_dynamic_resolution_no_timer.rodar'
empty.game.sensors[0].link(controller)
bpy.ops.wm.save_as_mainfile(filepath=out)
print("gravado", out)
