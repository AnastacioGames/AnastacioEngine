"""Regression test for the C Python ABI used by ``Range.constraints``.

Run as a source-level guard from the repository root:

    python tools/tests/constraint_abi_test.py

Run it in a game after building RangeRuntime (the test exits the game itself):

    build/bin/RangeRuntime.exe -p tools/tests/constraint_abi_test.py game.range
"""

from __future__ import print_function


def make_scene(output):
    """Create a minimal .range which runs this same file as a controller."""
    import bpy

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_GAME"
    scene.game_settings.resolution_x = 640
    scene.game_settings.resolution_y = 360

    bpy.ops.mesh.primitive_cube_add(location=(0.0, 0.0, 1.0))
    controller_object = bpy.context.object
    controller_object.name = "ConstraintAbiController"
    controller_object.game.physics_type = "RIGID_BODY"

    text = bpy.data.texts.new("constraint_abi_test.py")
    with open(__file__, "r") as handle:
        text.write(handle.read())
    scene.objects.active = controller_object
    bpy.ops.logic.sensor_add(type="ALWAYS", object=controller_object.name)
    sensor = controller_object.game.sensors[-1]
    sensor.use_pulse_true_level = True
    bpy.ops.logic.controller_add(type="PYTHON", object=controller_object.name)
    controller_object.game.controllers[-1].text = text
    sensor.link(controller_object.game.controllers[-1])
    bpy.ops.wm.save_as_mainfile(filepath=output)
    print("CONSTRAINT_ABI_SCENE: SAVED %s" % output)


def run_runtime():
    import Range

    constraints = Range.constraints
    setters = (
        ("setGravity", (0.0, -9.8, 0.0)),
        ("setDebugMode", (0,)),
        ("setNumIterations", (10,)),
        ("setErp", (0.2,)),
        ("setErp2", (0.8,)),
        ("setGlobalCfm", (0.0,)),
        ("setSplitImpulse", (1,)),
        ("setSplitImpulsePenetrationThreshold", (-0.04,)),
        ("setSplitImpulseTurnErp", (0.1,)),
        ("setLinearSlop", (0.04,)),
        ("setWarmstartingFactor", (0.85,)),
        ("setMaxGyroscopicForce", (100.0,)),
        ("setNumTimeSubSteps", (1,)),
        ("setDeactivationTime", (2.0,)),
        ("setDeactivationLinearTreshold", (0.8,)),
        ("setDeactivationAngularTreshold", (1.0,)),
        ("setContactBreakingTreshold", (0.02,)),
        ("setCcdMode", (1.0,)),
        ("setSorConstant", (1.0,)),
        ("setSolverTau", (0.6,)),
        ("setSolverDamping", (1.0,)),
        ("setLinearAirDamping", (0.0,)),
        ("setUseEpa", (1,)),
        ("setSolverType", (0,)),
    )

    for name, args in setters:
        method = getattr(constraints, name)
        assert method(*args) is None, "%s rejected valid arguments" % name
        try:
            method(*args[:-1])
        except TypeError:
            pass
        else:
            raise AssertionError("%s accepted too few arguments" % name)

    try:
        constraints.setGravity(x=0.0, y=-9.8, z=0.0)
    except TypeError:
        pass
    else:
        raise AssertionError("setGravity unexpectedly accepted keyword arguments")

    for name, args in (("createVehicle", (0,)),
                       ("getVehicleConstraint", (0,)),
                       ("getAppliedImpulse", (0,)),
                       ("removeConstraint", (0,)),
                       ("exportBulletFile", ("constraint_abi_test.bullet",))):
        method = getattr(constraints, name)
        try:
            method(*args[:-1])
        except TypeError:
            pass
        else:
            raise AssertionError("%s accepted too few arguments" % name)

    try:
        constraints.createConstraint(0, 0)
    except TypeError:
        pass
    else:
        raise AssertionError("createConstraint accepted too few arguments")

    with open("constraint_abi_test_result.txt", "w") as handle:
        handle.write("PASS\n")
    print("CONSTRAINT_ABI_TEST: PASS", flush=True)
    Range.logic.endGame()
    Range.logic.NextFrame()


def run_static():
    import os
    import re

    source = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                          "source", "source", "gameengine", "Ketsji",
                          "KX_PyConstraintBinding.cpp")
    with open(source, "r") as handle:
        text = handle.read()

    table = re.search(r"physicsconstraints_methods\[\].*?= \{(.*?)\n\};", text, re.S)
    assert table, "constraint method table not found"
    entries = re.findall(r'\{"[^"]+", \(PyCFunction\)(gPy\w+),\s*\n?\s*'
                         r'(METH_[A-Z_]+(?:\s*\|\s*METH_[A-Z_]+)*)', table.group(1))
    assert len(entries) == 31, "expected every constraint method to be checked"

    for function, flags in entries:
        declaration = re.search(r"static PyObject \*" + re.escape(function) +
                                r"\s*\((.*?)\)\s*\{", text, re.S)
        assert declaration, "declaration missing for %s" % function
        parameters = re.sub(r"\s+", " ", declaration.group(1)).strip()
        parameter_count = len([item for item in parameters.split(",") if item.strip()])
        has_keywords = "METH_KEYWORDS" in flags
        expected_count = 3 if has_keywords else 2
        assert parameter_count == expected_count and "PyObject *args" in parameters and (
            not has_keywords or "PyObject *kwds" in parameters), (
                "%s flags %s require %d arguments (%s), got (%s)" %
                (function, flags, expected_count,
                 "self, args, kwds" if has_keywords else "self, args", parameters))

    print("CONSTRAINT_ABI_STATIC_TEST: PASS (%d methods)" % len(entries))


if __name__ == "__main__" and "--make-scene" in __import__("sys").argv:
    arguments = __import__("sys").argv
    make_scene(arguments[arguments.index("--make-scene") + 1])
else:
    try:
        import Range
    except ImportError:
        run_static()
    else:
        run_runtime()
