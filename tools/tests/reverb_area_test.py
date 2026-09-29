"""Checks the native Reverb Area (Object.use_reverb_area / Add > Reverb Area).

Editor side (RNA): picking a behavior copies its values, editing a value switches
to Custom, the shape follows the Empty display. Game side: the camera walks
through spheres/boxes (rotated, non-uniform scale, nested with priority) and
the reverb/filter state of the speakers is compared with the expected fade.

    build/bin/RangeEngine.exe -b --python tools/tests/reverb_area_test.py -- --make-scene reverb_area.range
    build/bin/RangeRuntime.exe reverb_area.range

Results are printed with the REVERB_AREA prefix and written to
reverb_area_test_result.txt next to the scene. The expected values are saved
by the editor pass as reverb_area_reference.json.
"""

from __future__ import print_function

import json
import math

REFERENCE = "reverb_area_reference.json"
TOLERANCE = 1e-4
TICKS_PER_CASE = 4  # the world transform of the moved camera is read on a later tick


def _influence(area, point):
    """Same math as reverb_area_influence() in KX_Scene.cpp."""
    local = area.matrix_world.to_3x3().normalized().transposed() * (point - area.matrix_world.to_translation())
    scale = area.matrix_world.to_scale()
    u = []
    for i in range(3):
        half = abs(scale[i] * area.empty_draw_size)
        u.append(local[i] / half)
    if area.reverb_area.shape == 'BOX':
        dist = max(abs(v) for v in u)
    else:
        dist = math.sqrt(sum(v * v for v in u))
    inner = min(max(area.reverb_area.inner_factor, 0.4), 0.99)
    return min(max((1.0 - dist) / (1.0 - inner), 0.0), 1.0)


def _expected(areas, point):
    best = None
    best_influence = 0.0
    for area in areas:
        influence = _influence(area, point)
        if influence <= 0.0:
            continue
        stronger = influence > best_influence + 1e-4
        tie = abs(influence - best_influence) <= 1e-4 and area.reverb_area.priority > best.reverb_area.priority \
            if best else False
        if best is None or stronger or tie:
            best, best_influence = area, influence
    if best is None:
        return {"area": None, "effect": 0}
    ra = best.reverb_area
    return {
        "area": best.name,
        "influence": best_influence,
        "effect": 1,
        "reverb_gain": ra.gain * best_influence,
        "decay_time": ra.decay_time,
        "filter_gain": 1.0 - best_influence * (1.0 - ra.filter_gain),
        "filter_gainhf": 1.0 - best_influence * (1.0 - ra.filter_gain_hf),
    }


def _check_editor(bpy):
    """RNA behavior, printed as REVERB_AREA_EDITOR lines. Returns the failure count."""
    failures = 0

    def check(label, ok):
        nonlocal failures
        print("REVERB_AREA_EDITOR: %-40s %s" % (label, "PASS" if ok else "FAIL"), flush=True)
        failures += 0 if ok else 1

    bpy.ops.object.reverb_area_add(preset='CAVERN', shape='BOX', size=3.0)
    ob = bpy.context.active_object
    ra = ob.reverb_area
    check("add: flag on", ob.use_reverb_area)
    check("add: behavior Cavern", ra.preset == 'CAVERN')
    check("add: Cavern values copied", abs(ra.decay_time - 2.31) < 1e-5 and ra.filter_type == 'BANDPASS')
    check("add: box drawn as cube", ob.empty_draw_type == 'CUBE' and ra.shape == 'BOX')
    check("add: size is the Empty size", abs(ob.empty_draw_size - 3.0) < 1e-5)
    check("add: default fade zone 0.8", abs(ra.inner_factor - 0.8) < 1e-5)
    ra.shape = 'SPHERE'
    check("shape Sphere draws a sphere", ob.empty_draw_type == 'SPHERE')
    ra.gain = 0.123
    check("editing a value switches to Custom", ra.preset == 'CUSTOM' and abs(ra.gain - 0.123) < 1e-5)
    ra.preset = 'HALL'
    check("picking Hall overwrites values", abs(ra.decay_time - 3.92) < 1e-5 and abs(ra.gain - 0.316) < 1e-5)

    # An Empty from an old file (zeroed struct) gets defaults when the flag is turned on.
    plain = bpy.data.objects.new("PlainEmpty", None)
    bpy.context.scene.objects.link(plain)
    plain.empty_draw_type = 'CUBE'
    plain.use_reverb_area = True
    check("flag on old Empty seeds Generic", plain.reverb_area.preset == 'GENERIC'
          and abs(plain.reverb_area.gain - 0.32) < 1e-5 and plain.reverb_area.shape == 'BOX')

    bpy.data.objects.remove(ob, do_unlink=True)
    bpy.data.objects.remove(plain, do_unlink=True)
    return failures


