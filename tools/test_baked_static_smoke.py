"""Headless smoke test for Render > Baked Lighting > Static Lighting + Shadows.

Run with build/bin/AnastacioEngine.exe --background --factory-startup --python
tools/test_baked_static_smoke.py. The scene exists only in memory unless an output path is passed after --.
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
    principled.inputs['Roughness'].default_value = 0.45
    material.node_tree.links.new(principled.outputs[0], output.inputs[0])
    return material


def make_mesh(name, primitive, location, material, physics='STATIC'):
    primitive(location=location)
    obj = bpy.context.object
    obj.name = name
    obj.game.physics_type = physics
    obj.data.materials.append(material)
    return obj


scene = bpy.context.scene
for obj in list(scene.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.use_shading_nodes = True
scene.world = bpy.data.worlds.new("Static Smoke World")
scene.world.horizon_color = (0.03, 0.03, 0.03)
scene.world.mist_settings.use_mist = False
material = add_material("Static Smoke Material")

floor = make_mesh("Static Floor", lambda **kw: bpy.ops.mesh.primitive_plane_add(radius=4.0, **kw),
                  (0.0, 0.0, 0.0), material)
cube = make_mesh("Static Shadow Caster", lambda **kw: bpy.ops.mesh.primitive_cube_add(radius=1.0, **kw),
                 (0.0, 0.0, 1.0), material)
moving = make_mesh("Moving Receiver", lambda **kw: bpy.ops.mesh.primitive_uv_sphere_add(size=0.4, **kw),
                   (2.5, 0.0, 0.5), material, 'DYNAMIC')

sun_data = bpy.data.lamps.new("Static Smoke Sun", 'SUN')
sun_data.energy = 2.0
sun_data.use_shadow = True
sun = bpy.data.objects.new(sun_data.name, sun_data)
sun.rotation_euler = Vector((4.0, -6.0, -8.0)).to_track_quat('-Z', 'Y').to_euler()
scene.objects.link(sun)

camera_data = bpy.data.cameras.new("Static Smoke Camera")
camera_data.lens = 16.0
camera = bpy.data.objects.new(camera_data.name, camera_data)
camera.location = (7.0, -9.0, 6.0)
camera.rotation_euler = (Vector((0.0, 0.0, 0.7)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
scene.objects.link(camera)
scene.camera = camera

settings = scene.ae_lightmap_settings
settings.mode = 'STATIC'
settings.resolution = '256'
settings.samples = 8
settings.margin = 2
settings.use_gpu = False
settings.use_denoise = False
settings.use_world = True
settings.use_volume = True
settings.volume_spacing = 20.0

from bl_operators.anastacio_lightmap import lightmap_objects, lightmap_excluded_counts
assert len(lightmap_objects(scene)) == 2
assert floor in lightmap_objects(scene) and cube in lightmap_objects(scene)
assert lightmap_excluded_counts(scene)["Dynamic physics (set Static to bake)"] == 1
cube.ae_lightmap_include = False
assert cube not in lightmap_objects(scene)
cube.ae_lightmap_include = True
assert cube in lightmap_objects(scene)
# A scene bake must include the caster even when the receiver is the active object.
scene.objects.active = floor

result = bpy.ops.scene.ae_lightmap_bake()
assert result == {'FINISHED'}, result
assert scene.ae_lightmap_mode == 'STATIC'
assert scene.ae_lightmap_use
assert scene.ae_lightvol and scene.ae_lightvol_use
assert list(scene.ae_lightvol_grid[6:]) == [1.0, 1.0, 1.0]
assert floor.data.uv_textures.get('Lightmap')
assert cube.data.uv_textures.get('Lightmap')
assert not moving.data.uv_textures.get('Lightmap')
assert 0.0 < scene.ae_lightmap_atlas_coverage < 100.0

image = bpy.data.images[scene.ae_lightmap]
pixels = np.array(image.pixels[:], dtype=np.float32).reshape(-1, 4)
covered = pixels[:, 3] > 0.0
assert covered.any()
rgbm = pixels[covered]
decoded = np.square(rgbm[:, :3] * rgbm[:, 3, None] * 8.0)
assert np.isfinite(decoded).all()
assert decoded.min() >= -1e-5
assert decoded.max() > 0.1
assert decoded.max() - decoded.min() > 0.1

# The next-bake selector must never reinterpret the committed image.
settings.mode = 'AO'
assert scene.ae_lightmap_mode == 'STATIC'
settings.mode = 'STATIC'
print("AE_STATIC_SMOKE_OK covered=%d min=%.4f max=%.4f" %
      (covered.sum(), decoded.min(), decoded.max()))

if '--' in sys.argv:
    output = os.path.abspath(sys.argv[sys.argv.index('--') + 1])
    probe = bpy.data.texts.new("static_runtime_probe.py")
    probe.write("""import bge
import os

def tick(cont):
    path = os.environ.get('AE_STATIC_RUNTIME_EVIDENCE')
    if path:
        with open(path, 'w') as handle:
            handle.write('AE_STATIC_RUNTIME_OK\\n')
    bge.logic.endGame()
""")
    runner = bpy.data.objects.new("Static Runtime Probe", None)
    scene.objects.link(runner)
    scene.objects.active = runner
    bpy.ops.logic.sensor_add(type='ALWAYS', name='Run Once', object=runner.name)
    bpy.ops.logic.controller_add(type='PYTHON', name='Static Probe', object=runner.name)
    sensor = runner.game.sensors['Run Once']
    controller = runner.game.controllers['Static Probe']
    controller.mode = 'MODULE'
    controller.module = 'static_runtime_probe.tick'
    sensor.link(controller)
    bpy.ops.wm.save_as_mainfile(filepath=output, check_existing=False)
    print("AE_STATIC_SMOKE_SCENE", output)
