# Export Android (A3/A4 de docs/android-export-plan.md): transforma o pacote do export Web num APK.
# Nucleo sem bpy: o painel (bl_ui/properties_android.py) e tools/web/package-android.py so chamam este modulo.
# Copia tools/android/webview-template para uma pasta temporaria, poe o jogo em assets/www, aplica
# android-export.json e roda o Gradle. JDK e Android SDK nao vem com a engine e nunca sao instalados aqui.

import datetime
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

from .i18n import Msg

CONFIG_NAME = "android-export.json"
REPORT_NAME = "android-report.json"
GRADLE_LOG_NAME = "gradle.log"
SCHEMA_VERSION = 1

# Ligados ao template: namespace do codigo Kotlin (nao muda com o applicationId) e compileSdk.
TEMPLATE_NAMESPACE = "com.anastaciogames.rangewebview"
COMPILE_SDK = 37

ORIENTATIONS = {
    # auto: paisagem e retrato pelo sensor, respeitando o bloqueio de rotacao do sistema.
    "auto": "fullUser",
    "landscape": "sensorLandscape",
    "portrait": "sensorPortrait",
}
BUILD_TYPES = ("debug", "release")

DEFAULTS = {
    "schema_version": SCHEMA_VERSION,
    "applicationId": "",
    "appName": "",
    "versionName": "1.0",
    "versionCode": 1,
    "icon": "",
    "orientation": "auto",
    "buildType": "debug",
    # Release: caminho da chave e alias. A senha nunca entra aqui (vem do ambiente ou do painel, so na sessao).
    "keystore": "",
    "keyAlias": "",
}

# Senha da chave para o terminal e para o Gradle (o template le as variaveis RANGE_ANDROID_*).
PASSWORD_ENV = "RANGE_ANDROID_KEYSTORE_PASSWORD"
MIN_PASSWORD = 6  # minimo do keytool

# Arquivos do pacote Web que so servem para hospedagem e ficam fora do APK.
_WEB_ONLY = {"serve.py", "HOSTING.md"}
_APP_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z][A-Za-z0-9_]*)+$")
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_EXE = ".exe" if os.name == "nt" else ""


class AndroidError(Exception):
    """Erro para o usuario. args[0] e um Msg (traduzido na exibicao por i18n.tr)."""


def template_dir():
    """tools/android/webview-template da arvore de desenvolvimento, ou None."""
    here = os.path.dirname(os.path.abspath(__file__))
    while here != os.path.dirname(here):
        here = os.path.dirname(here)
        candidate = os.path.join(here, "tools", "android", "webview-template")
        if os.path.isfile(os.path.join(candidate, "app", "build.gradle.kts")):
            return candidate
    return None


# --- Configuracao (android-export.json) ---

