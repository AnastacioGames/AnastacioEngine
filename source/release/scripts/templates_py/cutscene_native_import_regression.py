"""Regressão do importador JSON nativo de Cutscene.

Execute no editor instalado:

    RangeEngine.exe --background --factory-startup --python \
        cutscene_native_import_regression.py

O teste cobre os dois formatos aceitos, referências por nome e rejeição de
schema/ações sem equivalente nativo. Ele não executa a Cutscene no runtime.
"""

import json
import os
import sys
import tempfile

import bpy


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import cutscene_native_import


TEST_FILE = os.path.join(tempfile.gettempdir(), "cutscene_native_import_regression.json")


def check(condition, message):
    if not condition:
        raise RuntimeError("[cutscene_native_import_regression] FAIL: " + message)


def add_empty(scene, name):
    obj = bpy.data.objects.new(name, None)
    scene.objects.link(obj)
    return obj


def write_json(document):
    with open(TEST_FILE, "w", encoding="utf-8") as handle:
        json.dump(document, handle)


def expect_value_error(document, expected_fragment):
    write_json(document)
    try:
        cutscene_native_import.import_native_cutscene(TEST_FILE, clear_existing=True)
    except ValueError as error:
        check(expected_fragment in str(error),
              "rejection message did not contain %r: %s" %
              (expected_fragment, error))
    else:
        raise RuntimeError("[cutscene_native_import_regression] FAIL: invalid JSON was accepted")


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    template = add_empty(scene, "ImportTemplate")
    spawn_point = add_empty(scene, "ImportSpawnPoint")
    dependent = add_empty(scene, "ImportDependent")

    write_json({
        scene.name: {
            "LegacySequence": [{
                "action": "spawn_object",
                "name": "Legacy Spawn",
                "time": 1.25,
                "params": {
                    "object": template.name,
                    "empty": spawn_point.name,
                    "dependent": dependent.name,
                },
            }],
        },
    })
    count = cutscene_native_import.import_native_cutscene(TEST_FILE, clear_existing=True)
    check(count == 1, "legacy format did not import one event")
    sequence = scene.cutscene_settings.sequences[0]
    event = sequence.events[0]
    check(sequence.name == scene.name + " / LegacySequence", "legacy sequence name mismatch")
    check(event.name == "Legacy Spawn", "legacy event name mismatch")
    check(abs(event.time - 1.25) < 0.0001, "legacy event time mismatch")
    check(event.template_object == template, "template reference mismatch")
    check(event.spawn_point == spawn_point, "spawn point reference mismatch")
    check(event.dependent_object == dependent, "dependent reference mismatch")

    write_json({
        "schema_version": 1,
        "scenes": {
            scene.name: {
                "VersionedSequence": [{
                    "action": "spawn_object",
                    "params": {
                        "template_object": template.name,
                        "spawn_point": spawn_point.name,
                    },
                }],
            },
        },
    })
    count = cutscene_native_import.import_native_cutscene(TEST_FILE, clear_existing=True)
    check(count == 1, "versioned format did not import one event")
    check(len(scene.cutscene_settings.sequences) == 1,
          "clear_existing did not remove the previous sequence")

    expect_value_error({"schema_version": 99, "scenes": {}}, "schema_version")
    expect_value_error({scene.name: {"Bad": [{"action": "play_sound"}]}},
                       "equivalente nativo")
    print("[cutscene_native_import_regression] PASS", flush=True)


if __name__ == "__main__":
    main()
