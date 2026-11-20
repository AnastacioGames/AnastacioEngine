"""Checks the Game Engine force fields (PFIELD_GAME opt-in): wind, force, range and opt-out.

    build/bin/AnastacioEngine.exe -b --python tools/tests/force_field_test.py -- --make-scene force_field.range
    build/bin/AnastacioRuntime.exe force_field.range

Results are printed with the FORCE_FIELD prefix and written to force_field_test_result.txt next to
the scene. Gravity is off so the only thing that moves a cube is a field.
"""

from __future__ import print_function

import math

END_FRAME = 90


def _cube(scene, name, location):
    import bmesh
    import bpy

    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    obj.location = location
    scene.objects.link(obj)
    obj.game.physics_type = "RIGID_BODY"
    obj.game.mass = 1.0
    obj.game.use_sleep = False
    return obj


def _field(scene, name, location, kind, strength, game, rotation=(0.0, 0.0, 0.0), max_dist=0.0):
    import bpy

    obj = bpy.data.objects.new(name, None)
    obj.location = location
    obj.rotation_euler = rotation
    scene.objects.link(obj)
    scene.objects.active = obj
    obj.field.type = kind
    obj.field.strength = strength
    obj.field.flow = 0.0
    obj.field.use_game_field = game
    if max_dist:
        obj.field.use_max_distance = True
        obj.field.distance_max = max_dist
    return obj


def make_scene(output):
    import bpy

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_GAME"
    scene.game_settings.resolution_x = 320
    scene.game_settings.resolution_y = 180
    scene.game_settings.physics_gravity = 0.0

    camera = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    camera.location = (0.0, -60.0, 10.0)
    scene.objects.link(camera)
    scene.camera = camera

    # Wind blowing along +X (local Z rotated 90 degrees around Y), range 5.
    _field(scene, "WindOn", (0.0, 0.0, 0.0), "WIND", 10.0, True, (0.0, math.radians(90.0), 0.0), 5.0)
    _cube(scene, "InRange", (2.0, 0.0, 0.0))
    _cube(scene, "OutOfRange", (20.0, 0.0, 0.0))
    # Same wind without the opt-in: must do nothing.
    _field(scene, "WindOff", (0.0, 30.0, 0.0), "WIND", 10.0, False, (0.0, math.radians(90.0), 0.0), 5.0)
    _cube(scene, "OptOut", (2.0, 30.0, 0.0))
    # Point force, positive strength pushes away from the field.
    _field(scene, "Repel", (0.0, -30.0, 0.0), "FORCE", 10.0, True, (0.0, 0.0, 0.0), 8.0)
    _cube(scene, "Pushed", (3.0, -30.0, 0.0))

    tester = bpy.data.objects.new("Tester", None)
    scene.objects.link(tester)
    scene.objects.active = tester
    text = bpy.data.texts.new("force_field_test.py")
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
    results.append("FORCE_FIELD: %s %s (%s)" % ("PASS" if ok else "FAIL", name, detail))


def run_runtime():
    import Range

    tester = Range.logic.getCurrentController().owner
    objects = Range.logic.getCurrentScene().objects
    frame = tester.get("frame", 0) + 1
    tester["frame"] = frame
    results = tester.get("results")
    if results is None:
        results = tester["results"] = []

    if frame == 1:
        tester["start"] = {n: list(objects[n].worldPosition) for n in ("InRange", "OutOfRange", "OptOut", "Pushed")}

    if frame == END_FRAME:
        def moved(name):
            now = objects[name].worldPosition
            return [now[i] - tester["start"][name][i] for i in range(3)]

        d = moved("InRange")
        _check(results, "wind pushes along +X", d[0] > 1.0 and abs(d[1]) < 0.1 and abs(d[2]) < 0.1,
               "moved %.2f %.2f %.2f" % tuple(d))
        d = moved("OutOfRange")
        _check(results, "wind respects max distance", max(abs(v) for v in d) < 0.05, "moved %.3f" % max(abs(v) for v in d))
        d = moved("OptOut")
        _check(results, "field without opt-in does nothing", max(abs(v) for v in d) < 0.05, "moved %.3f" % max(abs(v) for v in d))
        d = moved("Pushed")
        _check(results, "force repels from the field", d[0] > 1.0 and abs(d[1]) < 0.1, "moved %.2f %.2f %.2f" % tuple(d))
        failed = [line for line in results if " FAIL " in line]
        results.append("FORCE_FIELD: %d checks, %d failed" % (len(results), len(failed)))
        for line in results:
            print(line, flush=True)
        with open(Range.logic.expandPath("//force_field_test_result.txt"), "w") as handle:
            handle.write("\n".join(results) + "\n")
        Range.logic.endGame()


if __name__ == "__main__" and "--make-scene" in __import__("sys").argv:
    arguments = __import__("sys").argv
    make_scene(arguments[arguments.index("--make-scene") + 1])
else:
    run_runtime()
