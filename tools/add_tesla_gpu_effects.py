"""Add native GPU spark accents and ground mist to the cinematic Tesla scene."""
import bpy
import os
import shutil

scene = bpy.context.scene
prefix = 'Anastacio_GPU_'


def emitter(name, position, look, count):
    ob = scene.objects.get(prefix + name)
    if ob is None:
        ob = bpy.data.objects.new(prefix + name, None)
        scene.objects.link(ob)
    ob.location = position
    ob.use_gpu_particles = True
    gp = ob.gpu_particles
    gp.particle_look = look
    gp.particle_count = count
    gp.emit_from = 'VOLUME'
    gp.emitter_position = (0, 0, 0)
    gp.enabled = True
    gp.collision_mode = 'NONE'
    gp.billboard_mode = 'CAMERA_FACING'
    gp.use_debug_ui = False
    return ob, gp


for i in range(8):
    top = scene.objects['Bobina_%d_Toro' % i]
    ob, gp = emitter('Faiscas_%d' % i, top.matrix_world.translation, 'SPARKLE', 32)
    gp.enabled = False
    gp.lifetime = 0.4
    gp.emitter_radius = 0.55
    gp.gravity = (0, 0, -1.4)
    gp.velocity = (0, 0, 0.65)
    gp.velocity_randomness = 0.8
    gp.emission_direction = (0, 0, 1)
    gp.emission_angle = 150
    gp.size = 0.055
    gp.end_size = 0.008
    gp.color = (0.35, 0.65, 1, 0.8)
    gp.end_color = (0.16, 0.28, 0.6, 0)
    gp.blend_mode = 'ADDITIVE'

center = scene.objects['Terminal'].matrix_world.translation
ob, gp = emitter('Carga_Central', center, 'SPARKLE', 20)
gp.lifetime = 2.5
gp.emitter_radius = 1.25
gp.velocity = (0, 0, 0.06)
gp.velocity_randomness = 0.08
gp.gravity = (0, 0, 0)
gp.size = 0.025
gp.end_size = 0.005
gp.color = (0.22, 0.45, 1, 0.3)
gp.end_color = (0.1, 0.22, 0.5, 0)
gp.blend_mode = 'ADDITIVE'

for name, pos in [('Nevoa_Esquerda', (-7, 5, 0.45)), ('Nevoa_Direita', (7, 5, 0.45))]:
    ob, gp = emitter(name, pos, 'SMOKE', 36)
    gp.lifetime = 7
    gp.emitter_radius = 2.6
    gp.velocity = (0.12, 0.02, 0.015)
    gp.velocity_randomness = 0.03
    gp.gravity = (0, 0, 0)
    gp.size = 1.15
    gp.end_size = 2.4
    gp.color = (0.18, 0.25, 0.33, 0.055)
    gp.end_color = (0.12, 0.17, 0.23, 0)
    gp.blend_mode = 'ALPHA'

text = bpy.data.texts['piano_tesla.py']
script = text.as_string()
if '# ANASTACIO_GPU_ACCENTS' not in script:
    setup = '''
# ANASTACIO_GPU_ACCENTS: timed native GPU accents, no new shaders or textures.
def tesla_fx_hit(index, duration=0.45):
    emitter = logic.getCurrentScene().objects['Anastacio_GPU_Faiscas_%d' % index]
    emitter['tesla_fx_until'] = logic.getFrameTime() + duration
    emitter['tesla_fx_duration'] = duration
    emitter.particles.enabled = True

'''
    marker = 'for tecla, (bobina, som) in sons.items():'
    if script.count(marker) != 1:
        raise RuntimeError('Unexpected piano script')
    script = script.replace(marker, setup + marker)
    script = script.replace('        device.play(som)', '        device.play(som)\n        tesla_fx_hit(bobina)')
    script = script.replace('    device.play(som_trovao)', '    device.play(som_trovao)\n    for index in range(8):\n        tesla_fx_hit(index, 0.75)')
    script += '''
now = logic.getFrameTime()
for index in range(8):
    emitter = logic.getCurrentScene().objects['Anastacio_GPU_Faiscas_%d' % index]
    remaining = max(0.0, emitter.get('tesla_fx_until', 0.0) - now)
    if remaining > 0:
        fade = min(1.0, remaining / 0.2)
        emitter.particles.color = (0.35, 0.65, 1.0, 0.8 * fade)
    else:
        emitter.particles.enabled = False
'''
    compile(script, text.name, 'exec')
    text.from_string(script)
source = bpy.data.filepath
backup = os.path.splitext(source)[0] + '_before_gpu_effects.range'
if not os.path.exists(backup):
    shutil.copy2(source, backup)
bpy.ops.wm.save_as_mainfile(filepath=source)
print('TESLA_GPU_SAVED', source, 'emitters', 11, 'pool', 348, flush=True)
