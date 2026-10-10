"""Checks the game soft body fixes (scale, spawn, teleport, velocity, suspend, deformer).

    build/bin/AnastacioEngine.exe -b --python tools/tests/soft_body_test.py -- --make-scene soft_body.range
    build/bin/AnastacioRuntime.exe soft_body.range

Results are printed with the SOFT_BODY prefix and written to
soft_body_test_result.txt next to the scene.
"""

from __future__ import print_function

import math

END_FRAME = 150


def _cube_mesh(name, cuts=2):
    """Subdivided cube (+-1): interior vertices expose a wrong vertex -> node mapping."""
    import bmesh
    import bpy

    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=2.0)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=cuts, use_grid_fill=True)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    return mesh


def _grid_mesh(name, size=2.0, cuts=8):
    import bmesh
    import bpy

    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=cuts, y_segments=cuts, size=size)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    return mesh


def _object(scene, name, mesh, location, scale=1.0):
    import bpy

    obj = bpy.data.objects.new(name, mesh)
    obj.location = location
    obj.scale = (scale, scale, scale)
    scene.objects.link(obj)
    return obj


def _soft(obj, shape_match=True, mass=1.0):
    obj.game.physics_type = "SOFT_BODY"
    obj.game.mass = mass
    soft = obj.game.soft_body
    if soft is not None:
        soft.use_shape_match = shape_match
        soft.linear_stiffness = 0.9
    return obj


def make_scene(output):
    import bpy

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_GAME"
    scene.game_settings.resolution_x = 640
    scene.game_settings.resolution_y = 360

    camera = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    camera.location = (0.0, -50.0, 32.0)
    camera.rotation_euler = (math.radians(58.0), 0.0, 0.0)
    scene.objects.link(camera)
    scene.camera = camera

    floor = _object(scene, "Floor", _grid_mesh("Floor", size=40.0, cuts=2), (0.0, 0.0, 0.0))
    floor.game.physics_type = "STATIC"

    # Non uniform scale on a triangle mesh soft body: the rendered vertices must span +-1 in local
    # space (a mapping made with unscaled positions shrinks the x extent to ~1/3).
    scaled = _soft(_object(scene, "Scaled", _cube_mesh("Scaled"), (-8.0, 0.0, 6.0)))
    scaled.scale = (3.0, 1.0, 1.0)

    # Convex hull bounds with scale 2: the body must rest with its top near z = 4.
    hull = _soft(_object(scene, "Hull", _cube_mesh("Hull"), (-3.0, 0.0, 2.2), scale=2.0))
    hull.game.use_collision_bounds = True
    hull.game.collision_bounds_type = "CONVEX_HULL"

    # Spawned from a hidden layer far from the origin: must appear at the spawner.
    proto = _soft(_object(scene, "Proto", _cube_mesh("Proto"), (20.0, 0.0, 7.0)))
    proto.layers = [False, True] + [False] * 18
    spawner = bpy.data.objects.new("Spawner", None)
    spawner.location = (3.0, 0.0, 4.0)
    spawner.rotation_euler = (0.0, 0.0, math.radians(90.0))
    scene.objects.link(spawner)

    _soft(_object(scene, "Teleport", _cube_mesh("Teleport"), (8.0, 0.0, 1.2)))
    _soft(_object(scene, "Velocity", _cube_mesh("Velocity"), (13.0, 0.0, 1.2)))
    _soft(_object(scene, "Frozen", _cube_mesh("Frozen"), (-13.0, 0.0, 6.0)))

    # Modifier + vertex group used to select another deformer: the soft body must still deform.
    post = _object(scene, "Post", _cube_mesh("Post", cuts=0), (0.0, -8.0, 0.5), scale=0.5)
    post.game.physics_type = "STATIC"
    post.game.use_collision_bounds = True
    post.game.collision_bounds_type = "BOX"
    draped = _soft(_object(scene, "Draped", _grid_mesh("Draped"), (0.0, -8.0, 2.5)), shape_match=False)
    draped.modifiers.new("Subsurf", "SUBSURF")
    group = draped.vertex_groups.new("Pin")
    group.add([0], 1.0, "REPLACE")
    # Same setup without modifier: tells a deformer problem from a setup problem.
    post = _object(scene, "PostPlain", _cube_mesh("PostPlain", cuts=0), (6.0, -8.0, 0.5), scale=0.5)
    post.game.physics_type = "STATIC"
    post.game.use_collision_bounds = True
    post.game.collision_bounds_type = "BOX"
    _soft(_object(scene, "DrapedPlain", _grid_mesh("DrapedPlain"), (6.0, -8.0, 2.5)), shape_match=False)

    # Second material without physics: its vertices have no soft body node.
    two_mat = _soft(_object(scene, "TwoMat", _cube_mesh("TwoMat"), (-18.0, 0.0, 3.0)))
    solid = bpy.data.materials.new("Solid")
    ghost = bpy.data.materials.new("NoPhysics")
    ghost.game_settings.physics = False
    two_mat.data.materials.append(solid)
    two_mat.data.materials.append(ghost)
    for index, polygon in enumerate(two_mat.data.polygons):
        polygon.material_index = 1 if index % 3 == 0 else 0

    tester = bpy.data.objects.new("Tester", None)
    scene.objects.link(tester)
    scene.objects.active = tester
    text = bpy.data.texts.new("soft_body_test.py")
    with open(__file__, "r") as handle:
        text.write(handle.read())
    bpy.ops.logic.sensor_add(type="ALWAYS", object=tester.name)
    sensor = tester.game.sensors[-1]
    sensor.use_pulse_true_level = True
    bpy.ops.logic.controller_add(type="PYTHON", object=tester.name)
    tester.game.controllers[-1].text = text
    sensor.link(tester.game.controllers[-1])

    bpy.ops.wm.save_as_mainfile(filepath=output)


