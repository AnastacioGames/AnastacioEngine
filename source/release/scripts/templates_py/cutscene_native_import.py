"""Importa o schema JSON legado para Scene.cutscene_settings.

Uso no Range/Blender 2.79:
    RangeEngine.exe --background arquivo.blend --python \
        source/release/scripts/templates_py/cutscene_native_import.py -- \
        scripts/cutscenes/cutscenes_data.json

O importador aceita o formato legado ``{cena: {id: [passos]}}``, o schema 1
(``{"schema_version": 1, "scenes": {cena: {id: [passos]}}}``) e o schema 2
(``{cena: {"sequences": [{name, cutscene_id, events}]}}``) gerado por
``cutscene_native_export.py``. Todos os tipos de evento nativos são aceitos
(``cutscene_native_events.py``); ação desconhecida é rejeitada explicitamente.
"""

import json
import os
import sys

import bpy


SUPPORTED_SCHEMA_VERSIONS = (1, 2)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import cutscene_native_events as ev

# Nomes aceitos no formato legado do add-on, só para Spawn Object.
SPAWN_ALIASES = {
    "template_object": ("object",),
    "spawn_point": ("empty",),
    "dependent_object": ("dependent",),
}


def _read_document(path):
    with open(bpy.path.abspath(path), "r", encoding="utf-8") as handle:
        document = json.load(handle)

    version = None
    if isinstance(document, dict) and "scenes" in document:
        version = document.get("schema_version")
        if version not in SUPPORTED_SCHEMA_VERSIONS:
            raise ValueError("schema_version %r não suportado (esperado %s)" %
                             (version, "/".join(str(v) for v in SUPPORTED_SCHEMA_VERSIONS)))
        document = document["scenes"]

    if not isinstance(document, dict):
        raise ValueError("o JSON deve conter um mapa de cenas")
    return document, version


def _object_or_none(name, label, scene_name, sequence_name):
    if not name:
        return None
    obj = bpy.data.objects.get(name)
    if obj is None:
        raise ValueError("%s '%s' não encontrado (cena %s, sequência %s)" %
                         (label, name, scene_name, sequence_name))
    return obj


def _param(params, key, action):
    if key in params:
        return params[key]
    if action == "spawn_object":
        for alias in SPAWN_ALIASES.get(key, ()):
            if alias in params:
                return params[alias]
    return None


def _coerce(value, kind, key):
    try:
        if kind == ev.STR:
            return str(value)
        if kind == ev.FLOAT:
            return float(value)
        if kind == ev.INT:
            return int(value)
        if kind == ev.BOOL:
            return bool(value)
    except (TypeError, ValueError):
        raise ValueError("valor inválido para '%s': %r" % (key, value))
    return value


def _add_event(sequence_index, sequence, step, scene_name, sequence_name, event_index):
    action = step.get("action")
    spec = ev.ACTIONS.get(action)
    if spec is None:
        raise ValueError("ação '%s' não possui equivalente nativo (cena %s, "
                         "sequência %s, evento %d)" %
                         (action, scene_name, sequence_name, event_index))
    event_type, fields = spec

    params = step.get("params") or {}
    # Resolve tudo antes de criar o evento, para uma falha não deixar lixo.
    values = {}
    for key, kind, required in fields:
        raw = _param(params, key, action)
        if kind == ev.OBJ:
            value = _object_or_none(raw, key, scene_name, sequence_name)
            if value is None and required:
                raise ValueError("%s exige '%s' (cena %s, sequência %s)" %
                                 (action, key, scene_name, sequence_name))
        elif raw is None:
            continue
        else:
            value = _coerce(raw, kind, key)
        values[key] = value

    result = bpy.ops.cutscene.event_add(sequence_index=sequence_index)
    if "FINISHED" not in result:
        raise RuntimeError("não foi possível criar evento nativo (cena %s, sequência %s)" %
                           (scene_name, sequence_name))
    event = sequence.events[-1]
    event.name = step.get("name", action.replace("_", " ").title())
    event.time = float(step.get("time", params.get("time", 0.0)))
    event.type = event_type
    for key, value in values.items():
        setattr(event, key, value)


def _sequences_of(source_scene, version, scene_name):
    """Normaliza a cena para uma lista de (nome, cutscene_id, passos)."""
    if not isinstance(source_scene, dict):
        raise ValueError("a cena '%s' deve conter um mapa de sequências" % scene_name)
    if version == 2:
        entries = source_scene.get("sequences")
        if not isinstance(entries, list):
            raise ValueError("a cena '%s' deve conter a lista 'sequences'" % scene_name)
        result = []
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("events"), list):
                raise ValueError("sequência inválida na cena '%s'" % scene_name)
            result.append((entry.get("name", "Sequence"), entry.get("cutscene_id"),
                           entry["events"]))
        return result

    result = []
    for key, steps in source_scene.items():
        if not isinstance(steps, list):
            raise ValueError("sequência '%s' deve ser uma lista de passos" % key)
        result.append(("%s / %s" % (scene_name, key), None, steps))
    return result


def import_native_cutscene(path, scene=None, clear_existing=False):
    scene = scene or bpy.context.scene
    document, version = _read_document(path)
    source_scene = document.get(scene.name)
    if source_scene is None and len(document) == 1:
        source_scene = next(iter(document.values()))
    if source_scene is None:
        raise ValueError("o JSON não contém a cena ativa '%s'" % scene.name)
    sequences = _sequences_of(source_scene, version, scene.name)

    settings = scene.cutscene_settings
    if clear_existing:
        while settings.sequences:
            result = bpy.ops.cutscene.sequence_remove(index=len(settings.sequences) - 1)
            if "FINISHED" not in result:
                raise RuntimeError("não foi possível limpar sequências nativas")

    imported = 0
    for name, cutscene_id, steps in sequences:
        result = bpy.ops.cutscene.sequence_add()
        if "FINISHED" not in result:
            raise RuntimeError("não foi possível criar sequência nativa")
        sequence_index = len(settings.sequences) - 1
        sequence = settings.sequences[sequence_index]
        sequence.name = name
        if cutscene_id is not None:
            sequence.cutscene_id = int(cutscene_id)
        for event_index, step in enumerate(steps):
            _add_event(sequence_index, sequence, step, scene.name, sequence.name, event_index)
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
