"""Checks the Game Rigid Body Joint panel operator (object.game_joint_add) end to end.

    build/bin/AnastacioEngine.exe -b --python tools/tests/game_joint_test.py -- --make-scene game_joint.range
    build/bin/AnastacioRuntime.exe game_joint.range

Results use the JOINT prefix and go to game_joint_test_result.txt next to the scene.
Each pendulum hangs from a static anchor by a joint made with the operator (ball, hinge,
cone twist, 6DoF) and is dropped sideways; the pivot is the anchor centre, so the arm
length must stay constant while the body falls.
"""

from __future__ import print_function

import math

END_FRAME = 90
ARM = 3.0
KINDS = ("BALL", "HINGE", "CONE_TWIST", "GENERIC_6_DOF")


def _box(scene, name, location, size):
    import bpy
    import bmesh

    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=size)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    obj.location = location
    scene.objects.link(obj)
    return obj


def make_scene(output):
    import bpy

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_GAME"
    scene.game_settings.resolution_x = 320
    scene.game_settings.resolution_y = 180

    camera = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    camera.location = (45.0, -60.0, 10.0)
    camera.rotation_euler = (math.radians(90.0), 0.0, 0.0)
    scene.objects.link(camera)
    scene.camera = camera

    for index, kind in enumerate(KINDS):
        x = index * 30.0
        anchor = _box(scene, "Anchor" + kind, (x, 0.0, 10.0), 1.0)
        anchor.game.physics_type = "STATIC"
        # The hinge turns around X, so its arm must lie along Y to be able to swing.
        along_y = kind == "HINGE"
        bob = _box(scene, "Bob" + kind, (x, ARM, 10.0) if along_y else (x + ARM, 0.0, 10.0), 1.0)
        bob.game.physics_type = "RIGID_BODY"
        bob.game.mass = 1.0
        for obj in scene.objects:
            obj.select = False
        anchor.select = True
        bob.select = True
        scene.objects.active = bob
        bpy.ops.object.game_joint_add(pivot_type=kind)
        joint = bob.constraints[0]
        if along_y:
            joint.pivot_y = -ARM
        else:
            joint.pivot_x = -ARM
        if kind == "CONE_TWIST":
            for axis in "xyz":
                setattr(joint, "use_angular_limit_" + axis, True)
                setattr(joint, "limit_angle_max_" + axis, 1.5)
        elif kind == "GENERIC_6_DOF":
            # Position locked to the pivot, rotation free.
            for axis in "xyz":
                setattr(joint, "use_limit_" + axis, True)
                setattr(joint, "limit_min_" + axis, 0.0)
                setattr(joint, "limit_max_" + axis, 0.0)

    tester = bpy.data.objects.new("Tester", None)
    scene.objects.link(tester)
    scene.objects.active = tester
    text = bpy.data.texts.new("game_joint_test.py")
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
    results.append("JOINT: %s %s (%s)" % ("PASS" if ok else "FAIL", name, detail))


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
        for kind in KINDS:
            anchor = scene.objects["Anchor" + kind].worldPosition
            bob = scene.objects["Bob" + kind].worldPosition
            dist = (bob - anchor).length
            _check(results, kind + " arm length is kept", abs(dist - ARM) < 0.35, "dist %.2f" % dist)
            _check(results, kind + " bob falls", bob.z < anchor.z - 0.5, "dz %.2f" % (bob.z - anchor.z))
        failed = [line for line in results if " FAIL " in line]
        results.append("JOINT: %d checks, %d failed" % (len(results), len(failed)))
        for line in results:
            print(line)
        with open(Range.logic.expandPath("//game_joint_test_result.txt"), "w") as handle:
            handle.write("\n".join(results) + "\n")
        Range.logic.endGame()


if __name__ == "__main__" and "--make-scene" in __import__("sys").argv:
    arguments = __import__("sys").argv
    make_scene(arguments[arguments.index("--make-scene") + 1])
else:
    run_runtime()
