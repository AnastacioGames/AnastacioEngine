"""Checks the game Cloth preset and the vertex group pins.

    build/bin/AnastacioEngine.exe -b --python tools/tests/cloth_pin_test.py -- --make-scene cloth_pin.range
    build/bin/AnastacioRuntime.exe cloth_pin.range

Results use the CLOTH prefix and go to cloth_pin_test_result.txt next to the scene.
"""

from __future__ import print_function

import math

END_FRAME = 100


def _grid(name, size=4.0, cuts=8):
    import bmesh
    import bpy

    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=cuts, y_segments=cuts, size=size)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    return mesh


def _cloth(scene, name, location, pinned):
    import bpy

    obj = bpy.data.objects.new(name, _grid(name))
    obj.location = location
    scene.objects.link(obj)
    obj.game.physics_type = "SOFT_BODY"
    obj.game.mass = 1.0
    soft = obj.game.soft_body
    soft.use_cloth = True
    if pinned:
        group = obj.vertex_groups.new("Pin")
        top = [v.index for v in obj.data.vertices if v.co.y > 1.9]
        group.add(top, 1.0, "REPLACE")
        soft.pin_group = "Pin"
    return obj


def make_scene(output):
    import bpy

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_GAME"
    scene.game_settings.resolution_x = 320
    scene.game_settings.resolution_y = 180

    camera = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    camera.location = (0.0, -30.0, 10.0)
    camera.rotation_euler = (math.radians(90.0), 0.0, 0.0)
    scene.objects.link(camera)
    scene.camera = camera

    _cloth(scene, "Pinned", (-5.0, 0.0, 10.0), True)
    _cloth(scene, "Free", (5.0, 0.0, 10.0), False)
    preset = _cloth(scene, "Preset", (0.0, 10.0, 10.0), False)
    preset.game.physics_type = "STATIC"  # only reads RNA at generation time
    assert preset.game.soft_body.use_cloth

    tester = bpy.data.objects.new("Tester", None)
    scene.objects.link(tester)
    scene.objects.active = tester
    text = bpy.data.texts.new("cloth_pin_test.py")
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
    results.append("CLOTH: %s %s (%s)" % ("PASS" if ok else "FAIL", name, detail))


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
        pinned = scene.objects["Pinned"]
        free = scene.objects["Free"]
        # The culling box is in object space: a hanging sheet spreads along Z, a falling flat one does not.
        spread_pinned = pinned.cullingBox.max[2] - pinned.cullingBox.min[2]
        spread_free = free.cullingBox.max[2] - free.cullingBox.min[2]
        _check(results, "unpinned cloth falls", free.worldPosition.z < 9.0, "z %.2f" % free.worldPosition.z)
        _check(results, "pinned cloth held above the free one", pinned.worldPosition.z - free.worldPosition.z > 0.5,
               "pinned z %.2f free z %.2f" % (pinned.worldPosition.z, free.worldPosition.z))
        _check(results, "pinned cloth hangs from its edge", spread_pinned > 1.5 and spread_free < 0.5,
               "z spread pinned %.2f free %.2f" % (spread_pinned, spread_free))
        failed = [line for line in results if " FAIL " in line]
        results.append("CLOTH: %d checks, %d failed" % (len(results), len(failed)))
        for line in results:
            print(line)
        with open(Range.logic.expandPath("//cloth_pin_test_result.txt"), "w") as handle:
            handle.write("\n".join(results) + "\n")
        Range.logic.endGame()


if __name__ == "__main__" and "--make-scene" in __import__("sys").argv:
    arguments = __import__("sys").argv
    make_scene(arguments[arguments.index("--make-scene") + 1])
else:
    run_runtime()
