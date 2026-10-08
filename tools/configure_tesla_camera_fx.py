"""Enable native focus/blur on the existing cinematic Tesla scene.

Run with RangeEngine -b TeslaPiano_Cinematic.range --python <this file>.
"""
import bpy
import os
import shutil

scene = bpy.context.scene
cam = scene.camera
target = scene.objects.get('Terminal')
if not cam or not target:
    raise RuntimeError('Camera or central Terminal missing')
fx = cam.data.game_fx
cam.data.dof_object = target
cam.data.gpu_dof.focus_distance = (target.matrix_world.translation - cam.matrix_world.translation).length
cam.data.gpu_dof.blades = 6
fx.focus_mode = 'OBJECT'
fx.focus_range = 8.0
fx.focus_smooth = 0.2
fx.use_dof = True
fx.dof_quality = 'MEDIUM'
fx.dof_blur = 3.5
fx.use_speed_blur = True
fx.speed_blur_strength = 0.16
fx.speed_blur_max_speed = 10.0
fx.use_directional_blur = True
fx.directional_blur_strength = 0.18
fx.directional_blur_max = 0.012
fx.use_blur_protect = True
fx.use_cat_eye = True
fx.cat_eye_strength = 0.2
fx.use_vignette = True
fx.vignette_strength = 0.12
fx.vignette_radius = 1.0
fx.fisheye_strength = 0.0

text = bpy.data.texts['piano_tesla.py']
script = text.as_string()
if '# ANASTACIO_SHAKE_BLUR' not in script:
    # Lens-shift shake does not translate the camera, so feed its native trauma
    # into the existing speed override to make radial blur follow each impact.
    script += '''
# ANASTACIO_SHAKE_BLUR: stationary camera; native blur follows musical trauma.
camera = logic.getCurrentScene().active_camera
camera.speedOverride = camera.shakeTrauma ** 2 * camera.speedBlurMaxSpeed * 0.35
'''
    compile(script, 'piano_tesla.py', 'exec')
    text.from_string(script)
source = bpy.data.filepath
backup = os.path.splitext(source)[0] + '_before_camera_fx.range'
if not os.path.exists(backup):
    shutil.copy2(source, backup)
bpy.ops.wm.save_as_mainfile(filepath=source)
print('TESLA_CAMERA_FX_SAVED', source, 'focus', target.name, flush=True)
