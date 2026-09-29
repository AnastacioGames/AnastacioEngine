"""Checks that bone constraints give the same result in the game as in the editor.

Correctness (compares each bone's pose matrix, frame by frame, with the
editor's evaluation, saved next to the scene as bone_constraint_reference.json):

    build/bin/RangeEngine.exe -b --python tools/tests/bone_constraint_test.py -- --make-scene bone_constraints.range
    build/bin/RangeRuntime.exe bone_constraints.range

IK cost (N rigs with a 10-bone IK chain each; run plugged in, dedicated GPU,
and compare LEGACY with ITASC):

    build/bin/RangeEngine.exe -b --python tools/tests/bone_constraint_test.py -- --make-perf-scene ik_perf.range 20 LEGACY
    build/bin/RangeRuntime.exe ik_perf.range

Results are printed with the BONE_CONSTRAINT prefix and written to
bone_constraint_test_result.txt (IK_PERF / ik_perf_result.txt for the perf scene).
"""

from __future__ import print_function

import json
import math

FRAMES = 60
TOLERANCE = 1e-3
PERF_FRAMES = 300
REFERENCE = "bone_constraint_reference.json"

# (bone name, constraint type, expected in game). Types missing from the list
# in BL_ArmatureObject::LoadConstraints keep a stale target: CHILD_OF is the
# control for that. LIMIT_ROTATION has no target and should always match.
CASES = (
    ("CopyLoc", "COPY_LOCATION", True),
    ("CopyRot", "COPY_ROTATION", True),
    ("CopyScale", "COPY_SCALE", True),
    ("CopyTrans", "COPY_TRANSFORMS", True),
    ("TrackTo", "TRACK_TO", True),
    ("DampedTrack", "DAMPED_TRACK", True),
    ("LockedTrack", "LOCKED_TRACK", True),
    ("StretchTo", "STRETCH_TO", True),
    ("Floor", "FLOOR", True),
    ("Transform", "TRANSFORM", True),
    ("LimitDist", "LIMIT_DISTANCE", True),
    ("ChildOf", "CHILD_OF", False),
    ("LimitRot", "LIMIT_ROTATION", True),
)
IK_BONES = ("IK_1", "IK_2", "IK_3")


def target_transform(frame):
    """Deterministic target motion shared by the editor pass and the game."""
    location = (2.0 * math.sin(frame * 0.10),
                2.0 * math.cos(frame * 0.13),
                1.0 + 0.5 * math.sin(frame * 0.07))
    rotation = (frame * 0.05, 0.0, frame * 0.03)
    scale = 1.0 + 0.3 * math.sin(frame * 0.09)
    return location, rotation, (scale, scale, scale)


def _new_rig(scene, name, location):
    import bpy

    rig = bpy.data.objects.new(name, bpy.data.armatures.new(name))
    rig.location = location
    scene.objects.link(rig)
    scene.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    return rig


def _add_skin(scene, rig, bone_name):
    """A skinned mesh makes the game apply the pose every rendered frame."""
    import bpy

    mesh = bpy.data.meshes.new(rig.name + "_skin")
    mesh.from_pydata([(0, 0, 0), (0.1, 0, 0), (0, 0.1, 0)], [], [(0, 1, 2)])
    skin = bpy.data.objects.new(rig.name + "_skin", mesh)
    scene.objects.link(skin)
    skin.parent = rig
    skin.parent_type = "ARMATURE"
    group = skin.vertex_groups.new(bone_name)
    group.add([0, 1, 2], 1.0, "REPLACE")
    skin.modifiers.new("Armature", "ARMATURE").object = rig
    skin.game.physics_type = "NO_COLLISION"


def _add_controller(scene, obj, text):
    import bpy

    scene.objects.active = obj
    bpy.ops.logic.sensor_add(type="ALWAYS", object=obj.name)
    sensor = obj.game.sensors[-1]
    sensor.use_pulse_true_level = True
    bpy.ops.logic.controller_add(type="PYTHON", object=obj.name)
    obj.game.controllers[-1].text = text
    sensor.link(obj.game.controllers[-1])


