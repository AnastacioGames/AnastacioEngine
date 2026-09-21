"""Gera m3-bloom-resize.range para o teste Web de resize do Bloom.

Uso: RangeEngine.exe -b --python criar_m3_bloom_resize.py
"""
import os
import bpy


def cube_mesh():
    mesh = bpy.data.meshes.new("Cubo")
    mesh.from_pydata([(x, y, z) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)], [],
                      [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1),
                       (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)])
    mesh.update()
    return mesh


out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "m3-bloom-resize.range")
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.resolution_x = 640
scene.game_settings.resolution_y = 360
cube = bpy.data.objects.new("Cubo", cube_mesh())
scene.objects.link(cube)
scene.objects.active = cube
bpy.ops.logic.sensor_add(type='ALWAYS', name='Always', object=cube.name)
bpy.ops.logic.controller_add(type='PYTHON', name='M3 bloom resize', object=cube.name)
cube.game.sensors[0].use_pulse_true_level = True
controller = cube.game.controllers[0]
controller.mode = 'MODULE'
controller.module = 'm3_bloom_resize.rodar'
cube.game.sensors[0].link(controller)
bpy.ops.wm.save_as_mainfile(filepath=out)
print("gravado", out)
