# Perfil Web da Range Engine (marco A de docs/web-profile-validation-plan.md).
# Somente autoria: guarda configuracoes e mostra o estado. Nao faz I/O no draw()
# e ainda nao valida nem exporta; o botao Exportar Web fica indisponivel com motivo unico.

import bpy
from bpy.types import Operator, Panel, PropertyGroup

from bpy.app.translations import pgettext_iface as _

from .properties_scene import SceneButtonsPanel

WEB_SCHEMA_VERSION = 1
WEB_RUNTIME_ID = "web-runtime-release"
WEB_EXPORT_BLOCKED_REASON = "Export from a development tree with tools/web/package-web.py."

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
    report = collect_bpy.collect_report(stdlib=stdlib, touch_layout=context.scene.range_web.touch_layout.lower())
    report.extend(info.findings)
    return report, info


def _merge_preflight(report, package_dir):
    """Roda o pré-voo no navegador sobre o pacote e junta os achados ao relatório.

    Devolve a mensagem para o usuário; falha de ambiente (sem navegador, sem resposta)
    nunca vira erro do jogo."""
    from range_web import preflight_run

    found, why = preflight_run.run_preflight(package_dir)
    report.findings = [f for f in report.findings if f.location.get("origin") != "preflight"]
    if found is None:
        return _("Preflight not run: %s") % why
    for finding in found:
        finding.location["origin"] = "preflight"
    report.extend(found)
    return _("Preflight: %d problem(s).") % len(found) if found else _("Preflight found no problems.")


def _package_dir(context):
    return bpy.path.abspath(context.scene.range_web.output_directory)


def _serve_blocked_reason(context):
    """None se 'Abrir no navegador' pode rodar; senão o motivo (mostrado no painel)."""
    from range_web import local_server
    return local_server.package_problem(_package_dir(context), bpy.data.filepath or None)


def _preflight_blocked_reason(context):
    from range_web import local_server, preflight_run
    why = local_server.package_problem(_package_dir(context))
    if why:
        return why
    if preflight_run.find_browser() is None:
        return _("Chrome or Edge not found for the automatic test.")
    return None


def _open_in_browser(package_dir, source_file):
    """Sobe o servidor local e abre o navegador padrão. Devolve (ok, mensagem para o usuário)."""
    import webbrowser
    from range_web import local_server

    why = local_server.package_problem(package_dir, source_file)
    if why:
        return False, why
    try:
        url = local_server.start(package_dir)
    except OSError as exc:
        return False, _("Could not start the local server: %s") % exc
    if not bpy.app.background:
        webbrowser.open(url)
    return True, _("Serving at %s (click Play on the page).") % url


# Último Report da validação. Transitório: não vai para o .blend e é descartado ao recarregar.
_last_report = None