def _new_scene():
    import bpy

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_GAME"
    scene.game_settings.resolution_x = 640
    scene.game_settings.resolution_y = 360
    # Armatures only re-pose while a child mesh is visible (anim_needs_update).
    camera = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    camera.location = (0.0, -30.0, 10.0)
    camera.rotation_euler = (math.radians(72.0), 0.0, 0.0)
    scene.objects.link(camera)
    scene.camera = camera
    return scene


def _script_text():
    import bpy

    text = bpy.data.texts.new("bone_constraint_test.py")
    with open(__file__, "r") as handle:
        text.write(handle.read())
    return text


def make_scene(output):
    import bpy

    scene = _new_scene()
    target = bpy.data.objects.new("Target", None)
    scene.objects.link(target)

    # Same rig twice: "Rig" calls update() every tick, "RigNoUpdate" never does,
    # to show whether the pose follows a moving target without an action playing.
    rigs = []
    for rig_name in ("Rig", "RigNoUpdate"):
        rig = _new_rig(scene, rig_name, (0.0, 0.0, 0.0))
        bones = rig.data.edit_bones
        for index, (bone_name, _type, _expected) in enumerate(CASES):
            bone = bones.new(bone_name)
            bone.head = (index * 1.5 - 9.0, 4.0, 0.0)
            bone.tail = (index * 1.5 - 9.0, 4.0, 1.0)
        parent = None
        for index, bone_name in enumerate(IK_BONES):
            bone = bones.new(bone_name)
            bone.head = (0.0, -4.0, float(index))
            bone.tail = (0.0, -4.0, float(index + 1))
            bone.parent = parent
            bone.use_connect = parent is not None
            parent = bone
        bpy.ops.object.mode_set(mode="POSE")
        for bone_name, constraint_type, _expected in CASES:
            constraint = rig.pose.bones[bone_name].constraints.new(constraint_type)
            if constraint_type != "LIMIT_ROTATION":
                constraint.target = target
            else:
                constraint.use_limit_x = True
                constraint.max_x = 0.3
                rig.pose.bones[bone_name].rotation_mode = "XYZ"
                rig.pose.bones[bone_name].rotation_euler = (0.8, 0.0, 0.0)
            if constraint_type == "TRACK_TO":
                constraint.track_axis = "TRACK_Y"
                constraint.up_axis = "UP_Z"
        ik = rig.pose.bones[IK_BONES[-1]].constraints.new("IK")
        ik.target = target
        ik.chain_count = len(IK_BONES)
        bpy.ops.object.mode_set(mode="OBJECT")
        _add_skin(scene, rig, CASES[0][0])
        rigs.append(rig)

    # Editor reference: pose matrices after each target position.
    names = [case[0] for case in CASES] + list(IK_BONES)
    reference = []
    for frame in range(FRAMES):
        target.location, target.rotation_euler, target.scale = target_transform(frame)
        scene.update()
        reference.append({name: [list(row) for row in rigs[0].pose.bones[name].matrix]
                          for name in names})
    target.location, target.rotation_euler, target.scale = target_transform(0)
    import os
    with open(os.path.join(os.path.dirname(os.path.abspath(output)), REFERENCE), "w") as handle:
        json.dump(reference, handle)

    _add_controller(scene, target, _script_text())
    bpy.ops.wm.save_as_mainfile(filepath=output)
    print("BONE_CONSTRAINT_SCENE: SAVED %s" % output)


