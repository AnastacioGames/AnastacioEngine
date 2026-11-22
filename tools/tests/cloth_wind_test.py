"""Checks the Wind field on a Game Cloth (Bullet aero model, V_TwoSided).

    build/bin/AnastacioEngine.exe -b --python tools/tests/cloth_wind_test.py -- --make-scene cloth_wind.range
    build/bin/AnastacioRuntime.exe cloth_wind.range

Results use the CLOTHWIND prefix and go to cloth_wind_test_result.txt next to the scene.
Gravity is off. Three flat sheets (normal +Z): one under a wind blowing up, one under a wind
blowing down (the same sheet hit from the other face) and one outside any field.
"""

from __future__ import print_function

import math

END_FRAME = 90


def _grid(name, size=4.0, cuts=6):
    import bmesh
    import bpy

    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=cuts, y_segments=cuts, size=size)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    return mesh


def _cloth(scene, name, location):
    import bpy

    obj = bpy.data.objects.new(name, _grid(name))
    obj.location = location
    scene.objects.link(obj)
    obj.game.physics_type = "SOFT_BODY"
    obj.game.mass = 1.0
    obj.game.soft_body.use_cloth = True
    return obj


def _wind(scene, name, location, rotation, strength):
    import bpy

    obj = bpy.data.objects.new(name, None)
    obj.location = location
    obj.rotation_euler = rotation
    scene.objects.link(obj)
    scene.objects.active = obj
    obj.field.type = "WIND"
    obj.field.strength = strength
    obj.field.flow = 0.0
    obj.field.use_game_field = True
    obj.field.use_max_distance = True
    obj.field.distance_max = 8.0


def make_scene(output):
    import bpy

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_GAME"
    scene.game_settings.resolution_x = 320
    scene.game_settings.resolution_y = 180
    scene.game_settings.physics_gravity = 0.0

    camera = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    camera.location = (30.0, -60.0, 10.0)
    camera.rotation_euler = (math.radians(90.0), 0.0, 0.0)
    scene.objects.link(camera)
    scene.camera = camera

    _cloth(scene, "Up", (0.0, 0.0, 10.0))
    _cloth(scene, "Down", (30.0, 0.0, 10.0))
    _cloth(scene, "Calm", (60.0, 0.0, 10.0))
    _wind(scene, "WindUp", (0.0, 0.0, 6.0), (0.0, 0.0, 0.0), 8.0)
    _wind(scene, "WindDown", (30.0, 0.0, 14.0), (math.radians(180.0), 0.0, 0.0), 8.0)
    # A point Force below a sheet repels it (the Force field acts on soft bodies too).
    _cloth(scene, "Repelled", (90.0, 0.0, 10.0))
    _wind(scene, "Repel", (90.0, 0.0, 6.0), (0.0, 0.0, 0.0), 8.0)
    scene.objects["Repel"].field.type = "FORCE"

    tester = bpy.data.objects.new("Tester", None)
    scene.objects.link(tester)
    scene.objects.active = tester
    text = bpy.data.texts.new("cloth_wind_test.py")
    with open(__file__, "r") as handle:
        text.write(handle.read())
    bpy.ops.logic.sensor_add(type="ALWAYS", object=tester.name)
    sensor = tester.game.sensors[-1]
    sensor.use_pulse_true_level = True
    bpy.ops.logic.controller_add(type="PYTHON", object=tester.name)
    tester.game.controllers[-1].text = text
    sensor.link(tester.game.controllers[-1])
    bpy.ops.wm.save_as_mainfile(filepath=output)


def _check(results, name, ok, detail):
    results.append("CLOTHWIND: %s %s (%s)" % ("PASS" if ok else "FAIL", name, detail))


def run_runtime():
    import Range

    tester = Range.logic.getCurrentController().owner
    scene = Range.logic.getCurrentScene()
    frame = tester.get("frame", 0) + 1
    tester["frame"] = frame
    results = tester.get("results")
    if results is None:
        results = tester["results"] = []

    if frame == END_FRAME:
        up = scene.objects["Up"].worldPosition.z - 10.0
        down = scene.objects["Down"].worldPosition.z - 10.0
        calm = scene.objects["Calm"].worldPosition.z - 10.0
        _check(results, "wind pushes the sheet along its direction", up > 0.3, "dz %.2f" % up)
        _check(results, "wind hits the other face of the sheet too", down < -0.3, "dz %.2f" % down)
        _check(results, "sheet outside the field stays put", abs(calm) < 0.1, "dz %.2f" % calm)
        repelled = scene.objects["Repelled"].worldPosition.z - 10.0
        _check(results, "force field pushes the sheet away from it", repelled > 0.3, "dz %.2f" % repelled)
        failed = [line for line in results if " FAIL " in line]
        results.append("CLOTHWIND: %d checks, %d failed" % (len(results), len(failed)))
        for line in results:
            print(line)
        with open(Range.logic.expandPath("//cloth_wind_test_result.txt"), "w") as handle:
            handle.write("\n".join(results) + "\n")
        Range.logic.endGame()


if __name__ == "__main__" and "--make-scene" in __import__("sys").argv:
    arguments = __import__("sys").argv
    make_scene(arguments[arguments.index("--make-scene") + 1])
else:
    run_runtime()
