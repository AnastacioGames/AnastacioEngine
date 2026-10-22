import bpy, sys
out = sys.argv[sys.argv.index('--')+1]
sc = bpy.context.scene
for o in bpy.data.objects:
    for c in list(o.game.controllers): pass
    while o.game.sensors: 
        bpy.context.scene.objects.active = o
        bpy.ops.logic.sensor_remove(sensor=o.game.sensors[0].name, object=o.name)
    while o.game.controllers:
        bpy.ops.logic.controller_remove(controller=o.game.controllers[0].name, object=o.name)
    while o.game.actuators:
        bpy.ops.logic.actuator_remove(actuator=o.game.actuators[0].name, object=o.name)
    try:
        while len(o.game.components): o.game.components.remove(0)
    except Exception as e: print("comp", e)
import os
src = sys.argv[sys.argv.index('--')+2]
mod = os.path.splitext(os.path.basename(src))[0]
txt = bpy.data.texts.new(mod + ".py")
txt.from_string(open(sys.argv[sys.argv.index('--')+2]).read())
e = bpy.data.objects.new("tester", None); sc.objects.link(e); sc.objects.active = e
bpy.ops.logic.sensor_add(type='ALWAYS', object=e.name)
e.game.sensors[-1].use_pulse_true_level = True
bpy.ops.logic.controller_add(type='PYTHON', object=e.name)
c = e.game.controllers[-1]; c.mode='MODULE'; c.module=mod + '.tick'
c.link(sensor=e.game.sensors[-1])
bpy.ops.wm.save_as_mainfile(filepath=out, copy=True)
print("SAVED", out)
