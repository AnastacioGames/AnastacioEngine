"""Inject a short runtime probe into a copy of the legacy constraints tutorial.

Usage:
  AnastacioEngine.exe -b constraintsTutorial.range --python validar_tutorial_constraints_legado.py -- out.range out.txt
"""

import bpy
import sys


out_range, out_log = sys.argv[sys.argv.index('--') + 1:sys.argv.index('--') + 3]
scene = bpy.context.scene
text = bpy.data.texts.new('legacy_constraint_runtime_probe.py')
text.write("""import bge
import os

def tick(cont):
    own = cont.owner
    frame = own.get('probe_frame', 0) + 1
    own['probe_frame'] = frame
    if frame == 20:
        scene = bge.logic.getCurrentScene()
        expected = ('HingeSocket', 'HingeSocket.002', 'SliderSocket', 'Socket', 'Socket.002')
        found = [name for name in expected if name in scene.objects]
        path = os.environ.get('CONSTRAINT_TUTORIAL_LOG')
        if path:
            with open(path, 'w') as handle:
                handle.write('LEGACY_CONSTRAINT_TUTORIAL_RUNTIME: frames=%d expected_owners=%d\\n' % (frame, len(found)))
        bge.logic.endGame()
""")

probe = bpy.data.objects.new('legacy_constraint_runtime_probe', None)
scene.objects.link(probe)
scene.objects.active = probe
bpy.ops.logic.sensor_add(type='ALWAYS', name='always', object=probe.name)
bpy.ops.logic.controller_add(type='PYTHON', name='python', object=probe.name)
probe.game.sensors['always'].use_pulse_true_level = True
controller = probe.game.controllers['python']
controller.mode = 'MODULE'
controller.module = 'legacy_constraint_runtime_probe.tick'
probe.game.sensors['always'].link(controller)

bpy.ops.wm.save_as_mainfile(filepath=out_range, check_existing=False)
print('LEGACY_CONSTRAINT_TUTORIAL_PROBE_SAVED', out_range)
