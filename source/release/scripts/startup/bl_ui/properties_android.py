# Export Android da Range Engine (A4 de docs/android-export-plan.md), ao lado do painel Web.
# So guarda as configuracoes e chama range_web/android.py, o mesmo modulo de tools/web/package-android.py.
# Gradle e adb rodam numa thread; um operador modal acompanha para o editor nao travar.

import bpy
from bpy.types import Operator, Panel, PropertyGroup

from bpy.app.translations import pgettext_iface as _

from .properties_scene import SceneButtonsPanel

# Trabalho em andamento (gerar ou instalar). Transitorio: nao vai para o .blend.
_job = None
# Ultimo aviso/erro, mostrado no painel (o report da barra do topo some rapido).
_last_message = None


class _Job:
    def __init__(self, label, func):
        import threading
        self.label = label
        self.lines = []
        self.result = None
        self.error = None
        self.thread = threading.Thread(target=self._run, args=(func,), daemon=True)

    def log(self, line):
        print("[android] " + line)
        self.lines.append(line)

    def _run(self, func):
        try:
            self.result = func(self.log)
        except Exception as exc:  # AndroidError e falhas inesperadas voltam como mensagem ao usuario.
            self.error = exc

    def message(self):
        from range_web.i18n import tr
        return tr(self.error.args[0]) if self.error and self.error.args else str(self.error)


def _output_dir(context):
    return bpy.path.abspath(context.scene.range_android.output_directory)


def _config(context):
    import os
    from range_web import android

    settings = context.scene.range_android
    name = settings.app_name.strip() or os.path.splitext(os.path.basename(bpy.data.filepath))[0]
    config = dict(android.DEFAULTS)
    config.update({
        "applicationId": settings.application_id.strip(),
        "appName": name,
        "versionName": settings.version_name.strip(),
        "versionCode": settings.version_code,
        "icon": bpy.path.abspath(settings.icon) if settings.icon else "",
        "orientation": settings.orientation.lower(),
        "buildType": settings.build_type.lower(),
        "keystore": bpy.path.abspath(settings.keystore) if settings.keystore else "",
        "keyAlias": settings.key_alias.strip(),
        "aab": settings.aab,
    })
    return config


