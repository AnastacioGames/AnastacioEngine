"""Web smoke test of the game physics (fields, cloth, pins, joint). Gravity is off.

    build-native/bin/AnastacioEngine.exe -b --python tools/tests/web_physics_smoke.py -- --make-scene web_physics.range

Package with tools/web/package-web.py and open in a browser; results go to the console as
"[physics-smoke] PASS|FAIL ..." and a final "[physics-smoke] DONE n checks, m failed".
"""

from __future__ import print_function

import math

END_FRAME = 120
ARM = 3.0


def _grid(name):
    import bmesh
    import bpy

    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=6, y_segments=6, size=4.0)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    return mesh


def _cube(scene, name, location, physics):
    import bpy
    import bmesh

    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    obj.location = location
    scene.objects.link(obj)
    obj.game.physics_type = physics
    if physics == "RIGID_BODY":
        obj.game.mass = 1.0
    return obj


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
        group.add([v.index for v in obj.data.vertices if v.co.y > 1.9], 1.0, "REPLACE")
        soft.pin_group = "Pin"
    return obj


def _field(scene, name, location, rotation, kind, strength):
    import bpy

    obj = bpy.data.objects.new(name, None)
    obj.location = location
    obj.rotation_euler = rotation
    scene.objects.link(obj)
    scene.objects.active = obj
    obj.field.type = kind
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
    scene.game_settings.resolution_x = 640
    scene.game_settings.resolution_y = 360
    scene.game_settings.physics_gravity = 0.0

    camera = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    camera.location = (45.0, -80.0, 10.0)
    camera.rotation_euler = (math.radians(90.0), 0.0, 0.0)
    scene.objects.link(camera)
    scene.camera = camera

    # Rigid body pushed by a point Force field below it.
    _cube(scene, "ForceCube", (0.0, 0.0, 10.0), "RIGID_BODY")
    _field(scene, "ForceField", (0.0, 0.0, 6.0), (0.0, 0.0, 0.0), "FORCE", -10.0)
    # Cloth lifted by Wind, and a pinned cloth hanging in the same kind of wind.
    _cloth(scene, "WindCloth", (30.0, 0.0, 10.0), False)
    _field(scene, "WindA", (30.0, 0.0, 6.0), (0.0, 0.0, 0.0), "WIND", 8.0)
    _cloth(scene, "PinnedCloth", (60.0, 0.0, 10.0), True)
    _field(scene, "WindB", (60.0, 0.0, 6.0), (0.0, 0.0, 0.0), "WIND", 8.0)
    # Hinge pendulum (arm along Y, turns about X), pushed up by a Force field.
    anchor = _cube(scene, "Anchor", (90.0, 0.0, 10.0), "STATIC")
    bob = _cube(scene, "Bob", (90.0, ARM, 10.0), "RIGID_BODY")
    for obj in scene.objects:
        obj.select = False
    anchor.select = True
    bob.select = True
    scene.objects.active = bob
    bpy.ops.object.game_joint_add(pivot_type="HINGE")
    bob.constraints[0].pivot_y = -ARM
    _field(scene, "ForceB", (90.0, ARM, 6.0), (0.0, 0.0, 0.0), "FORCE", -10.0)

    tester = bpy.data.objects.new("Tester", None)
    scene.objects.link(tester)
    scene.objects.active = tester
    text = bpy.data.texts.new("web_physics_smoke.py")
    with open(__file__, "r") as handle:
        text.write(handle.read())
    bpy.ops.logic.sensor_add(type="ALWAYS", object=tester.name)
    sensor = tester.game.sensors[-1]
    sensor.use_pulse_true_level = True
    bpy.ops.logic.controller_add(type="PYTHON", object=tester.name)
    tester.game.controllers[-1].text = text
    sensor.link(tester.game.controllers[-1])
    bpy.ops.wm.save_as_mainfile(filepath=output)


def run_runtime():
    import Range

    tester = Range.logic.getCurrentController().owner
    scene = Range.logic.getCurrentScene()
    frame = tester.get("frame", 0) + 1
    tester["frame"] = frame
    if frame != END_FRAME:
        return

    lines = []

    def check(name, ok, detail):
        lines.append("[physics-smoke] %s %s (%s)" % ("PASS" if ok else "FAIL", name, detail))
        print(lines[-1], flush=True)
        return ok

    objects = scene.objects
    results = []
    dz = objects["ForceCube"].worldPosition.z - 10.0
    results.append(check("Force field pushes the rigid body", abs(dz) > 0.3, "dz %.2f" % dz))
    dz = objects["WindCloth"].worldPosition.z - 10.0
    results.append(check("Wind lifts the cloth", dz > 0.3, "dz %.2f" % dz))
    pinned = objects["PinnedCloth"]
    spread = pinned.cullingBox.max[2] - pinned.cullingBox.min[2]
    results.append(check("Pinned cloth bends away from its pinned edge", spread > 0.5, "z spread %.2f" % spread))
    anchor = objects["Anchor"].worldPosition
    bob = objects["Bob"].worldPosition
    dist = (bob - anchor).length
    results.append(check("Hinge keeps the arm length", abs(dist - ARM) < 0.35, "dist %.2f" % dist))
    results.append(check("Hinge bob moves under the field", abs(bob.z - 10.0) > 0.3, "dz %.2f" % (bob.z - 10.0)))
    lines.append("[physics-smoke] DONE %d checks, %d failed" % (len(results), results.count(False)))
    print(lines[-1], flush=True)
    try:
        with open(Range.logic.expandPath("//web_physics_result.txt"), "w") as handle:
            handle.write("
".join(lines) + "
")
    except Exception as error:
        print("[physics-smoke] could not write the result file: %s" % error, flush=True)


if __name__ == "__main__" and "--make-scene" in __import__("sys").argv:
    arguments = __import__("sys").argv
    make_scene(arguments[arguments.index("--make-scene") + 1])
else:
    run_runtime()
