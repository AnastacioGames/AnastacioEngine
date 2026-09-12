"""Smoke test for Cutscene data persistence in a .blend file.

Run from the installed editor:

    RangeEngine.exe --background --factory-startup --python cutscene_persistence_regression.py

The test creates one Spawn Object event, saves it, reopens the file in the
same process, and checks both scalar data and Object ID references.  It is
intended for editor/data regression only; it does not exercise runtime spawn.
"""

import bpy
import os
import tempfile


TEST_FILE = os.path.join(tempfile.gettempdir(), "cutscene_persistence_regression.blend")


def check(condition, message):
    if not condition:
        raise RuntimeError("[cutscene_persistence_regression] FAIL: " + message)


def add_empty(scene, name):
    obj = bpy.data.objects.new(name, None)
    scene.objects.link(obj)
    return obj


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    template = add_empty(scene, "CutsceneTemplate")
    spawn_point = add_empty(scene, "CutsceneSpawnPoint")
    dependent = add_empty(scene, "CutsceneDependent")

    bpy.ops.cutscene.sequence_add()
    settings = scene.cutscene_settings
    sequence = settings.sequences[0]
    sequence.name = "Persistence Sequence"

    bpy.ops.cutscene.event_add(sequence_index=0)
    event = sequence.events[0]
    event.name = "Persistence Spawn"
    event.time = 2.5
    event.template_object = template
    event.spawn_point = spawn_point
    event.dependent_object = dependent

    bpy.ops.wm.save_as_mainfile(filepath=TEST_FILE)
    bpy.ops.wm.open_mainfile(filepath=TEST_FILE)

    scene = bpy.context.scene
    settings = scene.cutscene_settings
    check(len(settings.sequences) == 1, "expected exactly one sequence after reopen")
    sequence = settings.sequences[0]
    check(sequence.name == "Persistence Sequence", "sequence name was not preserved")
    check(len(sequence.events) == 1, "expected exactly one event after reopen")
    event = sequence.events[0]
    check(event.name == "Persistence Spawn", "event name was not preserved")
    check(abs(event.time - 2.5) < 0.0001, "event time was not preserved")
    check(event.template_object.name == "CutsceneTemplate", "template reference was not preserved")
    check(event.spawn_point.name == "CutsceneSpawnPoint", "spawn point reference was not preserved")
    check(event.dependent_object.name == "CutsceneDependent", "dependent reference was not preserved")
    print("[cutscene_persistence_regression] PASS", flush=True)


if __name__ == "__main__":
    main()
