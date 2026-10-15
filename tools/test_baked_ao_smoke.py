"""Headless smoke test for Render > Baked Lighting > Ambient Occlusion.

Run with build/bin/AnastacioEngine.exe --background --factory-startup --python tools/test_baked_ao_smoke.py.
The scene exists only in memory; this script never saves over a project.
"""

import os
import sys

import bpy
import numpy as np
from mathutils import Vector


def add_material(name):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    principled = nodes.new("ShaderNodeBsdfPrincipled")
    material.node_tree.links.new(principled.outputs[0], output.inputs[0])
    return material


def make_static(name, primitive, location, material):
    primitive(location=location)
    obj = bpy.context.object
    obj.name = name
    obj.game.physics_type = 'STATIC'
    obj.data.materials.append(material)
    return obj


scene = bpy.context.scene
for obj in list(scene.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.use_shading_nodes = True
scene.world = bpy.data.worlds.new("AO Smoke World")
scene.world.horizon_color = (0.35, 0.35, 0.35)
scene.world.mist_settings.use_mist = False
material = add_material("AO Smoke Material")

make_static("AO Floor", lambda **kw: bpy.ops.mesh.primitive_plane_add(radius=4.0, **kw),
            (0.0, 0.0, 0.0), material)
make_static("AO Cube", lambda **kw: bpy.ops.mesh.primitive_cube_add(radius=1.0, **kw),
            (0.0, 0.0, 1.0), material)

sun_data = bpy.data.lamps.new("AO Smoke Sun", 'SUN')
sun_data.energy = 1.0
sun_data.use_shadow = True
sun = bpy.data.objects.new(sun_data.name, sun_data)
sun.rotation_euler = Vector((4.0, -6.0, -8.0)).to_track_quat('-Z', 'Y').to_euler()
scene.objects.link(sun)

camera_data = bpy.data.cameras.new("AO Smoke Camera")
camera_data.lens = 16.0
camera = bpy.data.objects.new(camera_data.name, camera_data)
camera.location = (7.0, -9.0, 6.0)
camera.rotation_euler = (Vector((0.0, 0.0, 0.7)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
scene.objects.link(camera)
scene.camera = camera

settings = scene.ae_lightmap_settings
settings.mode = 'AO'
settings.resolution = '256'
settings.samples = 8
settings.margin = 2
settings.use_gpu = False
settings.use_denoise = False
settings.ao_distance = 3.0
settings.ao_strength = 1.0

light = scene.world.light_settings
before = (light.use_ambient_occlusion, light.ao_factor, light.distance)
result = bpy.ops.scene.ae_lightmap_bake()
assert result == {'FINISHED'}, result
assert scene.ae_lightmap_mode == 'AO'
assert scene.ae_lightmap_use
assert not scene.ae_lightvol and not scene.ae_lightvol_use
assert before == (light.use_ambient_occlusion, light.ao_factor, light.distance)

image = bpy.data.images[scene.ae_lightmap]
pixels = np.array(image.pixels[:], dtype=np.float32).reshape(-1, 4)
covered = pixels[:, 3] > 0.0
assert covered.any()
rgbm = pixels[covered]
decoded = np.square(rgbm[:, :3] * rgbm[:, 3, None] * 8.0)
assert np.isfinite(decoded).all()
assert decoded.min() >= -1e-5 and decoded.max() <= 1.01
assert np.max(np.abs(decoded[:, 0] - decoded[:, 1])) < 1e-4
assert np.max(np.abs(decoded[:, 1] - decoded[:, 2])) < 1e-4
assert decoded.min() < 0.9 and decoded.max() > 0.95

# The next-bake selector must never reinterpret the committed image.
settings.mode = 'INDIRECT'
assert scene.ae_lightmap_mode == 'AO'
settings.mode = 'AO'
print("AE_AO_SMOKE_OK covered=%d min=%.4f max=%.4f" %
      (covered.sum(), decoded.min(), decoded.max()))

if '--' in sys.argv:
    output = os.path.abspath(sys.argv[sys.argv.index('--') + 1])
    probe = bpy.data.texts.new("ao_runtime_probe.py")
    probe.write("""import bge
import os

def tick(cont):
    path = os.environ.get('AE_AO_RUNTIME_EVIDENCE')
    if path:
        with open(path, 'w') as handle:
            handle.write('AE_AO_RUNTIME_OK\\n')
    bge.logic.endGame()
""")
    runner = bpy.data.objects.new("AO Runtime Probe", None)
    scene.objects.link(runner)
    scene.objects.active = runner
    bpy.ops.logic.sensor_add(type='ALWAYS', name='Run Once', object=runner.name)
    bpy.ops.logic.controller_add(type='PYTHON', name='AO Probe', object=runner.name)
    sensor = runner.game.sensors['Run Once']
    controller = runner.game.controllers['AO Probe']
    controller.mode = 'MODULE'
    controller.module = 'ao_runtime_probe.tick'
    sensor.link(controller)
    bpy.ops.wm.save_as_mainfile(filepath=output, check_existing=False)
    print("AE_AO_SMOKE_SCENE", output)
