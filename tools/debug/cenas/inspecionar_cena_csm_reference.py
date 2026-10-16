"""Inspeciona uma cena do gerador criar_cena_csm_reference.py e grava evidencia textual."""
import bpy
import os
import sys


args = sys.argv[sys.argv.index("--") + 1:]
output = os.path.abspath(args[0])
scene = bpy.context.scene
sun = scene.objects["CSM Sun"]
probe = scene.objects["CSM Reference Probe"]
sensor = probe.game.sensors["Always"]
controller = probe.game.controllers["Probe"]

lines = [
    "scene=%s" % scene.name,
    "camera=%s" % (scene.camera.name if scene.camera else "NONE"),
    "reference=%s" % sun.data.csm_reference,
    "csm=%s" % sun.data.use_csm_shadow,
    "debug=%s" % sun.data.use_csm_debug,
    "clip=%.3f,%.3f" % (sun.data.shadow_buffer_clip_start, sun.data.shadow_buffer_clip_end),
    "frustum=%.3f" % sun.data.shadow_frustum_size,
    "meshes=%d" % len([obj for obj in scene.objects if obj.type == "MESH"]),
    "probe_module=%s" % controller.module,
    "probe_pulse=%s" % sensor.use_pulse_true_level,
    "probe_text=%s" % ("csm_reference_probe.py" in bpy.data.texts),
]
with open(output, "w") as handle:
    handle.write("\n".join(lines) + "\n")
print("CSM_REFERENCE_INSPECTION", output)
