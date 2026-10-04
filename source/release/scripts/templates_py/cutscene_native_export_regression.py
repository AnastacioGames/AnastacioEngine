"""Regressão de exportação/importação JSON nativa de Cutscene (todos os tipos de evento)."""

import json
import os
import sys
import tempfile

import bpy


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import cutscene_native_events as ev
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


# Valores não padrão por propriedade, para detectar qualquer campo perdido.
def sample_value(key, kind, objects):
    if kind == ev.OBJ:
        return objects[key]
    if kind == ev.STR:
        return "valor " + key + " ção"
    if kind == ev.FLOAT:
        return 1.75
    if kind == ev.INT:
        return 7
    if kind == ev.BOOL:
        return True
    raise ValueError(kind)


def event_snapshot(event):
    snapshot = {"name": event.name, "time": round(event.time, 4), "type": event.type}
    for key, kind, _required in ev.ACTIONS[ev.TYPE_TO_ACTION[event.type]][1]:
        value = getattr(event, key)
        if kind == ev.OBJ:
            value = value.name if value else None
        elif kind == ev.FLOAT:
            value = round(value, 4)
        snapshot[key] = value
    return snapshot


def expect_error(function, fragment):
    try:
        function()
    except ValueError as error:
        check(fragment in str(error), "mensagem sem %r: %s" % (fragment, error))
    else:
        raise RuntimeError("[cutscene_native_export_regression] FAIL: erro esperado (%s)" % fragment)


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    objects = {
        key: add_empty(scene, "Obj_" + key)
        for key in ("template_object", "spawn_point", "dependent_object", "look_at_target",
                    "path_object", "path_curve", "path_look_at")
    }

    # Cobertura: toda opção do enum RNA tem ação, e toda ação aponta para uma opção.
    rna_types = {item.identifier for item in
                 bpy.types.CutsceneEvent.bl_rna.properties["type"].enum_items}
    check(rna_types == set(ev.TYPE_TO_ACTION), "tabela de ações difere do enum RNA: %s" %
          sorted(rna_types ^ set(ev.TYPE_TO_ACTION)))

    settings = scene.cutscene_settings
    bpy.ops.cutscene.sequence_add()
    bpy.ops.cutscene.sequence_add()
    settings.sequences[0].name = "Todos os tipos"
    settings.sequences[0].cutscene_id = 4
    settings.sequences[1].name = "Vazia"
    sequence = settings.sequences[0]

    for index, (action, (event_type, fields)) in enumerate(ev.ACTIONS.items()):
        bpy.ops.cutscene.event_add(sequence_index=0)
        event = sequence.events[index]
        event.name = "Evento " + action
        event.time = 0.5 * index
        event.type = event_type
        for key, kind, _required in fields:
            setattr(event, key, sample_value(key, kind, objects))
    expected = [event_snapshot(event) for event in sequence.events]
    check(len(expected) == len(ev.ACTIONS), "nem todos os eventos foram criados")

    document = cutscene_native_export.export_native_cutscene(TEST_FILE)
    check(document["schema_version"] == 2, "schema version mismatch")
    with open(TEST_FILE, "r", encoding="utf-8") as handle:
        on_disk = json.load(handle)
    sequences = on_disk["scenes"][scene.name]["sequences"]
    check([s["name"] for s in sequences] == ["Todos os tipos", "Vazia"], "sequências no JSON")
    check(sequences[0]["cutscene_id"] == 4, "cutscene_id no JSON")
    check([e["action"] for e in sequences[0]["events"]] == list(ev.ACTIONS), "ações/ordem no JSON")
    spawn = sequences[0]["events"][0]
    check(spawn["params"]["template_object"] == "Obj_template_object", "template no JSON")
    check(spawn["params"]["dependent_object"] == "Obj_dependent_object", "dependent no JSON")

    # Ida e volta: apaga tudo, importa o JSON e compara campo a campo.
    imported = cutscene_native_import.import_native_cutscene(TEST_FILE, clear_existing=True)
    check(imported == len(ev.ACTIONS), "importou %d eventos, esperava %d" % (imported, len(ev.ACTIONS)))
    settings = scene.cutscene_settings
    check([s.name for s in settings.sequences] == ["Todos os tipos", "Vazia"],
          "nomes de sequência perdidos na volta")
    check(settings.sequences[0].cutscene_id == 4, "cutscene_id perdido na volta")
    check(len(settings.sequences[1].events) == 0, "sequência vazia ganhou eventos")
    actual = [event_snapshot(event) for event in settings.sequences[0].events]
    for want, got in zip(expected, actual):
        check(want == got, "evento difere na volta:\n  esperado %r\n  obtido   %r" % (want, got))
    check(len(actual) == len(expected), "quantidade de eventos difere na volta")

    # Segunda exportação deve ser idêntica (estável).
    with open(TEST_FILE, "r", encoding="utf-8") as handle:
        first = handle.read()
    cutscene_native_export.export_native_cutscene(TEST_FILE)
    with open(TEST_FILE, "r", encoding="utf-8") as handle:
        check(handle.read() == first, "export -> import -> export não é estável")

    # Evento obrigatório sem objeto: o export recusa; Camera Path sem curva também.
    bpy.ops.cutscene.event_add(sequence_index=0)
    broken = settings.sequences[0].events[-1]
    broken.type = "SPAWN_OBJECT"
    expect_error(lambda: cutscene_native_export.export_native_cutscene(TEST_FILE), "ausente")
    bpy.ops.cutscene.event_remove(sequence_index=0, event_index=len(settings.sequences[0].events) - 1)

    print("[cutscene_native_export_regression] PASS", flush=True)


if __name__ == "__main__":
    main()
