"""Gera claude-aud-noargs.range (controller claude_aud_noargs_probe.rodar: audio invalido no Web).
Uso: RangeEngine.exe -b --python claude_r3_criar.py   (grava ao lado deste arquivo)"""
import os
import bpy

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "claude-aud-noargs.range")
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.world = bpy.data.worlds.new('Mundo')

cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
scene.objects.link(cam)
cam.location = (0, -6, 2)
cam.rotation_euler = (1.3, 0, 0)
scene.camera = cam
sun = bpy.data.objects.new('Sun', bpy.data.lamps.new('Sun', 'SUN'))
scene.objects.link(sun)
me = bpy.data.meshes.new('Cubo')
me.from_pydata([(x, y, z) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)], [],
               [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)])
me.update()
ob = bpy.data.objects.new('Cubo', me)
scene.objects.link(ob)
scene.objects.active = ob
bpy.ops.logic.sensor_add(type='ALWAYS', name='Always', object='Cubo')
bpy.ops.logic.controller_add(type='PYTHON', name='M3R', object='Cubo')
ob.game.sensors[0].use_pulse_true_level = True
c = ob.game.controllers[0]
c.mode = 'MODULE'
c.module = "claude_aud_noargs_probe.rodar"
ob.game.sensors[0].link(c)
bpy.ops.wm.save_as_mainfile(filepath=out)
print("gravado", out)
