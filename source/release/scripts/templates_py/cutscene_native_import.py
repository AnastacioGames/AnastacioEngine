"""Importa o schema JSON legado para Scene.cutscene_settings.

Uso no Range/Blender 2.79:
    RangeEngine.exe --background arquivo.blend --python \
        source/release/scripts/templates_py/cutscene_native_import.py -- \
        scripts/cutscenes/cutscenes_data.json

O importador aceita o formato legado ``{cena: {id: [passos]}}`` e o formato
versionado ``{"schema_version": 1, "scenes": {...}}``. O DNA nativo ainda
possui somente Spawn Object; qualquer outra ação é rejeitada explicitamente.
"""

import json
import sys

import bpy


SUPPORTED_SCHEMA_VERSION = 1


def _read_document(path):
    with open(bpy.path.abspath(path), "r", encoding="utf-8") as handle:
        document = json.load(handle)

    if isinstance(document, dict) and "scenes" in document:
        version = document.get("schema_version")
        if version != SUPPORTED_SCHEMA_VERSION:
            raise ValueError("schema_version %r não suportado (esperado %d)" %
                             (version, SUPPORTED_SCHEMA_VERSION))
        document = document["scenes"]

    if not isinstance(document, dict):
        raise ValueError("o JSON deve conter um mapa de cenas")
    return document


def _object_or_none(name, label, scene_name, sequence_name):
    if not name:
        return None
    obj = bpy.data.objects.get(name)
    if obj is None:
        raise ValueError("%s '%s' não encontrado (cena %s, sequência %s)" %
                         (label, name, scene_name, sequence_name))
    return obj


def _spawn_event(scene, sequence_index, sequence, step, scene_name, sequence_name, event_index):
    action = step.get("action")
    if action != "spawn_object":
        raise ValueError("ação '%s' não possui equivalente nativo (cena %s, "
                         "sequência %s, evento %d)" %
                         (action, scene_name, sequence_name, event_index))

    params = step.get("params") or {}
    result = bpy.ops.cutscene.event_add(sequence_index=sequence_index)
    if "FINISHED" not in result:
        raise RuntimeError("não foi possível criar evento nativo (cena %s, sequência %s)" %
                           (scene_name, sequence_name))
    event = sequence.events[-1]
    event.name = step.get("name", "Spawn Object")
    event.time = float(step.get("time", params.get("time", 0.0)))
    event.type = "SPAWN_OBJECT"
    event.template_object = _object_or_none(
        params.get("object") or params.get("template_object"),
        "Template Object", scene_name, sequence_name)
    event.spawn_point = _object_or_none(
        params.get("empty") or params.get("spawn_point"),
        "Spawn Point", scene_name, sequence_name)
    event.dependent_object = _object_or_none(
        params.get("dependent") or params.get("dependent_object"),
        "Dependent Object", scene_name, sequence_name)
    if event.template_object is None or event.spawn_point is None:
        bpy.ops.cutscene.event_remove(sequence_index=sequence_index,
                                      event_index=len(sequence.events) - 1)
        raise ValueError("Spawn Object exige object e empty (cena %s, sequência %s)" %
                         (scene_name, sequence_name))


def import_native_cutscene(path, scene=None, clear_existing=False):
    scene = scene or bpy.context.scene
    document = _read_document(path)
    source_scene = document.get(scene.name)
    if source_scene is None and len(document) == 1:
        source_scene = next(iter(document.values()))
    if source_scene is None:
        raise ValueError("o JSON não contém a cena ativa '%s'" % scene.name)
    if not isinstance(source_scene, dict):
        raise ValueError("a cena '%s' deve conter um mapa de sequências" % scene.name)

    settings = scene.cutscene_settings
    if clear_existing:
        while settings.sequences:
            result = bpy.ops.cutscene.sequence_remove(index=len(settings.sequences) - 1)
            if "FINISHED" not in result:
                raise RuntimeError("não foi possível limpar sequências nativas")

    imported = 0
    for sequence_key, steps in source_scene.items():
        if not isinstance(steps, list):
            raise ValueError("sequência '%s' deve ser uma lista de passos" % sequence_key)
        result = bpy.ops.cutscene.sequence_add()
        if "FINISHED" not in result:
            raise RuntimeError("não foi possível criar sequência nativa")
        sequence_index = len(settings.sequences) - 1
        sequence = settings.sequences[sequence_index]
        sequence.name = "%s / %s" % (scene.name, sequence_key)
        for event_index, step in enumerate(steps):
            _spawn_event(scene, sequence_index, sequence, step, scene.name, sequence.name, event_index)
            imported += 1
    settings.active_sequence_index = max(0, len(settings.sequences) - 1)
    settings.active_event_index = 0
    return imported


def main():
    arguments = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if len(arguments) != 1:
        raise SystemExit("uso: ... -- cutscenes_data.json")
    count = import_native_cutscene(arguments[0], clear_existing=False)
    print("[cutscene_native_import] importados %d eventos nativos" % count)


if __name__ == "__main__":
    main()