def _last_build(context):
    """(apk, applicationId) da ultima geracao no destino, pelo android-report.json; ou None."""
    import json
    import os
    from range_web import android

    out = _output_dir(context)
    try:
        with open(os.path.join(out, android.REPORT_NAME), encoding="utf-8") as f:
            report = json.load(f)
        apk = os.path.join(out, report["apk"]["file"])
        app_id = report["config"]["applicationId"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return (apk, app_id) if os.path.isfile(apk) else None


def _toolchain(context):
    from range_web import android
    settings = context.scene.range_android
    return android.find_toolchain(bpy.path.abspath(settings.jdk_directory),
                                  bpy.path.abspath(settings.sdk_directory))


def _redraw(context):
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'PROPERTIES':
                area.tag_redraw()


def _wrap(text, width=60):
    import textwrap
    return textwrap.wrap(text, width) or [text]


class _JobOperator:
    """Roda `self.work(log)` numa thread e acompanha por timer; em modo background roda direto."""

    def start(self, context, label, work):
        global _job, _last_message
        _last_message = None
        _job = _Job(label, work)
        if bpy.app.background:
            _job._run(work)
            return self.finish(context)
        _job.thread.start()
        self._timer = context.window_manager.event_timer_add(0.5, context.window)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type != 'TIMER':
            return {'PASS_THROUGH'}
        _redraw(context)
        if _job.thread.is_alive():
            return {'PASS_THROUGH'}
        context.window_manager.event_timer_remove(self._timer)
        return self.finish(context)

    def warn(self, context, message):
        global _last_message
        _last_message = ('ERROR', message)
        self.report({'WARNING'}, message)
        _redraw(context)
        return {'CANCELLED'}

    def finish(self, context):
        global _job, _last_message
        job, _job = _job, None
        if job.error is not None:
            return self.warn(context, job.message())
        _last_message = ('INFO', self.done_message(job.result))
        self.report({'INFO'}, _last_message[1])
        _redraw(context)
        return {'FINISHED'}


class RangeAndroidSettings(PropertyGroup):
    application_id: bpy.props.StringProperty(
        name="App ID",
        description="Unique app identifier, for example com.yourstudio.yourgame. "
                    "Do not change it after publishing: the phone would treat it as another app and the save is lost",
        default="",
    )
    app_name: bpy.props.StringProperty(
        name="App name",
        description="Name shown under the icon on the phone; empty uses the file name",
        default="",
    )
    version_name: bpy.props.StringProperty(
        name="App version",
        description="Version shown to the player, for example 1.0",
        default="1.0",
    )
    version_code: bpy.props.IntProperty(
        name="Version code",
        description="Integer that must increase with each version for the phone to accept the update",
        default=1, min=1, max=2100000000,
    )
    icon: bpy.props.StringProperty(
        name="App icon",
        description="PNG image of the app icon (square, 512x512 recommended); empty uses the Android default",
        subtype='FILE_PATH',
        default="",
    )
    orientation: bpy.props.EnumProperty(
        name="Screen orientation",
        items=(
            ('AUTO', "Automatic", "Landscape and portrait by the sensor, respecting the system rotation lock"),
            ('LANDSCAPE', "Landscape", "Landscape only (both sides)"),
            ('PORTRAIT', "Portrait", "Portrait only"),
        ),
        default='AUTO',
    )
    build_type: bpy.props.EnumProperty(
        name="Build type",
        items=(
            ('DEBUG', "Debug", "For testing on your phone; allows remote inspection (chrome://inspect)"),
            ('RELEASE', "Release", "Signed with your key, for distribution to players"),
        ),
        default='DEBUG',
    )
    keystore: bpy.props.StringProperty(
        name="Signing key",
        description="Key file (.jks) of the release, outside git and with a backup. "
                    "Updates only install if signed with the same key: losing it means publishing as a new app",
        subtype='FILE_PATH',
        default="",
    )
    key_alias: bpy.props.StringProperty(
        name="Key alias",
        description="Name of the key inside the key file",
        default="upload",
    )
    aab: bpy.props.BoolProperty(
        name="Also build AAB (Google Play)",
        description="Also generates the .aab bundle signed with the same key, the format Google Play requires; "
                    "the APK is still built for installing on your phone",
        default=False,
    )
    output_directory: bpy.props.StringProperty(
        name="Destination",
        description="Folder of the APK (and AAB), android-export.json, report and Gradle log",
        subtype='DIR_PATH',
        default="//android/",
    )
    jdk_directory: bpy.props.StringProperty(
        name="JDK",
        description="JDK folder; only used if JAVA_HOME and Android Studio are not found",
        subtype='DIR_PATH',
        default="",
    )
    sdk_directory: bpy.props.StringProperty(
        name="Android SDK",
        description="Android SDK folder; only used if ANDROID_HOME and Android Studio are not found",
        subtype='DIR_PATH',
        default="",
    )


class SCENE_PT_range_android(SceneButtonsPanel, Panel):
    bl_label = "Android (Range)"
    COMPAT_ENGINES = {'BLENDER_GAME'}
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        settings = context.scene.range_android

        col = layout.column()
        col.prop(settings, "application_id")
        col.prop(settings, "app_name")
        row = col.row(align=True)
        row.prop(settings, "version_name")
        row.prop(settings, "version_code")
        col.prop(settings, "icon")
        col.prop(settings, "orientation")
        col.prop(settings, "build_type")
        if settings.build_type == 'RELEASE':
            box = col.box()
            box.prop(settings, "keystore")
            box.prop(settings, "key_alias")
            box.prop(context.window_manager, "range_android_password")
            box.prop(settings, "aab")
            box.operator("scene.range_android_create_key", icon='KEY_HLT')
            box.label(text="Keep the key and the password with a backup: updates need the same key.",
                      icon='INFO')
        col.prop(settings, "output_directory")
        # Mesma propriedade do painel Web: o APK embute o pacote Web com o controle na tela dele.
        col.prop(context.scene.range_web, "touch_layout")

        box = layout.box()
        box.label(text="Tools (only if not found automatically):")
        box.prop(settings, "jdk_directory")
        box.prop(settings, "sdk_directory")

        layout.separator()
        layout.label(text="Uses the package from the Web panel; exports it again if it is outdated.")
        busy = _job is not None
        row = layout.row()
        row.enabled = not busy
        row.operator("scene.range_android_build", icon='EXPORT')
        # Instalar so libera com um APK gerado no destino; o motivo aparece em vez de um clique mudo.
        last = _last_build(context)
        row = layout.row()
        row.enabled = not busy and last is not None
        row.operator("scene.range_android_install", icon='PLAY')
        if busy:
            layout.label(text=_(_job.label) + "...", icon='TIME')
            if _job.lines:
                layout.label(text=_job.lines[-1])
        elif _last_message is not None:
            icon, text = _last_message
            for line in _wrap(text):
                layout.label(text=line, icon=icon)
                icon = 'NONE'
        elif last is None:
            layout.label(text="No APK in the destination yet.", icon='INFO')


class SCENE_OT_range_android_build(_JobOperator, Operator):
    """Builds the APK from the Web package with Gradle (JDK and Android SDK of Android Studio)"""
    bl_idname = "scene.range_android_build"
    bl_label = "Build APK"

    @classmethod
    def poll(cls, context):
        return _job is None

    def execute(self, context):
        import os
        from range_web import android, local_server
        from range_web.i18n import tr

        if not bpy.data.filepath:
            return self.warn(context, _("Save the file before exporting: the package uses the saved .range."))
        config = _config(context)
        problems = android.config_problems(config)
        if problems:
            return self.warn(context, tr(problems[0]))
        try:
            toolchain = _toolchain(context)
        except android.AndroidError as exc:
            return self.warn(context, tr(exc.args[0]))
        # Preencher o painel ja deixa o arquivo "modificado"; salva como o Ctrl+S para o pacote usar o .range atual.
        # Em modo background is_dirty nunca zera.
        if config["buildType"] == "release":
            problem = android.password_problem(context.window_manager.range_android_password
                                               or os.environ.get(android.PASSWORD_ENV, ""))
            if problem:
                return self.warn(context, tr(problem))
        if bpy.data.is_dirty and not bpy.app.background:
            if bpy.ops.wm.save_mainfile() != {'FINISHED'}:
                return self.warn(context, _("Save the file before exporting: the package uses the saved .range."))

        web_dir = bpy.path.abspath(context.scene.range_web.output_directory)
        if local_server.package_problem(web_dir, bpy.data.filepath):
            # Pacote Web ausente ou mais velho que o .range: o export Web valida e gera de novo.
            if bpy.ops.scene.range_web_export() != {'FINISHED'}:
                return self.warn(context, _("Web export failed; see the Web (Range) panel."))
        out_dir = _output_dir(context)
        password = context.window_manager.range_android_password

        def work(log):
            return android.build_apk(web_dir, config, out_dir, toolchain, log=log, password=password)

        return self.start(context, "Building APK", work)

    def done_message(self, apk):
        return _("APK generated at %s") % apk


class SCENE_OT_range_android_install(_JobOperator, Operator):
    """Installs the last APK on the phone connected by USB (adb), keeping the save, and opens the game"""
    bl_idname = "scene.range_android_install"
    bl_label = "Install on phone"

    @classmethod
    def poll(cls, context):
        return _job is None and _last_build(context) is not None

    def execute(self, context):
        from range_web import android
        from range_web.i18n import tr

        apk, app_id = _last_build(context)
        try:
            toolchain = _toolchain(context)
        except android.AndroidError as exc:
            return self.warn(context, tr(exc.args[0]))

        def work(log):
            return android.install_apk(apk, app_id, toolchain, log=log)

        return self.start(context, "Installing on phone", work)

    def done_message(self, serial):
        return _("Installed on %s and opened.") % serial


class SCENE_OT_range_android_create_key(Operator):
    """Creates the release signing key with the JDK keytool, in the file chosen in Signing key"""
    bl_idname = "scene.range_android_create_key"
    bl_label = "Create key"

    def execute(self, context):
        import os
        from range_web import android
        from range_web.i18n import tr

        settings = context.scene.range_android
        path = bpy.path.abspath(settings.keystore) if settings.keystore else ""
        if not path:
            # Padrao fora do projeto: pasta do usuario, um arquivo por app.
            app = settings.application_id.strip() or "range-game"
            path = os.path.join(os.path.expanduser("~"), "RangeAndroidKeys", app + ".jks")
        name = _config(context)["appName"]
        try:
            android.create_keystore(path, settings.key_alias.strip(), context.window_manager.range_android_password,
                                    name, _toolchain(context))
        except android.AndroidError as exc:
            return _JobOperator.warn(self, context, tr(exc.args[0]))
        settings.keystore = path
        global _last_message
        _last_message = ('INFO', _("Key created at %s. Back up the file and the password.") % path)
        self.report({'INFO'}, _last_message[1])
        return {'FINISHED'}


classes = (
    RangeAndroidSettings,
    SCENE_OT_range_android_create_key,
    SCENE_OT_range_android_build,
    SCENE_OT_range_android_install,
    SCENE_PT_range_android,
)

if __name__ == "__main__":  # only for live edit.
    from bpy.utils import register_module
    register_module(__name__)
