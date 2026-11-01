"""Writes two copies of a scene for the TAA comparison in the browser (docs/plano-taa.md):
<out>/taa_off.range (TAA and FXAA off) and <out>/taa_on.range (TAA on, FXAA off).

    AnastacioEngine -b <scene>.range --python tools/debug/make_taa_scenes.py -- <out>

The camera logic is removed so both pages show the same still view.
"""

import os
import sys

import bpy

out = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "/tmp/taa_web"
os.makedirs(out, exist_ok=True)

scene = bpy.context.scene
cam = scene.camera
if cam is not None:
    for ctrl in list(cam.game.controllers):
        cam.game.controllers.remove(ctrl)
    for sens in list(cam.game.sensors):
        cam.game.sensors.remove(sens)

fx = scene.scenefx_settings
fx.use_fxaa = False
for name, taa in (("taa_off", False), ("taa_on", True)):
    fx.use_taa = taa
    path = os.path.join(out, name + ".range")
    bpy.ops.wm.save_as_mainfile(filepath=path, copy=True)
    print("TAASCENE", path, "use_taa=%s sharpen=%.2f" % (fx.use_taa, fx.taa_sharpen))