def _write_wav(path):
    import struct
    import wave

    rate = 22050
    with wave.open(path, "w") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(2 * math.pi * 440 * i / rate)))
                                    for i in range(rate)))


def _add_area(bpy, name, preset, shape, size, location, rotation_z=0.0, scale=(1.0, 1.0, 1.0), priority=0):
    bpy.ops.object.reverb_area_add(preset=preset, shape=shape, size=size)
    ob = bpy.context.active_object
    ob.name = name
    ob.location = location
    ob.rotation_euler = (0.0, 0.0, math.radians(rotation_z))
    ob.scale = scale
    ob.reverb_area.priority = priority
    return ob


def _add_speaker(bpy, scene, name, sound, is3d):
    data = bpy.data.speakers.new(name)
    data.sound = sound
    data.use_sound_3d = is3d
    data.mode = 'LOOPEND'
    data.start_init = True
    ob = bpy.data.objects.new(name, data)
    ob.location = (0.0, 0.0, 0.0)
    scene.objects.link(ob)
    return ob


def make_scene(output):
    import os
    import bpy
    from mathutils import Vector

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_GAME"
    scene.game_settings.resolution_x = 640
    scene.game_settings.resolution_y = 360
    if hasattr(scene, "audio3d_update"):
        scene.audio3d_update = 0

    editor_failures = _check_editor(bpy)

    camera = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    scene.objects.link(camera)
    scene.camera = camera

    areas = [
        _add_area(bpy, "Cave", 'CAVERN', 'SPHERE', 10.0, (0.0, 0.0, 0.0)),
        # Nested in the cave, rotated: wins the tie at full strength by priority.
        _add_area(bpy, "Room", 'HALL', 'BOX', 2.0, (5.0, 0.0, 0.0), rotation_z=45.0, priority=1),
        # Rotated box with non-uniform scale: half extents 4 x 2 x 2 in its own axes.
        _add_area(bpy, "Lake", 'UNDERWATER', 'BOX', 2.0, (50.0, 0.0, 0.0), rotation_z=45.0, scale=(2.0, 1.0, 1.0)),
    ]
    scene.update()

    diag = Vector((math.cos(math.radians(45.0)), math.sin(math.radians(45.0)), 0.0))
    perp = Vector((-diag.y, diag.x, 0.0))
    points = [
        ("outside everything", Vector((0.0, -30.0, 0.0))),
        ("cave center", Vector((0.0, 0.0, 0.0))),
        ("cave fade band", Vector((0.0, -9.0, 0.0))),
        ("room center (priority tie)", Vector((5.0, 0.0, 0.0))),
        ("room fade band (cave stronger)", Vector((5.0, 0.0, 0.0)) + diag * 1.9),
        ("lake local X 3.5 (rotated)", Vector((50.0, 0.0, 0.0)) + diag * 3.5),
        ("lake local Y 1.9 (rotated)", Vector((50.0, 0.0, 0.0)) + perp * 1.9),
        ("lake local Y 2.1 (outside)", Vector((50.0, 0.0, 0.0)) + perp * 2.1),
        ("back in the cave", Vector((0.0, 0.0, 0.0))),
    ]
    reference = {
        "editor_failures": editor_failures,
        "cases": [{"label": label, "point": list(point), "expected": _expected(areas, point)}
                  for label, point in points],
    }

    folder = os.path.dirname(os.path.abspath(output))
    wav = os.path.join(folder, "reverb_area_tone.wav")
    _write_wav(wav)
    sound = bpy.data.sounds.load(wav)
    _add_speaker(bpy, scene, "Speaker3D", sound, True)
    _add_speaker(bpy, scene, "Speaker2D", sound, False)
    _add_speaker(bpy, scene, "ScriptSpeaker", sound, True)

    text = bpy.data.texts.new("reverb_area_test.py")
    with open(__file__, "r") as handle:
        text.write(handle.read())
    scene.objects.active = camera
    bpy.ops.logic.sensor_add(type="ALWAYS", object=camera.name)
    sensor = camera.game.sensors[-1]
    sensor.use_pulse_true_level = True
    bpy.ops.logic.controller_add(type="PYTHON", object=camera.name)
    camera.game.controllers[-1].text = text
    sensor.link(camera.game.controllers[-1])

    with open(os.path.join(folder, REFERENCE), "w") as handle:
        json.dump(reference, handle, indent=1)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(output))
    print("REVERB_AREA_SCENE: SAVED %s (%d editor failures)" % (output, editor_failures))