def make_perf_scene(output, rig_count, solver):
    import bpy

    scene = _new_scene()
    target = bpy.data.objects.new("Target", None)
    scene.objects.link(target)
    for rig_index in range(rig_count):
        rig = _new_rig(scene, "IKRig%d" % rig_index,
                       ((rig_index % 5) * 3.0 - 6.0, (rig_index // 5) * 3.0, 0.0))
        parent = None
        for index in range(10):
            bone = rig.data.edit_bones.new("B%d" % index)
            bone.head = (0.0, 0.0, index * 0.3)
            bone.tail = (0.0, 0.0, (index + 1) * 0.3)
            bone.parent = parent
            bone.use_connect = parent is not None
            parent = bone
        bpy.ops.object.mode_set(mode="POSE")
        rig.pose.ik_solver = solver
        ik = rig.pose.bones["B9"].constraints.new("IK")
        ik.target = target
        ik.chain_count = 10
        bpy.ops.object.mode_set(mode="OBJECT")
        _add_skin(scene, rig, "B9")

    _add_controller(scene, target, _script_text())
    bpy.ops.wm.save_as_mainfile(filepath=output)
    print("IK_PERF_SCENE: SAVED %s (%d rigs, %s)" % (output, rig_count, solver))


def _move_target(Range, target, frame):
    from mathutils import Euler

    location, rotation, scale = target_transform(frame)
    target.worldPosition = location
    target.worldOrientation = Euler(rotation).to_matrix()
    target.worldScale = scale


def _finish(Range, path, lines):
    with open(path, "w") as handle:
        handle.write("\n".join(lines) + "\n")
    Range.logic.endGame()


def run_runtime():
    import Range

    target = Range.logic.getCurrentController().owner
    scene = Range.logic.getCurrentScene()
    if "IKRig0" in scene.objects:
        run_perf(Range, target)
        return
    rig = scene.objects["Rig"]
    rig_stale = scene.objects["RigNoUpdate"]
    frame = target.get("frame", 0)

    # The pose read now was applied at the end of the previous tick, after the
    # target moved to frame - 1.
    if frame > 0:
        if "reference" not in target:
            with open(Range.logic.expandPath("//" + REFERENCE), "r") as handle:
                target["reference"] = json.load(handle)
        reference = target["reference"][frame - 1]
        errors = target.get("errors") or {}
        for label, armature in (("", rig), ("stale:", rig_stale)):
            channels = {channel.name: channel for channel in armature.channels}
            for name, expected in reference.items():
                got = channels[name].pose_matrix
                error = max(abs(got[row][col] - expected[row][col])
                            for row in range(4) for col in range(4))
                key = label + name
                errors[key] = max(errors.get(key, 0.0), error)
        target["errors"] = errors

    if frame >= FRAMES:
        report(Range, target["errors"])
        return
    _move_target(Range, target, frame)
    rig.update()
    target["frame"] = frame + 1


def report(Range, errors):
    lines = []
    failures = 0
    expected = {case[0]: case for case in CASES}
    for name in [case[0] for case in CASES] + list(IK_BONES):
        constraint_type, should_pass = (expected[name][1], expected[name][2]) \
            if name in expected else ("IK", True)
        error = errors[name]
        passed = error < TOLERANCE
        status = "PASS" if passed else "FAIL"
        if passed != should_pass:
            status += " (unexpected)"
            failures += 1
        stale = errors["stale:" + name]
        lines.append("BONE_CONSTRAINT: %-16s %-12s %-18s max_err=%.6f without_update=%.6f"
                     % (constraint_type, name, status, error, stale))
    lines.append("BONE_CONSTRAINT: %s (%d unexpected)"
                 % ("PASS" if failures == 0 else "FAIL", failures))
    for line in lines:
        print(line, flush=True)
    _finish(Range, "bone_constraint_test_result.txt", lines)


def run_perf(Range, target):
    frame = target.get("frame", 0)
    _move_target(Range, target, frame)
    for obj in Range.logic.getCurrentScene().objects:
        if obj.name.startswith("IKRig") and not obj.name.endswith("_skin"):
            obj.update()
    if frame > 30:  # skip warm-up
        totals = target.get("totals") or {}
        for category, values in Range.logic.getProfileInfo().items():
            totals[category] = totals.get(category, 0.0) + values[0]
        target["totals"] = totals
    target["frame"] = frame + 1
    if frame >= PERF_FRAMES:
        samples = PERF_FRAMES - 30
        lines = ["IK_PERF: %-20s %.3f ms" % (category, total / samples)
                 for category, total in sorted(target["totals"].items())]
        lines.append("IK_PERF: average fps %.1f" % Range.logic.getAverageFrameRate())
        for line in lines:
            print(line, flush=True)
        _finish(Range, "ik_perf_result.txt", lines)


if __name__ == "__main__" and "--make-scene" in __import__("sys").argv:
    arguments = __import__("sys").argv
    make_scene(arguments[arguments.index("--make-scene") + 1])
elif __name__ == "__main__" and "--make-perf-scene" in __import__("sys").argv:
    arguments = __import__("sys").argv
    position = arguments.index("--make-perf-scene")
    make_perf_scene(arguments[position + 1], int(arguments[position + 2]),
                    arguments[position + 3])
else:
    run_runtime()
