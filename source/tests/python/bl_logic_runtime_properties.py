"""Regression coverage for typed runtime-property Logic Brick settings.

Run twice:
  RangeEngine --background --factory-startup --python bl_logic_runtime_properties.py -- create file.blend
  RangeEngine --background file.blend --python bl_logic_runtime_properties.py -- verify
"""

import bpy
import sys


def argument_after_separator():
    args = sys.argv
    return args[args.index("--") + 1:] if "--" in args else []


def add_property_bricks(obj):
    bpy.context.scene.objects.active = obj
    obj.select = True

    bpy.ops.logic.sensor_add(type='PROPERTY', object=obj.name)
    sensor = obj.game.sensors[-1]
    sensor.use_runtime_property = True
    sensor.runtime_property = 'LINEAR_VELOCITY'
    sensor.runtime_value = (1.0, 2.0, 3.0)

    bpy.ops.logic.actuator_add(type='PROPERTY', object=obj.name)
    actuator = obj.game.actuators[-1]
    actuator.use_runtime_property = True
    actuator.runtime_property = 'MASS'
    actuator.runtime_value = (2.5, 0.0, 0.0)

    bpy.ops.logic.actuator_add(type='PROPERTY', object=obj.name)
    actuator = obj.game.actuators[-1]
    actuator.use_runtime_property = True
    actuator.runtime_property = 'VISIBLE'
    actuator.runtime_bool_value = False

    for sensor_type in ('NEAR', 'RADAR', 'RAY'):
        bpy.ops.logic.sensor_add(type=sensor_type, object=obj.name)
        sensor = obj.game.sensors[-1]
        sensor.name = 'Debug' + sensor_type.title()
        sensor.use_debug = True


def verify(obj):
    sensor = obj.game.sensors[0]
    assert sensor.use_runtime_property
    assert sensor.runtime_property == 'LINEAR_VELOCITY'
    assert tuple(sensor.runtime_value) == (1.0, 2.0, 3.0)

    mass = obj.game.actuators[0]
    assert mass.use_runtime_property
    assert mass.runtime_property == 'MASS'
    assert mass.runtime_value[0] == 2.5

    visible = obj.game.actuators[1]
    assert visible.runtime_property == 'VISIBLE'
    assert not visible.runtime_bool_value

    for sensor_name in ('DebugNear', 'DebugRadar', 'DebugRay'):
        assert obj.game.sensors[sensor_name].use_debug


args = argument_after_separator()
if not args:
    raise RuntimeError("Expected 'create <blend-path>' or 'verify'")

if args[0] == 'create':
    bpy.ops.mesh.primitive_cube_add()
    cube = bpy.context.object
    cube.name = 'LogicRuntimePropertyRegression'
    add_property_bricks(cube)
    bpy.ops.wm.save_as_mainfile(filepath=args[1])
elif args[0] == 'verify':
    verify(bpy.data.objects['LogicRuntimePropertyRegression'])
else:
    raise RuntimeError("Unknown mode: %s" % args[0])
