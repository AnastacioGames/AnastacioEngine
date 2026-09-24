import bpy
import os
import sys
import subprocess
from bpy.types import Operator
from bpy.app.translations import pgettext_tip as tip_
from bpy.props import EnumProperty, IntProperty


class FLOWMENU_OT_open_external_editor(Operator):
    bl_label = "Open AS"
    bl_idname = "wm.flowmenu_open_external_editor"
    bl_description = "Opens the project folder or the script of the selected component"

    # Se index >= 0, abre o script daquele componente. Se -1, abre a pasta do projeto.
    index: IntProperty(default=-1)

    editors_enum: EnumProperty(name="Editor", items=[
        ("default", "System Default", "Opens with the default program of the system"),
        ("code", "VSCode", "Visual Studio Code"),],
                               default="default")

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "editors_enum")

    def invoke(self, context, event):
        # Se o index for -1, foi chamado pelo menu geral -> Mostra Popup para escolher editor
        if self.index == -1:
            wm = context.window_manager
            return wm.invoke_props_dialog(self)

        # Se veio de um componente específico (botão), executa direto
        return self.execute(context)

    def execute(self, context):
        # 1. MODO ESPECÍFICO: Abre um arquivo de script
        if self.index >= 0:
            return self.open_specific_script(context)

        # 2. MODO GERAL: Abre a pasta do projeto
        return self.open_project_folder(context)

    def get_editor_command(self, path):
        """Retorna o comando correto baseado no SO e no editor escolhido"""
        editor = self.editors_enum

        # Se for o padrão do sistema
        if editor == "default":
            if os.name == 'nt':  # Windows
                os.startfile(path)
            elif sys.platform.startswith('darwin'):  # Mac
                subprocess.call(('open', path))
            else:  # Linux
                subprocess.call(('xdg-open', path))
            return True

        # Se for VSCode ou Sublime
        try:
            # VSCode usa 'code', Sublime usa 'subl'
            # 'path' aqui é o arquivo ou a pasta
            subprocess.Popen([editor, path], shell=True)
            return True
        except Exception as e:
            self.report({'ERROR'}, tip_("Could not run the editor '%s': %s") % (editor, e))
            return False

    def open_specific_script(self, context):
        ob = context.active_object
        if not ob or not ob.game:
            return {'CANCELLED'}

        try:
            component = ob.game.components[self.index]
        except IndexError:
            return {'CANCELLED'}

        # Lógica inteligente para achar o arquivo
        module_name = component.module  # Ex: scripts.player ou player

        # Onde o .blend está salvo
        base_path = bpy.path.abspath("//")
        if not base_path:
            self.report({'ERROR'}, tip_("Save the .blend file before opening scripts!"))
            return {'CANCELLED'}

        # Tenta construir o caminho do arquivo
        # 1. Tenta transformar pontos em barras (ex: scripts.player -> scripts/player.py)
        rel_path = module_name.replace(".", os.sep) + ".py"
        filepath = os.path.join(base_path, rel_path)

        # 2. Se não existir, tenta forçar a pasta 'scripts' caso o módulo não tenha especificado
        if not os.path.exists(filepath):
            # Ex: modulo 'player' -> tenta 'scripts/player.py'
            alt_path = os.path.join(base_path, "scripts", rel_path)
            if os.path.exists(alt_path):
                filepath = alt_path

        # Verificação final
        if not os.path.exists(filepath):
            self.report({'WARNING'}, tip_("File not found at: %s") % filepath)
            # Tenta abrir a pasta para ajudar o usuário a achar
            self.get_editor_command(base_path)
            return {'CANCELLED'}

        # Abre o arquivo encontrado
        self.get_editor_command(filepath)
        return {'FINISHED'}

    def open_project_folder(self, context):
        # Pega o caminho do blend
        root_file = bpy.data.filepath
        if not root_file:
            # Fallback para pasta de usuário se arquivo não salvo
            root_path = os.path.expanduser("~")
        else:
            root_path = os.path.dirname(root_file)

        self.get_editor_command(root_path)
        return {'FINISHED'}
