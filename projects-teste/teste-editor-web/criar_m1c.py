"""Gera m1c-shader.range (cubo com material + controller Python shader_quebrado.quebrar).
Uso: RangeEngine.exe -b --python criar_m1c.py [-- --link]   (grava ao lado deste arquivo;
--link gera m1c-shader-link.range com falha de link)"""
import os
import bpy

import sys
MODO = "link" if "--link" in sys.argv else "vertex"
out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "m1c-shader-link.range" if MODO == "link" else "m1c-shader.range")
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.use_glsl_lights = True

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
mat = bpy.data.materials.new('MatQuebradoLink' if MODO == 'link' else 'MatQuebrado')
me.materials.append(mat)
ob = bpy.data.objects.new('Cubo', me)
scene.objects.link(ob)
scene.objects.active = ob

bpy.ops.logic.sensor_add(type='ALWAYS', name='Always', object='Cubo')
bpy.ops.logic.controller_add(type='PYTHON', name='Quebrar', object='Cubo')
ob.game.sensors[0].use_pulse_true_level = False
c = ob.game.controllers[0]
c.mode = 'MODULE'
c.module = 'shader_quebrado.quebrar_link' if MODO == 'link' else 'shader_quebrado.quebrar'
ob.game.sensors[0].link(c)
bpy.ops.wm.save_as_mainfile(filepath=out)
print("gravado", out)
