"""Exporta Scene.cutscene_settings para o schema JSON nativo versionado.

Uso no Range/Blender 2.79:
    RangeEngine.exe --background arquivo.blend --python \
        source/release/scripts/templates_py/cutscene_native_export.py -- \
        cutscenes_native.json

Somente eventos ``SPAWN_OBJECT`` têm representação nativa nesta versão.
"""

import json
import sys

import bpy


SCHEMA_VERSION = 1


def _object_name(obj, label, scene_name, sequence_name, event_index):
    if obj is None:
        raise ValueError("%s ausente (cena %s, sequência %s, evento %d)" %
                         (label, scene_name, sequence_name, event_index))
    return obj.name


def _event_document(event, scene_name, sequence_name, event_index):
    if event.type != "SPAWN_OBJECT":
        raise ValueError("tipo '%s' não possui equivalente nativo (cena %s, "
                         "sequência %s, evento %d)" %
                         (event.type, scene_name, sequence_name, event_index))

    params = {
        "template_object": _object_name(
            event.template_object, "Template Object", scene_name, sequence_name, event_index),
        "spawn_point": _object_name(
            event.spawn_point, "Spawn Point", scene_name, sequence_name, event_index),
    }
    if event.dependent_object is not None:
        params["dependent_object"] = event.dependent_object.name
    return {
        "action": "spawn_object",
        "name": event.name,
        "time": event.time,
        "params": params,
    }


def export_native_cutscene(path, scene=None):
    scene = scene or bpy.context.scene
    sequences = {}
    settings = scene.cutscene_settings
    for sequence in settings.sequences:
        sequences[sequence.name] = [
            _event_document(event, scene.name, sequence.name, event_index)
            for event_index, event in enumerate(sequence.events)
        ]

    document = {
        "schema_version": SCHEMA_VERSION,
        "scenes": {scene.name: sequences},
    }
    with open(bpy.path.abspath(path), "w", encoding="utf-8") as handle:
        json.dump(document, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return document


def main():
    arguments = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if len(arguments) != 1:
        raise SystemExit("uso: ... -- cutscenes_native.json")
    document = export_native_cutscene(arguments[0])
    print("[cutscene_native_export] exportadas %d sequências" %
          len(document["scenes"][bpy.context.scene.name]))


if __name__ == "__main__":
    main()