def _extent(obj):
    box = obj.cullingBox
    return [box.max[i] - box.min[i] for i in range(3)]


def _ray_top(tester, x, y):
    hit, point, _normal = tester.rayCast((x, y, -1.0), (x, y, 20.0), 0.0)
    return hit, point


def _check(results, name, ok, detail):
    results.append("SOFT_BODY: %s %s (%s)" % ("PASS" if ok else "FAIL", name, detail))


def run_runtime():
    import Range

    tester = Range.logic.getCurrentController().owner
    scene = Range.logic.getCurrentScene()
    objects = scene.objects
    frame = tester.get("frame", 0) + 1
    tester["frame"] = frame
    results = tester.get("results")
    if results is None:
        results = tester["results"] = []

    if frame == 1:
        spawned = scene.addObject("Proto", "Spawner")
        spawned.name  # keep reference alive
        tester["spawned"] = spawned
        frozen = objects["Frozen"]
        frozen.suspendDynamics()
        tester["frozen_z"] = frozen.worldPosition.z
        velocity = objects["Velocity"]
        velocity.mass = 3.0
        velocity.friction = 0.4

    if frame == 3:
        spawned = tester["spawned"]
        pos = spawned.worldPosition
        _check(results, "spawn position", abs(pos.x - 3.0) < 0.5 and abs(pos.y) < 0.5,
               "pos %.2f %.2f %.2f, expected near 3 0" % (pos.x, pos.y, pos.z))
        hit, point = _ray_top(tester, 3.0, 0.0)
        _check(results, "spawn nodes at spawner", hit is not None and hit.name == "Proto",
               "ray hit %s" % (hit.name if hit else None))
        velocity = objects["Velocity"]
        _check(results, "soft mass", abs(velocity.mass - 3.0) < 1e-3, "mass %.3f" % velocity.mass)
        _check(results, "soft friction", abs(velocity.friction - 0.4) < 1e-3, "friction %.3f" % velocity.friction)

    if frame == 10:
        ext = _extent(objects["Scaled"])
        _check(results, "scaled mapping", min(ext) > 1.6,
               "local extent %.2f %.2f %.2f, expected ~2" % tuple(ext))

    if frame == 20:
        frozen = objects["Frozen"]
        drop = tester["frozen_z"] - frozen.worldPosition.z
        _check(results, "suspend freezes", abs(drop) < 0.05, "moved %.3f" % drop)
        frozen.restoreDynamics()

    if frame == 45:
        objects["Teleport"].worldPosition = (8.0, 6.0, 3.0)

    if frame == 47:
        teleport = objects["Teleport"]
        pos = teleport.worldPosition
        _check(results, "teleport position", abs(pos.x - 8.0) < 0.5 and abs(pos.y - 6.0) < 0.5,
               "pos %.2f %.2f %.2f" % (pos.x, pos.y, pos.z))
        hit, point = _ray_top(tester, 8.0, 6.0)
        _check(results, "teleport nodes", hit is not None and hit.name == "Teleport",
               "ray hit %s" % (hit.name if hit else None))
        tester["teleport_pos"] = list(pos)
        teleport.worldOrientation = (0.0, 0.0, math.radians(45.0))

    if frame == 49:
        pos = objects["Teleport"].worldPosition
        before = tester["teleport_pos"]
        dist = math.sqrt((pos.x - before[0]) ** 2 + (pos.y - before[1]) ** 2)
        _check(results, "orientation keeps position", dist < 0.5, "moved %.3f" % dist)

    if frame == 60:
        frozen = objects["Frozen"]
        _check(results, "restore falls", frozen.worldPosition.z < tester["frozen_z"] - 0.5,
               "z %.2f" % frozen.worldPosition.z)
        velocity = objects["Velocity"]
        velocity.setLinearVelocity((0.0, 0.0, 5.0))

    if frame == 61:
        vel = objects["Velocity"].getLinearVelocity()
        _check(results, "linear velocity", vel.z > 2.0, "vz %.2f" % vel.z)
        objects["Velocity"].setAngularVelocity((0.0, 0.0, 3.0))

    if frame == 62:
        ang = objects["Velocity"].getAngularVelocity()
        _check(results, "angular velocity", ang.z > 1.5, "wz %.2f" % ang.z)

    if frame == 100:
        hit, point = _ray_top(tester, -3.0, 0.0)
        top = point.z if hit else 0.0
        _check(results, "convex hull scale", hit is not None and hit.name == "Hull" and top > 3.0,
               "top %.2f, expected ~4" % top)
        for name in ("Draped", "DrapedPlain"):
            obj = objects[name]
            ext = _extent(obj)
            _check(results, name + " deforms", ext[2] > 0.3, "z extent %.2f, pos %.2f %.2f %.2f"
                   % (ext[2], obj.worldPosition.x, obj.worldPosition.y, obj.worldPosition.z))
        ext = _extent(objects["TwoMat"])
        _check(results, "non physics material", all(0.5 < e < 5.0 for e in ext),
               "extent %.2f %.2f %.2f" % tuple(ext))

    if frame == END_FRAME:
        failed = [line for line in results if " FAIL " in line]
        results.append("SOFT_BODY: %d checks, %d failed" % (len(results), len(failed)))
        for line in results:
            print(line, flush=True)
        with open(Range.logic.expandPath("//soft_body_test_result.txt"), "w") as handle:
            handle.write("\n".join(results) + "\n")
        Range.logic.endGame()


if __name__ == "__main__" and "--make-scene" in __import__("sys").argv:
    arguments = __import__("sys").argv
    make_scene(arguments[arguments.index("--make-scene") + 1])
else:
    run_runtime()
