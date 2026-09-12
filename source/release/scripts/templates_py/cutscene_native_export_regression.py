"""Regressão de exportação/importação JSON nativa de Cutscene."""

import json
import os
import sys
import tempfile

import bpy


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import cutscene_native_export
import cutscene_native_import


TEST_FILE = os.path.join(tempfile.gettempdir(), "cutscene_native_export_regression.json")


def check(condition, message):
    if not condition:
        raise RuntimeError("[cutscene_native_export_regression] FAIL: " + message)


def add_empty(scene, name):
    obj = bpy.data.objects.new(name, None)
    scene.objects.link(obj)
    return obj


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    template = add_empty(scene, "ExportTemplate")
    spawn_point = add_empty(scene, "ExportSpawnPoint")
    dependent = add_empty(scene, "ExportDependent")

    bpy.ops.cutscene.sequence_add()
    settings = scene.cutscene_settings
    sequence = settings.sequences[0]
    sequence.name = "Export Sequence"
    bpy.ops.cutscene.event_add(sequence_index=0)
    event = sequence.events[0]
    event.name = "Export Spawn"
    event.time = 3.5
    event.template_object = template
    event.spawn_point = spawn_point
    event.dependent_object = dependent

    document = cutscene_native_export.export_native_cutscene(TEST_FILE)
    check(document["schema_version"] == 1, "schema version mismatch")
    with open(TEST_FILE, "r", encoding="utf-8") as handle:
        on_disk = json.load(handle)
    step = on_disk["scenes"][scene.name]["Export Sequence"][0]
    check(step["action"] == "spawn_object", "action mismatch")
    check(step["time"] == 3.5, "time mismatch")
    check(step["params"]["template_object"] == template.name, "template name mismatch")
    check(step["params"]["spawn_point"] == spawn_point.name, "spawn point name mismatch")
    check(step["params"]["dependent_object"] == dependent.name, "dependent name mismatch")

    imported = cutscene_native_import.import_native_cutscene(TEST_FILE, clear_existing=True)
    check(imported == 1, "round-trip did not import one event")
    event = scene.cutscene_settings.sequences[0].events[0]
    check(event.name == "Export Spawn", "event name lost on round-trip")
    check(abs(event.time - 3.5) < 0.0001, "event time lost on round-trip")
    check(event.template_object == template, "template reference lost on round-trip")
    check(event.spawn_point == spawn_point, "spawn reference lost on round-trip")
    check(event.dependent_object == dependent, "dependent reference lost on round-trip")
    print("[cutscene_native_export_regression] PASS", flush=True)


if __name__ == "__main__":
    main()
