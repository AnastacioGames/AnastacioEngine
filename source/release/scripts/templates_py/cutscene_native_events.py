"""Tabela dos tipos de evento de Cutscene usada pelo export/import JSON.

Cada ação do JSON mapeia para um tipo ``CutsceneEvent.type`` e para as
propriedades RNA que a ação persiste. Objetos são gravados por nome; os demais
campos são valores simples. Mantenha esta tabela em sincronia com
``rna_def_cutscene_event`` (rna_scene.c).
"""

OBJ = "object"
STR = "string"
FLOAT = "float"
INT = "int"
BOOL = "bool"

# action -> (event type, [(chave JSON == nome RNA, tipo, obrigatório)])
ACTIONS = {
    "spawn_object": ("SPAWN_OBJECT", [
        ("template_object", OBJ, True), ("spawn_point", OBJ, True),
        ("dependent_object", OBJ, False)]),
    "dialog": ("DIALOG", [
        ("dialog_text_en", STR, False), ("dialog_text_pt", STR, False),
        ("dialog_text_es", STR, False), ("dialog_text_ru", STR, False),
        ("dialog_audio_path", STR, False), ("dialog_live", BOOL, False)]),
    "hide_dialog": ("HIDE_DIALOG", []),
    "camera_shot": ("CAMERA_SHOT", [("camera_order", INT, False)]),
    "look_at": ("LOOK_AT", [("look_at_target", OBJ, False)]),
    "restore_gameplay_camera": ("RESTORE_GAMEPLAY_CAMERA", []),
    "camera_start": ("CAMERA_START", []),
    "camera_stop": ("CAMERA_STOP", []),
    "lock_player": ("LOCK_PLAYER", []),
    "unlock_player": ("UNLOCK_PLAYER", []),
    "player_anim": ("PLAYER_ANIM", [
        ("player_anim_name", STR, False), ("player_anim_blend", FLOAT, False)]),
    "show_mouse": ("SHOW_MOUSE", []),
    "hide_mouse": ("HIDE_MOUSE", []),
    "change_scene": ("CHANGE_SCENE", [("change_scene_name", STR, False)]),
    "wait_time": ("WAIT_TIME", [("wait_seconds", FLOAT, False)]),
    "wait_trigger": ("WAIT_TRIGGER", [("trigger_name", STR, False)]),
    "wait_camera_end": ("WAIT_CAMERA_END", []),
    "camera_path": ("CAMERA_PATH", [
        ("path_object", OBJ, True), ("path_curve", OBJ, True),
        ("path_look_at", OBJ, False), ("path_duration", FLOAT, False),
        ("path_follow", BOOL, False), ("path_set_camera", BOOL, False)]),
}

TYPE_TO_ACTION = {value[0]: key for key, value in ACTIONS.items()}
