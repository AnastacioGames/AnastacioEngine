"""Cena controlada para comparar a referencia Camera/Light do CSM.

Uso:
  AnastacioEngine.exe -b --factory-startup --python tools/debug/cenas/criar_cena_csm_reference.py -- saida.range CAMERA
  AnastacioEngine.exe -b --factory-startup --python tools/debug/cenas/criar_cena_csm_reference.py -- saida.range LIGHT

O debug do CSM fica ligado. Camera desenha fatias que partem da camera ativa; Light desenha
tres caixas concentricas no espaco local da Sun. O runtime grava evidencia em CSM_REFERENCE_RESULT.
"""
import bpy
import os
import sys
from mathutils import Vector


args = sys.argv[sys.argv.index("--") + 1:]
output = os.path.abspath(args[0])
reference = args[1].upper()
if reference not in {"CAMERA", "LIGHT"}:
    raise ValueError("Referencia deve ser CAMERA ou LIGHT")

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = "BLENDER_GAME"
scene.game_settings.use_frame_rate = False
scene.game_settings.vsync = "OFF"
scene.game_settings.use_shading_nodes = False
scene.render.resolution_x = 960
scene.render.resolution_y = 540
scene["csm_reference_expected"] = reference

world = bpy.data.worlds.new("CSM Reference World")
world.horizon_color = (0.04, 0.05, 0.08)
world.mist_settings.use_mist = False
scene.world = world


def material(name, color):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = color
    mat.use_shadeless = False
    return mat


ground_mat = material("Ground", (0.32, 0.36, 0.42))
near_mat = material("Near", (0.75, 0.15, 0.08))
middle_mat = material("Middle", (0.12, 0.65, 0.18))
far_mat = material("Far", (0.08, 0.20, 0.75))

bpy.ops.mesh.primitive_plane_add(radius=45, location=(0, 5, 0))
ground = bpy.context.object
ground.name = "Ground"
ground.data.materials.append(ground_mat)

# Marcos distribuídos pela cena tornam as transicoes das tres cascatas legiveis.
for band, y, mat in (("Near", -8, near_mat), ("Middle", 5, middle_mat), ("Far", 22, far_mat)):
    for x in (-9, -3, 3, 9):
        bpy.ops.mesh.primitive_cube_add(radius=1.2, location=(x, y, 2.4))
        obj = bpy.context.object
        obj.name = "%s_%+d" % (band, x)
        obj.scale = (1.0, 1.0, 2.0)
        obj.data.materials.append(mat)

lamp_data = bpy.data.lamps.new("CSM Sun", "SUN")
lamp_data.use_shadow = True
lamp_data.use_csm_shadow = True
lamp_data.csm_reference = reference
lamp_data.use_csm_debug = True
lamp_data.cascaded_proportion_two = 0.25
lamp_data.cascaded_proportion_three = 0.35
lamp_data.shadow_buffer_size = 1024
lamp_data.shadow_csm_two_buffer_size = 512
lamp_data.shadow_csm_three_buffer_size = 256
lamp_data.shadow_buffer_clip_start = 1.0
lamp_data.shadow_buffer_clip_end = 80.0
lamp_data.shadow_frustum_size = 16.0
lamp_data.energy = 1.0
sun = bpy.data.objects.new("CSM Sun", lamp_data)
sun.location = (-24, -12, 28)
sun.rotation_euler = (Vector((0, 8, 0)) - sun.location).to_track_quat("-Z", "Y").to_euler()
scene.objects.link(sun)

camera_data = bpy.data.cameras.new("Camera")
camera_data.lens = 20
camera_data.clip_start = 0.1
camera_data.clip_end = 120.0
camera = bpy.data.objects.new("Camera", camera_data)
camera.location = (24, -34, 18)
camera.rotation_euler = (Vector((0, 8, 2)) - camera.location).to_track_quat("-Z", "Y").to_euler()
scene.objects.link(camera)
scene.camera = camera

probe_source = '''import bge
import os

state = {"frames": 0}

def tick(cont):
    state["frames"] += 1
    if state["frames"] < 90:
        return
    stats = bge.logic.getRenderStats()
    path = os.environ.get("CSM_REFERENCE_RESULT")
    if path:
        with open(path, "w") as handle:
            handle.write("reference=%s\\n" % cont.owner["reference"])
            handle.write("shadowPasses=%s\\n" % stats.get("shadowPasses", -1))
            handle.write("lightsShadowUpdated=%s\\n" % stats.get("lightsShadowUpdated", -1))
    bge.logic.endGame()
'''
text = bpy.data.texts.new("csm_reference_probe.py")
text.write(probe_source)
bpy.ops.object.add(type="EMPTY", location=(0, 0, 0))
probe = bpy.context.object
probe.name = "CSM Reference Probe"
probe["reference"] = reference
bpy.ops.logic.sensor_add(type="ALWAYS", name="Always", object=probe.name)
bpy.ops.logic.controller_add(type="PYTHON", name="Probe", object=probe.name)
sensor = probe.game.sensors["Always"]
sensor.use_pulse_true_level = True
controller = probe.game.controllers["Probe"]
controller.mode = "MODULE"
controller.module = "csm_reference_probe.tick"
sensor.link(controller)

bpy.ops.wm.save_as_mainfile(filepath=output, check_existing=False)
print("CSM_REFERENCE_SCENE", reference, output)
