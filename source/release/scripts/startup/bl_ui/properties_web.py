# Perfil Web da Range Engine (marco A de docs/web-profile-validation-plan.md).
# Somente autoria: guarda configuracoes e mostra o estado. Nao faz I/O no draw()
# e ainda nao valida nem exporta; o botao Exportar Web fica indisponivel com motivo unico.

import bpy
from bpy.types import Operator, Panel, PropertyGroup

from .properties_scene import SceneButtonsPanel

WEB_SCHEMA_VERSION = 1
WEB_RUNTIME_ID = "web-runtime-release"
WEB_EXPORT_BLOCKED_REASON = "Empacotamento Web ainda não implementado (marco F)."

_MAX_ROWS_SHOWN = 30
_ENGINE_API_MODULES = frozenset(("Range", "mathutils", "bgl", "blf", "aud"))
_SEVERITY_ICONS = {'ERROR': 'CANCEL', 'WARNING': 'ERROR', 'INFO': 'INFO'}

# Onde procurar o runtime instalado: variável de ambiente e, em árvore de desenvolvimento,
# a saída dos presets web-runtime*. Sem layout de instalação definido (marco F).
_DEV_RUNTIME_DIRS = {"web-runtime-release": "build-web-release/bin", "web-runtime": "build-web/bin"}


def _runtime_candidates():
    import os
    dirs = []
    env = os.environ.get("RANGE_WEB_RUNTIME_DIR")
    if env:
        dirs.append(env)
    rel = _DEV_RUNTIME_DIRS.get(bpy.context.scene.range_web.runtime_id)
    here = os.path.dirname(os.path.abspath(__file__))
    while rel and here != os.path.dirname(here):
        here = os.path.dirname(here)
        candidate = os.path.join(here, rel)
        if os.path.isdir(candidate):
            dirs.append(candidate)
            break
    return dirs


# Último Report da validação. Transitório: não vai para o .blend e é descartado ao recarregar.
_last_report = None


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
        layout.operator("scene.range_web_validate", icon='FILE_REFRESH')
        self._draw_report(layout)

        layout.separator()
        col = layout.column()
        col.enabled = False
        col.label(text="Exportar Web indisponível:")
        col.label(text=WEB_EXPORT_BLOCKED_REASON)
        layout.label(text="Prévia desktop (tecla P) não é Teste Web.")

    @staticmethod
    def _draw_report(layout):
        # Só lê o resultado guardado; a coleta roda no operador, nunca aqui.
        report = _last_report
        if report is None:
            layout.label(text="Nenhuma verificação executada.", icon='INFO')
            return
        layout.label(text=report.summary(), icon='CANCEL' if report.errors else 'FILE_TICK')
        layout.label(text="Resultado da última validação; revalide após editar.")
        for index, finding in enumerate(report.findings[:_MAX_ROWS_SHOWN]):
            box = layout.box()
            row = box.row()
            row.label(text="%s  %s" % (finding.rule_id, finding.message),
                      icon=_SEVERITY_ICONS[finding.severity])
            loc = finding.location
            if loc.get("object") or loc.get("scene"):
                row.operator("scene.range_web_locate", text="Localizar").index = index
            if loc.get("chain"):
                box.label(text=loc["chain"])
            if finding.fix:
                box.label(text=finding.fix)
        hidden = len(report.findings) - _MAX_ROWS_SHOWN
        if hidden > 0:
            layout.label(text="... e mais %d resultado(s)." % hidden)


class SCENE_OT_range_web_validate(Operator):
    """Analisa cenas, controllers, scripts e assets do arquivo contra o perfil Web"""
    bl_idname = "scene.range_web_validate"
    bl_label = "Validar Web"

    def execute(self, context):
        global _last_report
        import sys
        from range_web import collect_bpy, runtime

        # Com manifesto do runtime, os módulos Python vêm dele. Sem manifesto (WEB-PKG-001 já
        # vai no relatório), a biblioteca padrão do interpretador em uso serve de aproximação
        # para WEB-PY-001/PKG-003; os módulos da API do motor (KX_PythonInit.cpp) contam como presentes.
        info = runtime.find_runtime(context.scene.range_web.runtime_id, _runtime_candidates())
        stdlib = info.python_modules()
        if stdlib is None:
            stdlib = set(sys.stdlib_module_names) | set(sys.builtin_module_names) | _ENGINE_API_MODULES
        _last_report = collect_bpy.collect_report(stdlib=stdlib)
        _last_report.extend(info.findings)
        self.report({'WARNING' if _last_report.errors else 'INFO'}, _last_report.summary())
        return {'FINISHED'}


class SCENE_OT_range_web_locate(Operator):
    """Seleciona a origem do resultado (cena e objeto)"""
    bl_idname = "scene.range_web_locate"
    bl_label = "Localizar"

    index: bpy.props.IntProperty(options={'HIDDEN', 'SKIP_SAVE'})

    def execute(self, context):
        report = _last_report
        if report is None or not (0 <= self.index < len(report.findings)):
            self.report({'WARNING'}, "Resultado desatualizado; valide novamente.")
            return {'CANCELLED'}
        loc = report.findings[self.index].location
        scene = bpy.data.scenes.get(loc.get("scene", ""))
        if scene is not None and context.screen is not None:
            context.screen.scene = scene
        scene = scene or context.scene
        ob = scene.objects.get(loc.get("object", ""))
        if ob is None:
            self.report({'INFO'}, loc.get("chain") or "Origem fora das cenas (objeto do pool de spawn).")
            return {'FINISHED'}
        for other in scene.objects:
            other.select = False
        ob.select = True
        scene.objects.active = ob
        self.report({'INFO'}, loc.get("chain", ob.name))
        return {'FINISHED'}


classes = (
    RangeWebSettings,
    SCENE_OT_range_web_validate,
    SCENE_OT_range_web_locate,
    SCENE_PT_range_web,
)

if __name__ == "__main__":  # only for live edit.
    from bpy.utils import register_module
    register_module(__name__)
