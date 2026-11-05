# SPDX-License-Identifier: GPL-2.0-or-later
"""KTX2 orientation on the GPU: two shadeless planes seen from above, with cor.ktx2 (from the engine)
and externo.ktx2 (see testar_ktx2_marca.py). Both must show blue at the top and red at the bottom.
  AnastacioEngine -b --factory-startup --python this.py -- <dir>
  ANASTACIO_KTX2_TARGET=bc|etc2|astc|rgba KTX2_GPU_OUTPUT=out.json AnastacioRuntime <dir>/ktx2-gpu.range
"""
import math
import os
import sys
import bpy

folder = os.path.abspath(sys.argv[sys.argv.index('--') + 1])
scene = bpy.context.scene
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.resolution_x = 640
scene.game_settings.resolution_y = 320
scene.game_settings.show_fullscreen = False
scene.world = scene.world or bpy.data.worlds.new('World')

for x, name in ((-1.1, 'cor'), (1.1, 'externo')):
    image = bpy.data.images.load(os.path.join(folder, name + '.ktx2'), check_existing=False)
    image.name = name
    image.colorspace_settings.name = 'Non-Color'
    image.pack()
    mat = bpy.data.materials.new(name)
    mat.use_shadeless = True
    mat.diffuse_color = (1, 1, 1)
    tex = bpy.data.textures.new(name, 'IMAGE')
    tex.image = image
    slot = mat.texture_slots.add()
    slot.texture = tex
    slot.texture_coords = 'UV'
    bpy.ops.mesh.primitive_plane_add(radius=1, location=(x, 0, 0), calc_uvs=True)
    plane = scene.objects.active
    plane.name = name
    plane.game.physics_type = 'NO_COLLISION'
    plane.data.materials.append(mat)

data = bpy.data.cameras.new('Camera')
data.type = 'ORTHO'
data.ortho_scale = 4.4
camera = bpy.data.objects.new('Camera', data)
scene.objects.link(camera)
camera.location = (0, 0, 5)
camera.rotation_euler = (0, 0, 0)
scene.camera = camera
scene.objects.active = camera
camera.select = True

text = bpy.data.texts.new('ktx2_probe.py')
text.write('''import bge, bgl, json, os
state = {'n': 0}
def tick(cont):
    state['n'] += 1
    if state['n'] < 20:
        return
    w, h = bge.render.getWindowWidth(), bge.render.getWindowHeight()
    rows = {}
    buf = bgl.Buffer(bgl.GL_FLOAT, 4)
    for name, u in (('cor', 0.25), ('externo', 0.75)):
        for where, v in (('top', 0.75), ('bottom', 0.25)):
            bgl.glReadPixels(int(w * u), int(h * v), 1, 1, bgl.GL_RGBA, bgl.GL_FLOAT, buf)
            rows[name + '_' + where] = [round(c, 2) for c in buf.to_list()]
    with open(os.environ['KTX2_GPU_OUTPUT'], 'w') as stream:
        json.dump(rows, stream)
    bge.logic.endGame()
''')
bpy.ops.logic.sensor_add(type='ALWAYS', object=camera.name)
sensor = camera.game.sensors[-1]
sensor.use_pulse_true_level = True
bpy.ops.logic.controller_add(type='PYTHON', object=camera.name)
controller = camera.game.controllers[-1]
controller.mode = 'MODULE'
controller.module = 'ktx2_probe.tick'
sensor.link(controller)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(folder, 'ktx2-gpu.range'))
print('KTX2_GPU_SCENE_CREATED')