def load_config(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as exc:
        raise AndroidError(Msg("Could not read %s: %s", path, exc))
    if not isinstance(data, dict):
        raise AndroidError(Msg("Invalid %s: expected a JSON object.", path))
    config = dict(DEFAULTS)
    config.update(data)
    for key in ("icon", "keystore"):
        value = config.get(key)
        if value and not os.path.isabs(value):
            config[key] = os.path.join(os.path.dirname(os.path.abspath(path)), value)
    return config


def save_config(config, path):
    data = {key: config.get(key, DEFAULTS[key]) for key in DEFAULTS}
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def config_problems(config):
    """Lista de Msg com o que impede gerar o APK com esta configuracao (vazia = ok)."""
    problems = []
    app_id = config.get("applicationId") or ""
    if not app_id:
        problems.append(Msg("Fill in the app ID (for example com.yourstudio.yourgame)."))
    elif not _APP_ID_RE.match(app_id):
        problems.append(Msg("Invalid app ID %s: use at least two parts separated by dots, "
                            "with letters, digits and _ (for example com.yourstudio.yourgame).", app_id))
    if not (config.get("appName") or "").strip():
        problems.append(Msg("Fill in the app name."))
    if not (config.get("versionName") or "").strip():
        problems.append(Msg("Fill in the version name (for example 1.0)."))
    code = config.get("versionCode")
    if not isinstance(code, int) or isinstance(code, bool) or not 1 <= code <= 2100000000:
        problems.append(Msg("The version code must be an integer from 1 to 2100000000."))
    if config.get("orientation") not in ORIENTATIONS:
        problems.append(Msg("Invalid orientation: %s.", config.get("orientation")))
    if config.get("buildType") not in BUILD_TYPES:
        problems.append(Msg("Invalid build type: %s.", config.get("buildType")))
    elif config["buildType"] == "release":
        problems.extend(keystore_problems(config))
    icon = config.get("icon") or ""
    if icon:
        try:
            with open(icon, "rb") as f:
                is_png = f.read(8) == _PNG_SIGNATURE
        except OSError:
            problems.append(Msg("Icon not found: %s", icon))
        else:
            if not is_png:
                problems.append(Msg("The icon must be a PNG image: %s", icon))
    return problems


def inside_git(path):
    """Raiz do repositorio git que contem `path`, ou None."""
    here = os.path.dirname(os.path.abspath(path))
    while True:
        if os.path.exists(os.path.join(here, ".git")):
            return here
        parent = os.path.dirname(here)
        if parent == here:
            return None
        here = parent


def keystore_problems(config, must_exist=True):
    """O que impede usar a chave do release (vazia = ok). must_exist=False ao criar a chave."""
    problems = []
    keystore = config.get("keystore") or ""
    if not keystore:
        problems.append(Msg("Release needs a signing key: choose the key file or create one."))
    else:
        repo = inside_git(keystore)
        if repo:
            problems.append(Msg("The signing key must stay outside git repositories (%s is inside %s). "
                                "Keep it in a private folder with a backup.", keystore, repo))
        elif must_exist and not os.path.isfile(keystore):
            problems.append(Msg("Signing key not found: %s", keystore))
    if not (config.get("keyAlias") or "").strip():
        problems.append(Msg("Fill in the key alias."))
    return problems


def password_problem(password):
    if not password:
        return Msg("Type the signing key password (or set %s).", PASSWORD_ENV)
    if len(password) < MIN_PASSWORD:
        return Msg("The key password needs at least %d characters.", MIN_PASSWORD)
    return None


# --- JDK e Android SDK ---

class Toolchain:
    def __init__(self, java_home, sdk_dir, java_source, sdk_source):
        self.java_home = java_home
        self.sdk_dir = sdk_dir
        self.java_source = java_source
        self.sdk_source = sdk_source

    @property
    def adb(self):
        return os.path.join(self.sdk_dir, "platform-tools", "adb" + _EXE)

    @property
    def keytool(self):
        return os.path.join(self.java_home, "bin", "keytool" + _EXE)

    @property
    def apksigner(self):
        """apksigner do build-tools mais novo, ou None."""
        name = "apksigner.bat" if os.name == "nt" else "apksigner"
        found = glob.glob(os.path.join(self.sdk_dir, "build-tools", "*", name))

        def version(path):
            return [int(x) if x.isdigit() else 0 for x in os.path.basename(os.path.dirname(path)).split(".")]
        return max(found, key=version) if found else None

    def env(self):
        env = dict(os.environ)
        env["JAVA_HOME"] = self.java_home
        env["ANDROID_HOME"] = self.sdk_dir
        env.pop("ANDROID_SDK_ROOT", None)
        env["PATH"] = os.path.join(self.java_home, "bin") + os.pathsep + env.get("PATH", "")
        return env


def _is_jdk(path):
    return bool(path) and os.path.isfile(os.path.join(path, "bin", "java" + _EXE)) \
        and os.path.isfile(os.path.join(path, "bin", "javac" + _EXE))


def _is_sdk(path):
    return bool(path) and os.path.isdir(os.path.join(path, "platforms"))


def _studio_dirs():
    """Pastas do Android Studio instalado (registro do Windows e locais padrao)."""
    dirs = []
    if os.name == "nt":
        try:
            import winreg
            for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                try:
                    with winreg.OpenKey(hive, r"SOFTWARE\Android Studio") as key:
                        dirs.append(winreg.QueryValueEx(key, "Path")[0])
                except OSError:
                    pass
        except ImportError:
            pass
        for var in ("ProgramFiles", "ProgramW6432", "LOCALAPPDATA"):
            base = os.environ.get(var)
            if base:
                dirs.append(os.path.join(base, "Android", "Android Studio"))
                dirs.append(os.path.join(base, "Programs", "Android Studio"))
    elif sys.platform == "darwin":
        dirs += ["/Applications/Android Studio.app/Contents",
                 os.path.expanduser("~/Applications/Android Studio.app/Contents")]
    else:
        dirs += ["/opt/android-studio", "/usr/local/android-studio", os.path.expanduser("~/android-studio")]
    return [d for d in dirs if d]


def _studio_sdk_dirs():
    if os.name == "nt":
        local = os.environ.get("LOCALAPPDATA")
        return [os.path.join(local, "Android", "Sdk")] if local else []
    if sys.platform == "darwin":
        return [os.path.expanduser("~/Library/Android/sdk")]
    return [os.path.expanduser("~/Android/Sdk")]


def find_toolchain(jdk_dir="", sdk_dir="", environ=None, studio_dirs=None, studio_sdk_dirs=None):
    """Procura JDK e SDK: variaveis de ambiente, Android Studio instalado e, por ultimo, as pastas
    indicadas no painel. Levanta AndroidError com o que falta; nunca instala nada."""
    environ = os.environ if environ is None else environ
    studio_dirs = _studio_dirs() if studio_dirs is None else studio_dirs
    studio_sdk_dirs = _studio_sdk_dirs() if studio_sdk_dirs is None else studio_sdk_dirs

    jdks = [(environ.get("JAVA_HOME"), "JAVA_HOME")]
    jdks += [(os.path.join(d, "jbr"), "Android Studio") for d in studio_dirs]
    jdks += [(jdk_dir, "panel")]
    sdks = [(environ.get("ANDROID_HOME"), "ANDROID_HOME"), (environ.get("ANDROID_SDK_ROOT"), "ANDROID_SDK_ROOT")]
    sdks += [(d, "Android Studio") for d in studio_sdk_dirs]
    sdks += [(sdk_dir, "panel")]

    java = next(((p, s) for p, s in jdks if _is_jdk(p)), None)
    sdk = next(((p, s) for p, s in sdks if _is_sdk(p)), None)
    if java is None or sdk is None:
        what = Msg("JDK and Android SDK not found") if java is None and sdk is None else \
            Msg("JDK not found") if java is None else Msg("Android SDK not found")
        raise AndroidError(Msg("%s (searched JAVA_HOME/ANDROID_HOME, Android Studio and the folders in the "
                               "Android panel). Install Android Studio (it brings the JDK and the SDK) or point "
                               "to the folders in the Android panel. Nothing was installed.", what))
    toolchain = Toolchain(os.path.abspath(java[0]), os.path.abspath(sdk[0]), java[1], sdk[1])
    platforms = glob.glob(os.path.join(toolchain.sdk_dir, "platforms", "android-%d*" % COMPILE_SDK))
    if not platforms:
        raise AndroidError(Msg("The Android SDK at %s does not have platform %d. Install it in Android Studio "
                               "(SDK Manager > Android SDK Platform %d). Nothing was installed.",
                               toolchain.sdk_dir, COMPILE_SDK, COMPILE_SDK))
    if not glob.glob(os.path.join(toolchain.sdk_dir, "build-tools", "*")):
        raise AndroidError(Msg("The Android SDK at %s has no Build-Tools. Install them in Android Studio "
                               "(SDK Manager > SDK Tools). Nothing was installed.", toolchain.sdk_dir))
    return toolchain


# --- Pacote Web ---

def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_web_package(package_dir):
    """Confere o pacote do export Web pelos hashes de SHA256SUMS.txt e devolve o manifest.json."""
    sums = os.path.join(package_dir, "SHA256SUMS.txt")
    manifest_path = os.path.join(package_dir, "manifest.json")
    if not (os.path.isfile(sums) and os.path.isfile(manifest_path)
            and os.path.isfile(os.path.join(package_dir, "index.html"))):
        raise AndroidError(Msg("Web package not found at %s. Click Export Web first.", package_dir))
    with open(sums, encoding="utf-8") as f:
        entries = [line.split("  ", 1) for line in f.read().splitlines() if line.strip()]
    if not entries or any(len(e) != 2 for e in entries):
        raise AndroidError(Msg("Unreadable SHA256SUMS.txt in %s. Export Web again.", package_dir))
    for digest, rel in entries:
        path = os.path.join(package_dir, *rel.split("/"))
        if not os.path.isfile(path):
            raise AndroidError(Msg("Incomplete Web package: %s is missing. Export Web again.", rel))
        if _sha256(path) != digest:
            raise AndroidError(Msg("Web package changed after export: %s. Export Web again.", rel))
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    listed = {rel for _digest, rel in entries}
    missing = [rel for rel in manifest.get("files", {}) if rel not in listed]
    if missing:
        raise AndroidError(Msg("Incomplete Web package: %s is missing. Export Web again.", missing[0]))
    return manifest


# --- Projeto Gradle ---

def _xml_escape(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _android_string(text):
    """Valor de <string> do Android: XML escapado, aspas e apostrofo com barra e @/? iniciais escapados."""
    text = _xml_escape(text.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"'))
    if text[:1] in ("@", "?"):
        text = "\\" + text
    return text


def _kotlin_string(text):
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$")


def _replace_once(text, pattern, replacement, where):
    new, count = re.subn(pattern, lambda _m: replacement, text, count=1)
    if count != 1:
        raise AndroidError(Msg("Android template changed: %s not found in %s.", pattern, where))
    return new


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _write(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def apply_config(project, config):
    """Aplica id, nome, versao, icone e orientacao ao template copiado em `project`."""
    gradle = os.path.join(project, "app", "build.gradle.kts")
    text = _read(gradle)
    text = _replace_once(text, r'applicationId = "[^"]*"',
                         'applicationId = "%s"' % config["applicationId"], gradle)
    text = _replace_once(text, r"versionCode = \d+", "versionCode = %d" % config["versionCode"], gradle)
    text = _replace_once(text, r'versionName = "[^"]*"',
                         'versionName = "%s"' % _kotlin_string(config["versionName"].strip()), gradle)
    _write(gradle, text)

    strings = os.path.join(project, "app", "src", "main", "res", "values", "strings.xml")
    text = _read(strings)
    text = _replace_once(text, r'<string name="app_name">[^<]*</string>',
                         '<string name="app_name">%s</string>' % _android_string(config["appName"].strip()),
                         strings)
    _write(strings, text)

    manifest = os.path.join(project, "app", "src", "main", "AndroidManifest.xml")
    text = _read(manifest)
    text = _replace_once(text, r'android:screenOrientation="[^"]*"',
                         'android:screenOrientation="%s"' % ORIENTATIONS[config["orientation"]], manifest)
    if config.get("icon"):
        mipmap = os.path.join(project, "app", "src", "main", "res", "mipmap-xxxhdpi")
        os.makedirs(mipmap, exist_ok=True)
        shutil.copyfile(config["icon"], os.path.join(mipmap, "ic_launcher.png"))
        text = _replace_once(text, r'android:label="@string/app_name"',
                             'android:icon="@mipmap/ic_launcher"\n        android:label="@string/app_name"',
                             manifest)
    _write(manifest, text)


def prepare_project(template, package_dir, config, work_dir):
    """Copia o template para `work_dir` (sem saidas de build nem pacote antigo) e poe o jogo em assets/www."""
    # "www" e o pacote de teste copiado a mao para o template (ignorado pelo git).
    ignore = shutil.ignore_patterns("build", ".gradle", ".idea", ".kotlin", "local.properties", "*.iml", "www")
    shutil.copytree(template, work_dir, ignore=ignore)
    www = os.path.join(work_dir, "app", "src", "main", "assets", "www")
    shutil.copytree(package_dir, www, ignore=lambda d, names: [n for n in names if n in _WEB_ONLY]
                    if os.path.samefile(d, package_dir) else [])
    apply_config(work_dir, config)
    return work_dir


def _gradle_failure(log_path):
    """Trecho util do log do Gradle (secao 'What went wrong') para mostrar no erro."""
    try:
        lines = _read(log_path).splitlines()
    except OSError:
        return ""
    for i, line in enumerate(lines):
        if "What went wrong" in line:
            return " ".join(l.strip() for l in lines[i + 1:i + 6] if l.strip() and not l.startswith("*"))
    tail = [l.strip() for l in lines if l.strip()][-3:]
    return " ".join(tail)


def run_gradle(project, toolchain, build_type, log_path, log=print, extra_env=None):
    task = "assembleDebug" if build_type == "debug" else "assembleRelease"
    wrapper = os.path.join(project, "gradlew.bat" if os.name == "nt" else "gradlew")
    if os.name != "nt":
        os.chmod(wrapper, 0o755)
    cmd = [wrapper, task, "--console=plain", "--stacktrace"]
    log("Gradle: %s (log em %s)" % (task, log_path))
    with open(log_path, "w", encoding="utf-8", errors="replace") as out:
        creation = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        env = toolchain.env()
        env.update(extra_env or {})
        result = subprocess.run(cmd, cwd=project, env=env, stdout=out, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, creationflags=creation)
    if result.returncode != 0:
        raise AndroidError(Msg("Gradle failed (see %s): %s", log_path, _gradle_failure(log_path)))
    apk = os.path.join(project, "app", "build", "outputs", "apk", build_type, "app-%s.apk" % build_type)
    if not os.path.isfile(apk):
        raise AndroidError(Msg("Gradle finished but the APK was not found at %s.", apk))
    return apk


def _run(cmd, timeout=120, **kw):
    creation = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    return subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=timeout,
                          stdin=subprocess.DEVNULL, creationflags=creation, **kw)


def create_keystore(path, alias, password, name, toolchain=None, log=print):
    """Cria a chave do release com o keytool do JDK (PKCS12, RSA 4096, ~27 anos). Nunca sobrescreve."""
    problems = keystore_problems({"keystore": path, "keyAlias": alias}, must_exist=False)
    problem = password_problem(password)
    if problem:
        problems.append(problem)
    if problems:
        raise AndroidError(problems[0])
    if os.path.exists(path):
        raise AndroidError(Msg("%s already exists; a signing key is never overwritten.", path))
    toolchain = toolchain or find_toolchain()
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    common = re.sub(r'[,+"\\<>;=#]', " ", name or "").strip() or "Range"
    # A senha vai pelo ambiente (:env), nao pela linha de comando visivel a outros processos.
    env = dict(os.environ, RANGE_KEYTOOL_PASS=password)
    result = _run([toolchain.keytool, "-genkeypair", "-keystore", path, "-storetype", "PKCS12",
                   "-alias", alias, "-keyalg", "RSA", "-keysize", "4096", "-validity", "10000",
                   "-dname", "CN=" + common,
                   "-storepass:env", "RANGE_KEYTOOL_PASS", "-keypass:env", "RANGE_KEYTOOL_PASS"], env=env)
    if result.returncode != 0 or not os.path.isfile(path):
        output = (result.stdout + result.stderr).strip()
        raise AndroidError(Msg("keytool failed: %s", output.splitlines()[-1] if output else result.returncode))
    log("Chave criada em %s (alias %s). Guarde uma copia de seguranca e a senha." % (path, alias))
    return path


def check_keystore(path, alias, password, toolchain):
    """Abre a chave com o keytool antes do Gradle, para dar erro claro de senha ou alias."""
    env = dict(os.environ, RANGE_KEYTOOL_PASS=password)
    result = _run([toolchain.keytool, "-list", "-keystore", path, "-alias", alias,
                   "-storepass:env", "RANGE_KEYTOOL_PASS"], env=env)
    if result.returncode == 0:
        return
    output = (result.stdout + result.stderr).lower()
    if "password" in output:
        raise AndroidError(Msg("Wrong password for the signing key %s.", path))
    if "alias" in output or "does not exist" in output:
        raise AndroidError(Msg("The signing key %s has no alias %s.", path, alias))
    raise AndroidError(Msg("keytool failed: %s", output.strip().splitlines()[-1] if output.strip() else
                           result.returncode))


def signing_certificate(apk, toolchain):
    """SHA-256 do certificado que assinou o APK (apksigner verify), ou "" se nao der para ler."""
    if not toolchain.apksigner:
        return ""
    try:
        result = _run([toolchain.apksigner, "verify", "--print-certs", apk], env=toolchain.env())
    except (OSError, subprocess.SubprocessError):
        return ""
    m = re.search(r"certificate SHA-256 digest: ([0-9a-f]+)", result.stdout)
    return m.group(1) if result.returncode == 0 and m else ""


def _java_version(toolchain):
    try:
        out = subprocess.run([os.path.join(toolchain.java_home, "bin", "java" + _EXE), "-version"],
                             capture_output=True, text=True, timeout=30,
                             creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        return (out.stderr or out.stdout).splitlines()[0].strip()
    except (OSError, IndexError, subprocess.SubprocessError):
        return ""


def _template_versions(template):
    versions = {}
    root = _read(os.path.join(template, "build.gradle.kts"))
    m = re.search(r'id\("com\.android\.application"\) version "([^"]+)"', root)
    versions["agp"] = m.group(1) if m else ""
    props = _read(os.path.join(template, "gradle", "wrapper", "gradle-wrapper.properties"))
    m = re.search(r"gradle-([\d.]+)-bin\.zip", props)
    versions["gradle"] = m.group(1) if m else ""
    app = _read(os.path.join(template, "app", "build.gradle.kts"))
    for key in ("compileSdk", "minSdk", "targetSdk"):
        m = re.search(r"%s = (\d+)" % key, app)
        versions[key] = int(m.group(1)) if m else None
    return versions


def _apk_name(config):
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", config["appName"].strip()).strip("_") or "app"
    version = re.sub(r"[^A-Za-z0-9._-]+", "_", config["versionName"].strip())
    return "%s-%s-%s.apk" % (stem, version, config["buildType"])


def build_apk(package_dir, config, out_dir, toolchain=None, template=None, log=print, password=None):
    """Gera o APK a partir do pacote Web em `package_dir`. Devolve o caminho do APK copiado para `out_dir`.

    Release: `password` (ou a variavel RANGE_ANDROID_KEYSTORE_PASSWORD) abre a chave de config["keystore"].

    Grava em `out_dir`: o APK, android-export.json (a configuracao usada), android-report.json e gradle.log.
    """
    problems = config_problems(config)
    if problems:
        raise AndroidError(problems[0])
    release = config["buildType"] == "release"
    signing_env = {}
    if release:
        password = password or os.environ.get(PASSWORD_ENV, "")
        problem = password_problem(password)
        if problem:
            raise AndroidError(problem)
        signing_env = {"RANGE_ANDROID_KEYSTORE": os.path.abspath(config["keystore"]),
                       "RANGE_ANDROID_KEY_ALIAS": config["keyAlias"].strip(), PASSWORD_ENV: password}
    template = template or template_dir()
    if template is None:
        raise AndroidError(Msg("Android template not found (tools/android/webview-template). "
                               "Export from a development tree."))
    toolchain = toolchain or find_toolchain()
    if release:
        check_keystore(signing_env["RANGE_ANDROID_KEYSTORE"], signing_env["RANGE_ANDROID_KEY_ALIAS"], password,
                       toolchain)
    log("JDK: %s (%s)" % (toolchain.java_home, toolchain.java_source))
    log("Android SDK: %s (%s)" % (toolchain.sdk_dir, toolchain.sdk_source))
    manifest = verify_web_package(package_dir)
    log("Pacote Web conferido: %s %s" % (manifest.get("name"), manifest.get("version")))

    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    save_config(config, os.path.join(out_dir, CONFIG_NAME))
    # Pasta de trabalho fora do projeto; a da ultima geracao fica para diagnostico ate a proxima.
    base = os.path.join(tempfile.gettempdir(), "range-android-build")
    os.makedirs(base, exist_ok=True)
    for old in os.listdir(base):
        shutil.rmtree(os.path.join(base, old), ignore_errors=True)
    work = os.path.join(tempfile.mkdtemp(prefix=config["applicationId"] + "-", dir=base), "project")
    prepare_project(template, package_dir, config, work)
    log("Projeto Android montado em %s" % work)

    built = run_gradle(work, toolchain, config["buildType"], os.path.join(out_dir, GRADLE_LOG_NAME), log,
                       extra_env=signing_env)
    apk = os.path.join(out_dir, _apk_name(config))
    shutil.copyfile(built, apk)
    certificate = signing_certificate(apk, toolchain)
    if release and not certificate:
        raise AndroidError(Msg("The release APK is not signed (apksigner could not verify %s).", apk))

    report = {
        "schema": "range-android-report",
        "schema_version": SCHEMA_VERSION,
        "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "apk": {"file": os.path.basename(apk), "bytes": os.path.getsize(apk), "sha256": _sha256(apk)},
        "config": {key: config.get(key) for key in DEFAULTS},
        "web_package": {
            "dir": os.path.abspath(package_dir),
            "name": manifest.get("name"),
            "version": manifest.get("version"),
            "entry_game": manifest.get("entry_game"),
            "runtime": manifest.get("runtime", {}),
            "files": {rel: info.get("sha256") for rel, info in manifest.get("files", {}).items()
                      if rel not in _WEB_ONLY},
        },
        "template": _template_versions(template),
        "toolchain": {
            "java_home": toolchain.java_home,
            "java_source": toolchain.java_source,
            "java_version": _java_version(toolchain),
            "sdk_dir": toolchain.sdk_dir,
            "sdk_source": toolchain.sdk_source,
            "platforms": sorted(os.path.basename(p) for p in
                                glob.glob(os.path.join(toolchain.sdk_dir, "platforms", "android-*"))),
            "build_tools": sorted(os.path.basename(p) for p in
                                  glob.glob(os.path.join(toolchain.sdk_dir, "build-tools", "*"))),
        },
        "signing": {
            "keystore": os.path.abspath(config["keystore"]) if release else "",
            "keyAlias": config["keyAlias"].strip() if release else "",
            "certificate_sha256": certificate,
        },
        "project_dir": work,
    }
    with open(os.path.join(out_dir, REPORT_NAME), "w", encoding="utf-8", newline="\n") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
        f.write("\n")
    log("APK: %s (%.1f MiB)" % (apk, report["apk"]["bytes"] / (1 << 20)))
    return apk


# --- Instalacao pelo adb ---

def _adb(toolchain, *args, timeout=600):
    if not os.path.isfile(toolchain.adb):
        raise AndroidError(Msg("adb not found at %s. Install Android SDK Platform-Tools in Android Studio.",
                               toolchain.adb))
    creation = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    return subprocess.run([toolchain.adb, *args], capture_output=True, text=True, errors="replace",
                          timeout=timeout, stdin=subprocess.DEVNULL, creationflags=creation)


def find_device(toolchain):
    """Serial do aparelho pronto para instalar; erro claro se nao houver ou nao estiver autorizado."""
    out = _adb(toolchain, "devices", timeout=60).stdout
    rows = [line.split("\t") for line in out.splitlines()[1:] if "\t" in line]
    ready = [serial for serial, state in rows if state.strip() == "device"]
    if ready:
        return ready[0]
    if any(state.strip() == "unauthorized" for _serial, state in rows):
        raise AndroidError(Msg("The phone did not authorize this computer. Unlock it and accept "
                               "the USB debugging prompt."))
    raise AndroidError(Msg("No phone connected. Connect it by USB with USB debugging enabled "
                           "(Developer options)."))


def install_apk(apk, application_id, toolchain=None, launch=True, log=print):
    """Instala por cima (adb install -r, mantem o save) e abre o jogo. Devolve o serial do aparelho."""
    if not os.path.isfile(apk):
        raise AndroidError(Msg("APK not found at %s. Click Build APK first.", apk))
    toolchain = toolchain or find_toolchain()
    serial = find_device(toolchain)
    log("Instalando %s em %s" % (os.path.basename(apk), serial))
    result = _adb(toolchain, "-s", serial, "install", "-r", apk)
    output = (result.stdout + result.stderr).strip()
    if result.returncode != 0 or "Success" not in output:
        if "INSTALL_FAILED_UPDATE_INCOMPATIBLE" in output:
            raise AndroidError(Msg("The phone already has %s signed with another key. Uninstalling it "
                                   "erases the game's save; do it by hand only if you accept that.",
                                   application_id))
        if "INSTALL_FAILED_VERSION_DOWNGRADE" in output:
            raise AndroidError(Msg("The phone has a newer version of %s. Increase the version code.",
                                   application_id))
        raise AndroidError(Msg("adb install failed: %s", output.splitlines()[-1] if output else result.returncode))
    if launch:
        _adb(toolchain, "-s", serial, "shell", "am", "start", "-n",
             "%s/%s.MainActivity" % (application_id, TEMPLATE_NAMESPACE), timeout=60)
    return serial
