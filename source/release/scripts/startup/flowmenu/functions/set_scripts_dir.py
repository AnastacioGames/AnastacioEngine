import bpy
import os


def set_scripts_dir():
    # Verifica se o arquivo foi salvo no disco
    if not bpy.data.is_saved:
        return ""

    game_file_path = bpy.data.filepath

    # Maneira mais segura de pegar o diretório do arquivo atual
    game_scripts_path = os.path.dirname(game_file_path)

    return game_scripts_path