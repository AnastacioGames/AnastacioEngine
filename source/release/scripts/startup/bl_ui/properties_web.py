# Perfil Web da Range Engine (marco A de docs/web-profile-validation-plan.md).
# Somente autoria: guarda configuracoes e mostra o estado. Nao faz I/O no draw()
# e ainda nao valida nem exporta; o botao Exportar Web fica indisponivel com motivo unico.

import bpy
from bpy.types import Panel, PropertyGroup

from .properties_scene import SceneButtonsPanel

WEB_SCHEMA_VERSION = 1
WEB_RUNTIME_ID = "web-runtime-release"
WEB_EXPORT_BLOCKED_REASON = "Validador Web ainda não implementado (marco B)."


class RangeWebSettings(PropertyGroup):
    schema_version: bpy.props.IntProperty(
        name="Schema",
        description="Versão das configurações do perfil Web",
        default=WEB_SCHEMA_VERSION,
        options={'HIDDEN'},
    )
    check_compatibility: bpy.props.BoolProperty(
        name="Verificar compatibilidade Web",
        description="Mostra avisos de compatibilidade Web durante a edição. "
                    "A exportação Web sempre valida, independentemente desta opção",
        default=False,
    )
    runtime_id: bpy.props.StringProperty(
        name="Runtime",
        description="Runtime Web usado no pacote; a disponibilidade é verificada na exportação",
        default=WEB_RUNTIME_ID,
    )
    entry_scene: bpy.props.StringProperty(
        name="Cena de entrada",
        description="Cena inicial do pacote Web; vazio usa a cena atual",
        default="",
    )
    output_directory: bpy.props.StringProperty(
        name="Destino",
        description="Diretório de saída do pacote Web",
        subtype='DIR_PATH',
        default="//web/",
    )


class SCENE_PT_range_web(SceneButtonsPanel, Panel):
    bl_label = "Web (Range)"
    COMPAT_ENGINES = {'BLENDER_GAME'}
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        web = context.scene.range_web

        layout.prop(web, "check_compatibility")

        col = layout.column()
        col.prop(web, "runtime_id")
        col.prop(web, "entry_scene")
        col.prop(web, "output_directory")

        layout.separator()
        layout.label(text="Nenhuma verificação executada.", icon='INFO')

        col = layout.column()
        col.enabled = False
        col.label(text="Exportar Web indisponível:")
        col.label(text=WEB_EXPORT_BLOCKED_REASON)
        layout.label(text="Prévia desktop (tecla P) não é Teste Web.")


classes = (
    RangeWebSettings,
    SCENE_PT_range_web,
)

if __name__ == "__main__":  # only for live edit.
    from bpy.utils import register_module
    register_module(__name__)