def run_runtime():
    import Range

    camera = Range.logic.getCurrentController().owner
    scene = Range.logic.getCurrentScene()
    if "reference" not in camera:
        with open(Range.logic.expandPath("//" + REFERENCE), "r") as handle:
            camera["reference"] = json.load(handle)
        # A script-owned effect: reverb areas must leave this speaker alone.
        scene.objects["ScriptSpeaker"].SetEffect(1, 0)
    cases = camera["reference"]["cases"]
    tick = camera.get("tick", 0)
    index, step = divmod(tick, TICKS_PER_CASE)

    if index >= len(cases):
        report(Range, camera)
        return

    case = cases[index]
    if step == 0:
        camera.worldPosition = case["point"]
    elif step == TICKS_PER_CASE - 1:
        results = camera.get("results") or []
        results.append(_measure(scene, case))
        camera["results"] = results
    camera["tick"] = tick + 1


def _measure(scene, case):
    expected = case["expected"]
    speaker = scene.objects["Speaker3D"]
    errors = []

    if speaker.GetActiveEffect() != expected["effect"]:
        errors.append("effect %d != %d" % (speaker.GetActiveEffect(), expected["effect"]))
    if expected["effect"]:
        for name in ("reverb_gain", "decay_time", "filter_gain", "filter_gainhf"):
            attr = "reverb_decay_time" if name == "decay_time" else name
            got = getattr(speaker, attr)
            if abs(got - expected[name]) > TOLERANCE:
                errors.append("%s %.5f != %.5f" % (attr, got, expected[name]))

    if scene.objects["Speaker2D"].GetActiveEffect() != 0:
        errors.append("2D speaker got an effect")
    script = scene.objects["ScriptSpeaker"]
    if script.GetActiveEffect() != 1 or abs(script.reverb_gain - 0.32) > TOLERANCE:
        errors.append("script-owned speaker was changed (effect %d gain %.3f)"
                      % (script.GetActiveEffect(), script.reverb_gain))

    detail = "area=%s" % expected["area"]
    if expected["effect"]:
        detail += " influence=%.3f reverb_gain=%.4f" % (expected["influence"], speaker.reverb_gain)
    return "REVERB_AREA: %-32s %-4s %s %s" % (case["label"], "FAIL" if errors else "PASS", detail,
                                              "; ".join(errors))


def report(Range, camera):
    lines = list(camera["results"])
    failures = sum(1 for line in lines if " FAIL " in line) + camera["reference"]["editor_failures"]
    lines.append("REVERB_AREA: editor checks: %d failures" % camera["reference"]["editor_failures"])
    lines.append("REVERB_AREA: %s (%d failures)" % ("PASS" if failures == 0 else "FAIL", failures))
    for line in lines:
        print(line, flush=True)
    with open(Range.logic.expandPath("//reverb_area_test_result.txt"), "w") as handle:
        handle.write("\n".join(lines) + "\n")
    Range.logic.endGame()


if __name__ == "__main__" and "--make-scene" in __import__("sys").argv:
    arguments = __import__("sys").argv
    make_scene(arguments[arguments.index("--make-scene") + 1])
else:
    run_runtime()