class RangeWebSettings(PropertyGroup):
    schema_version: bpy.props.IntProperty(
        name="Schema",
        description="Version of the Web profile settings",
        default=WEB_SCHEMA_VERSION,
        options={'HIDDEN'},
    )
    check_compatibility: bpy.props.BoolProperty(
        name="Check Web compatibility",
        description="Shows Web compatibility warnings while editing. "
                    "Web export always validates, regardless of this option",
        default=False,
    )
    runtime_id: bpy.props.StringProperty(
        name="Runtime",
        description="Web runtime used in the package; availability is checked on export",
        default=WEB_RUNTIME_ID,
    )
    entry_scene: bpy.props.StringProperty(
        name="Entry scene",
        description="Initial scene of the Web package; empty uses the current scene",
        default="",
    )
    auto_preflight: bpy.props.BoolProperty(
        name="Preflight after export",
        description="After exporting, opens the package in a windowless Chrome/Edge (about 15 s) "
                    "and adds the problems seen in the browser to the report",
        default=True,
    )
    open_after_export: bpy.props.BoolProperty(
        name="Open after export",
        description="After exporting, starts a local server and opens the game in the default browser",
        default=False,
    )
    output_directory: bpy.props.StringProperty(
        name="Destination",
        description="Output directory of the Web package",
        subtype='DIR_PATH',
        default="//web/",
    )
    # Controle na tela (A1): vale para o Web e para o APK, que embute este pacote.
    touch_layout: bpy.props.EnumProperty(
        name="Touch controls",
        description="On-screen controls shown on touch screens (phones, tablets and the Android app)",
        items=(
            ('NONE', "None", "No on-screen controls; taps reach the game as mouse clicks"),
            ('STICK', "Stick + 2 buttons", "Left stick and A/B buttons, as gamepad 0"),
            ('DPAD', "D-pad + 4 buttons", "D-pad and A/B/X/Y buttons, as gamepad 0"),
            ('TWIN', "Two sticks", "Left and right sticks, as gamepad 0"),
            ('WASD', "Stick as WASD + Space", "For games that read the keyboard: the stick presses W/A/S/D "
                                               "and the button presses Space"),
            ('ARROWS', "D-pad as arrows + Space/Enter", "For games that read the keyboard: the d-pad presses "
                                                         "the arrow keys and the buttons press Space and Enter"),
        ),
        default='STICK',
    )
    touch_stick: bpy.props.EnumProperty(
        name="Stick mode",
        description="Where the on-screen stick appears",
        items=(
            ('DYNAMIC', "Where the finger touches", "The stick appears under the finger, anywhere on its half of the screen"),
            ('FIXED', "In the corner", "The stick stays in the corner"),
        ),
        default='DYNAMIC',
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
        col.prop(web, "auto_preflight")
        col.prop(web, "open_after_export")

        box = layout.box()
        box.prop(web, "touch_layout")
        row = box.row()
        row.enabled = web.touch_layout in {'STICK', 'TWIN', 'WASD'}
        row.prop(web, "touch_stick", expand=True)
        box.label(text="Shown only on touch screens; test on a PC with ?touch=1 in the address.", icon='INFO')

        layout.separator()
        layout.operator("scene.range_web_validate", icon='FILE_REFRESH')
        self._draw_report(layout)

        layout.separator()
        layout.operator("scene.range_web_export", icon='EXPORT')
        layout.label(text="Desktop preview (P key) is not a Web test.")
        from range_web import local_server
        # Botões só liberam com o ambiente pronto; o motivo aparece em vez de um clique mudo.
        why = _serve_blocked_reason(context)
        row = layout.row()
        row.enabled = why is None
        row.operator("scene.range_web_serve", icon='URL')
        why_pre = _preflight_blocked_reason(context)
        row = layout.row()
        row.enabled = why_pre is None
        row.operator("scene.range_web_preflight", icon='PLAY')
        for reason in {why, why_pre} - {None}:
            layout.label(text=reason, icon='INFO')
        served = local_server.url()
        if served:
            layout.label(text=_("Serving at %s") % served, icon='WORLD')
            layout.operator("scene.range_web_stop_server", icon='PAUSE')
        layout.operator("scene.range_web_import_preflight", icon='FILE_FOLDER')

    @staticmethod
    def _draw_report(layout):
        from range_web.i18n import tr
        # Só lê o resultado guardado; a coleta roda no operador, nunca aqui.
        report = _last_report
        if report is None:
            layout.label(text="No check has been run.", icon='INFO')
            return
        layout.label(text=report.summary(), icon='CANCEL' if report.errors else 'FILE_TICK')
        layout.label(text="Result of the last validation; revalidate after editing.")
        for index, finding in enumerate(report.findings[:_MAX_ROWS_SHOWN]):
            box = layout.box()
            row = box.row()
            # Mensagens do runtime trazem quebras de linha; o label as desenharia como quadrados.
            lines = "%s  %s" % (finding.rule_id, tr(finding.message))
            head, *rest = lines.splitlines() or [""]
            row.label(text=head, icon=_SEVERITY_ICONS[finding.severity])
            loc = finding.location
            if loc.get("object") or loc.get("scene"):
                row.operator("scene.range_web_locate", text="Locate").index = index
            if loc.get("chain"):
                box.label(text=loc["chain"])
            if finding.fix:
                rest += tr(finding.fix).splitlines()
            for line in rest:
                if line.strip():
                    box.label(text=line)
        hidden = len(report.findings) - _MAX_ROWS_SHOWN
        if hidden > 0:
            layout.label(text=_("... and %d more result(s).") % hidden)


class SCENE_OT_range_web_validate(Operator):
    """Analyzes the file's scenes, controllers, scripts and assets against the Web profile"""
    bl_idname = "scene.range_web_validate"
    bl_label = "Validate Web"

    def execute(self, context):
        global _last_report
        # O pré-voo importado descreve o pacote no navegador, não o .blend; sobrevive a um novo Validar.
        kept = [f for f in (_last_report.findings if _last_report else [])
                if f.location.get("origin") == "preflight"]
        _last_report, _info = _run_validation(context)
        _last_report.extend(kept)
        self.report({'WARNING' if _last_report.errors else 'INFO'}, _last_report.summary())
        return {'FINISHED'}


class SCENE_OT_range_web_export(Operator):
    """Validates again and generates the Web package; errors block it and the previous export is preserved"""
    bl_idname = "scene.range_web_export"
    bl_label = "Export Web"

    def execute(self, context):
        global _last_report
        import os
        import shutil
        import subprocess
        import sys
        import tempfile
        from range_web import export
        from range_web.i18n import tr

        web = context.scene.range_web
        # Em modo background is_dirty nunca zera (não há janela para reiniciá-lo).
        if not bpy.data.filepath or (bpy.data.is_dirty and not bpy.app.background):
            self.report({'WARNING'}, _("Save the file before exporting: the package uses the saved .range."))
            return {'CANCELLED'}
        packager = _packager_path()
        python = shutil.which("python") or shutil.which("python3")
        if packager is None or python is None:
            self.report({'WARNING'}, _(WEB_EXPORT_BLOCKED_REASON))
            return {'CANCELLED'}

        _last_report, info = _run_validation(context)
        if not info.usable:
            self.report({'WARNING'}, _("Web runtime unavailable; see WEB-PKG-001 in the report."))
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
                cmd += ["--touch-layout", web.touch_layout.lower(), "--touch-stick", web.touch_stick.lower()]
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
            self.report({'WARNING'}, _("%s Fix and validate again.") % tr(exc.args[0]))
            return {'CANCELLED'}
        except Exception as exc:
            self.report({'WARNING'}, _("Export failed; the previous one was preserved: %s") % exc)
            return {'CANCELLED'}
        message = _("Web package generated at %s") % dest
        if web.auto_preflight:
            message += ". " + _merge_preflight(_last_report, dest)
        if web.open_after_export and not bpy.app.background and not _last_report.errors:
            message += ". " + _open_in_browser(dest, None)[1]
        self.report({'WARNING' if _last_report.errors else 'INFO'}, message)
        return {'FINISHED'}


class SCENE_OT_range_web_preflight(Operator):
    """Opens the exported package in a windowless Chrome/Edge and adds what the browser saw to the report (about 15 s)"""
    bl_idname = "scene.range_web_preflight"
    bl_label = "Test package in browser"

    @classmethod
    def poll(cls, context):
        return _preflight_blocked_reason(context) is None

    def execute(self, context):
        global _last_report
        from range_web import results

        dest = bpy.path.abspath(context.scene.range_web.output_directory)
        if _last_report is None:
            _last_report = results.Report()
        message = _merge_preflight(_last_report, dest)
        self.report({'WARNING' if _last_report.errors else 'INFO'}, message)
        return {'FINISHED'}


class SCENE_OT_range_web_serve(Operator):
    """Starts a local server with the exported package and opens the game in the default browser"""
    bl_idname = "scene.range_web_serve"
    bl_label = "Open in browser"

    @classmethod
    def poll(cls, context):
        return _serve_blocked_reason(context) is None

    def execute(self, context):
        dest = bpy.path.abspath(context.scene.range_web.output_directory)
        ok, message = _open_in_browser(dest, bpy.data.filepath)
        self.report({'INFO' if ok else 'WARNING'}, message)
        return {'FINISHED' if ok else 'CANCELLED'}


class SCENE_OT_range_web_stop_server(Operator):
    """Stops the local server of the Web package"""
    bl_idname = "scene.range_web_stop_server"
    bl_label = "Stop server"

    def execute(self, context):
        from range_web import local_server
        local_server.stop()
        self.report({'INFO'}, _("Local server stopped."))
        return {'FINISHED'}


class SCENE_OT_range_web_import_preflight(Operator):
    """Reads the preflight report (JSON) of the package in the browser and adds the results to the report"""
    bl_idname = "scene.range_web_import_preflight"
    bl_label = "Import Web preflight"

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
                    _("Preflight: %d problem(s).") % len(found) if found else _("Preflight found no problems."))
        return {'FINISHED'}


class SCENE_OT_range_web_locate(Operator):
    """Selects the origin of the result (scene and object)"""
    bl_idname = "scene.range_web_locate"
    bl_label = "Locate"

    index: bpy.props.IntProperty(options={'HIDDEN', 'SKIP_SAVE'})

    def execute(self, context):
        report = _last_report
        if report is None or not (0 <= self.index < len(report.findings)):
            self.report({'WARNING'}, _("Stale result; validate again."))
            return {'CANCELLED'}
        loc = report.findings[self.index].location
        scene = bpy.data.scenes.get(loc.get("scene", ""))
        if scene is not None and context.screen is not None:
            context.screen.scene = scene
        scene = scene or context.scene
        ob = scene.objects.get(loc.get("object", ""))
        if ob is None:
            self.report({'INFO'}, loc.get("chain") or _("Origin outside the scenes (spawn pool object)."))
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
    SCENE_OT_range_web_preflight,
    SCENE_OT_range_web_serve,
    SCENE_OT_range_web_stop_server,
    SCENE_OT_range_web_import_preflight,
    SCENE_PT_range_web,
)

if __name__ == "__main__":  # only for live edit.
    from bpy.utils import register_module
    register_module(__name__)
