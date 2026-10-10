"""Exporta Scene.cutscene_settings para o schema JSON nativo versionado.

Uso no Range/Blender 2.79:
    AnastacioEngine.exe --background arquivo.blend --python \
        source/release/scripts/templates_py/cutscene_native_export.py -- \
        cutscenes_native.json

Todos os tipos de evento têm representação (schema_version 2; ver
``cutscene_native_events.py``).
"""

import json
import os
import sys

import bpy


SCHEMA_VERSION = 2

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import cutscene_native_events as ev


def _where(scene_name, sequence_name, event_index):
    return "cena %s, sequência %s, evento %d" % (scene_name, sequence_name, event_index)


def _event_document(event, scene_name, sequence_name, event_index):
    action = ev.TYPE_TO_ACTION.get(event.type)
    if action is None:
        raise ValueError("tipo '%s' não possui equivalente nativo (%s)" %
                         (event.type, _where(scene_name, sequence_name, event_index)))

    params = {}
    for key, kind, required in ev.ACTIONS[action][1]:
        value = getattr(event, key)
        if kind == ev.OBJ:
            if value is None:
                if required:
                    raise ValueError("%s ausente (%s)" %
                                     (key, _where(scene_name, sequence_name, event_index)))
                continue
            value = value.name
        elif kind == ev.FLOAT:
            value = float(value)
        elif kind == ev.INT:
            value = int(value)
        elif kind == ev.BOOL:
            value = bool(value)
        params[key] = value
    return {
        "action": action,
        "name": event.name,
        "time": event.time,
        "params": params,
    }


def export_native_cutscene(path, scene=None):
    scene = scene or bpy.context.scene
    sequences = []
    for sequence in scene.cutscene_settings.sequences:
        sequences.append({
            "name": sequence.name,
            "cutscene_id": sequence.cutscene_id,
            "events": [
                _event_document(event, scene.name, sequence.name, event_index)
                for event_index, event in enumerate(sequence.events)
            ],
        })

    document = {
        "schema_version": SCHEMA_VERSION,
        "scenes": {scene.name: {"sequences": sequences}},
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
          len(document["scenes"][bpy.context.scene.name]["sequences"]))


if __name__ == "__main__":
    main()
