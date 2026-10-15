"""Inspect and optionally reproduce a lightmap bake in an existing .range scene.

Run with AnastacioEngine.exe -b scene.range --python this_script.py. The scene is
never saved. Set AE_BAKE_REPRO_MODE=AO, STATIC, or INDIRECT to run the bake.
"""

import os

import bpy
import numpy as np


scene = bpy.context.scene
settings = scene.ae_lightmap_settings
print("AE_REPRO_SCENE", scene.name, "mode", settings.mode, "gpu", settings.use_gpu)
for obj in scene.objects:
    if obj.type != 'MESH':
        continue
    print("AE_REPRO_OBJECT", obj.name, "physics", obj.game.physics_type)
    for slot in obj.material_slots:
        mat = slot.material
        print("AE_REPRO_MATERIAL", mat.name if mat else None,
              "nodes", bool(mat and mat.use_nodes),
              "active_texture", bool(mat and mat.active_texture),
              "texture_slots", len([s for s in mat.texture_slots if s]) if mat else 0)

mode = os.environ.get("AE_BAKE_REPRO_MODE")
if mode:
    settings.mode = mode
    settings.use_gpu = os.environ.get("AE_BAKE_REPRO_GPU", "1") == "1"
    settings.resolution = os.environ.get("AE_BAKE_REPRO_RESOLUTION", "256")
    result = bpy.ops.scene.ae_lightmap_bake()
    print("AE_REPRO_BAKE_RESULT", sorted(result))
    print("AE_REPRO_IMAGE", scene.ae_lightmap,
          tuple(bpy.data.images[scene.ae_lightmap].size) if scene.ae_lightmap else None)
    if scene.ae_lightmap:
        rgba = np.array(bpy.data.images[scene.ae_lightmap].pixels[:],
                        dtype=np.float32).reshape(-1, 4)
        # RGBM stores the exposure multiplier in alpha, not a binary mask.
        covered = rgba[:, 3] > 0.001
        print("AE_REPRO_PIXELS", int(covered.sum()),
              "atlas_coverage", scene.ae_lightmap_atlas_coverage,
              float(rgba[covered, :3].min()) if covered.any() else None,
              float(rgba[covered, :3].max()) if covered.any() else None)
