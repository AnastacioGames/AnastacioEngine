"""One-off headless setup script for the Ketsji Plano 1A item 4 smoke test.

Not part of the test itself; run once to produce the dedicated scene file:
  build/bin/RangeEngine.exe -b "projects-teste/Teste de nova luz e sombra.range" \
      -P projects-teste/scripts/_setup_sun_projection_scene.py

Finds the existing Sun lamp in the source scene, assigns it as the scene's
world_sun (required for KX_Scene::GetWorldSun() to return non-null), and
saves a new dedicated file so the smoke test does not depend on unrelated
scene content or on hand-editing a .blend in the GUI.
"""

import bpy

scene = bpy.context.scene

sun_object = None
for obj in scene.objects:
    if obj.type == "LAMP" and obj.data.type == "SUN":
        sun_object = obj
        break

if sun_object is None:
    raise RuntimeError("No Sun-type lamp found in the source scene")

scene.world_sun_set = sun_object

import os

out_path = os.path.join(os.path.dirname(bpy.data.filepath), "ketsji_sun_projection_smoke.range")
bpy.ops.wm.save_as_mainfile(filepath=out_path, copy=True)
print("KETSJI_SUN_PROJECTION_SETUP: saved with world_sun={}".format(sun_object.name))
