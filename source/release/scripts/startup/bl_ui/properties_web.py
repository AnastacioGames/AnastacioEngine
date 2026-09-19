# Perfil Web da Range Engine (marco A de docs/web-profile-validation-plan.md).
# Somente autoria: guarda configuracoes e mostra o estado. Nao faz I/O no draw()
# e ainda nao valida nem exporta; o botao Exportar Web fica indisponivel com motivo unico.

import bpy
from bpy.types import Operator, Panel, PropertyGroup

from .properties_scene import SceneButtonsPanel

WEB_SCHEMA_VERSION = 1
WEB_RUNTIME_ID = "web-runtime-release"
WEB_EXPORT_BLOCKED_REASON = "Exporte a partir de uma árvore de desenvolvimento com tools/web/package-web.py."

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


def _packager_path():
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    while here != os.path.dirname(here):
        here = os.path.dirname(here)
        candidate = os.path.join(here, "tools", "web", "package-web.py")
        if os.path.isfile(candidate):
            return candidate
    return None


def _run_validation(context):
    """Coleta e valida agora; é o único caminho usado pelo botão Validar e pelo Exportar."""
    import sys
    from range_web import collect_bpy, runtime

    # Com manifesto do runtime, os módulos Python vêm dele. Sem manifesto (WEB-PKG-001 já
    # vai no relatório), a biblioteca padrão do interpretador em uso serve de aproximação
    # para WEB-PY-001/PKG-003; os módulos da API do motor (KX_PythonInit.cpp) contam como presentes.
    info = runtime.find_runtime(context.scene.range_web.runtime_id, _runtime_candidates())
    stdlib = info.python_modules()
    if stdlib is None:
        stdlib = set(sys.stdlib_module_names) | set(sys.builtin_module_names) | _ENGINE_API_MODULES
    report = collect_bpy.collect_report(stdlib=stdlib)
    report.extend(info.findings)
    return report, info


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
        layout.operator("scene.range_web_export", icon='EXPORT')
        layout.label(text="Prévia desktop (tecla P) não é Teste Web.")
        layout.operator("scene.range_web_import_preflight", icon='FILE_FOLDER')

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
        _last_report, _info = _run_validation(context)
        self.report({'WARNING' if _last_report.errors else 'INFO'}, _last_report.summary())
        return {'FINISHED'}


class SCENE_OT_range_web_export(Operator):
    """Valida de novo e gera o pacote Web; erros bloqueiam e o export anterior é preservado"""
    bl_idname = "scene.range_web_export"
    bl_label = "Exportar Web"

    def execute(self, context):
        global _last_report
        import os
        import shutil
        import subprocess
        import sys
        import tempfile
        from range_web import export

        web = context.scene.range_web
        # Em modo background is_dirty nunca zera (não há janela para reiniciá-lo).
        if not bpy.data.filepath or (bpy.data.is_dirty and not bpy.app.background):
            self.report({'WARNING'}, "Salve o arquivo antes de exportar: o pacote usa o .range salvo.")
            return {'CANCELLED'}
        packager = _packager_path()
        python = shutil.which("python") or shutil.which("python3")
        if packager is None or python is None:
            self.report({'WARNING'}, WEB_EXPORT_BLOCKED_REASON)
            return {'CANCELLED'}

        _last_report, info = _run_validation(context)
        if not info.usable:
            self.report({'WARNING'}, "Runtime Web indisponível; veja WEB-PKG-001 no relatório.")
            return {'CANCELLED'}
        dest = bpy.path.abspath(web.output_directory)
        game = bpy.data.filepath
        from range_web import collect_bpy
        extras = collect_bpy.collect_extra_files()

        def build(out):
            with tempfile.TemporaryDirectory() as scratch:
                name = "pkg"
                game_copy = os.path.join(scratch, os.path.splitext(os.path.basename(game))[0] + ".range")
                shutil.copy2(game, game_copy)
                cmd = [python, packager, "--game", game_copy, "--name", name,
                       "--runtime-dir", info.directory, "--out-dir", scratch]
                cmd += ["--extra-root", collect_bpy.project_root()]
                for extra in extras:
                    cmd += ["--extra", extra]
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    raise RuntimeError(result.stderr.strip() or "empacotador falhou")
                for entry in os.listdir(os.path.join(scratch, name)):
                    shutil.move(os.path.join(scratch, name, entry), os.path.join(out, entry))

        try:
            export.export_package(_last_report, dest, build)
        except export.ExportBlocked as exc:
            self.report({'WARNING'}, "%s Corrija e valide novamente." % exc)
            return {'CANCELLED'}
        except Exception as exc:
            self.report({'WARNING'}, "Export falhou; o anterior foi preservado: %s" % exc)
            return {'CANCELLED'}
        self.report({'INFO'}, "Pacote Web gerado em %s" % dest)
        return {'FINISHED'}


class SCENE_OT_range_web_import_preflight(Operator):
    """Lê o relatório de pré-voo (JSON) do pacote no navegador e junta os resultados ao relatório"""
    bl_idname = "scene.range_web_import_preflight"
    bl_label = "Importar pré-voo Web"

    filepath: bpy.props.StringProperty(subtype='FILE_PATH', options={'HIDDEN', 'SKIP_SAVE'})
    filter_glob: bpy.props.StringProperty(default="*.json", options={'HIDDEN'})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        global _last_report
        from range_web import preflight, results

        # Pré-voo descreve um pacote já publicado; o Exportar revalida e não o reaproveita.
        if _last_report is None:
            _last_report = results.Report()
        _last_report.findings = [f for f in _last_report.findings
                                 if f.location.get("origin") != "preflight"]
        found = preflight.load_preflight(bpy.path.abspath(self.filepath))
        for finding in found:
            finding.location["origin"] = "preflight"
        _last_report.extend(found)
        self.report({'WARNING' if found else 'INFO'},
                    "Pré-voo: %d problema(s)." % len(found) if found else "Pré-voo sem problemas.")
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
    SCENE_OT_range_web_export,
    SCENE_PT_range_web,
)

if __name__ == "__main__":  # only for live edit.
    from bpy.utils import register_module
    register_module(__name__)
