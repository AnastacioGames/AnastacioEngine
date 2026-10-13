"""Monta a pasta web/ de um pacote de release (Windows ou Linux).

Uso: python tools/stage_release_web.py <pasta do pacote> [--runtime-dir build-web-release/bin]

Cria, ao lado dos executaveis:
  web/runtime/           RangeRuntime.{js,wasm,data,manifest.json} (Export Web e Android)
  web/tools/             scripts versionados de tools/web (package-web.py, package-android.py, ...)
  web/android-template/  arquivos versionados de tools/android/webview-template (Build APK)

O runtime Web e o mesmo nas duas plataformas. Do template so entram os arquivos do git:
app/build, .gradle e assets/www sao gerados e pesam dezenas de MB.
"""

import argparse
import os
import shutil
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RUNTIME_FILES = ("RangeRuntime.js", "RangeRuntime.wasm", "RangeRuntime.data", "RangeRuntime.manifest.json")


def tracked(rel_dir):
    # safe.directory: no container de build do Linux o repositorio montado pertence a outro usuario.
    out = subprocess.run(["git", "-c", "safe.directory=*", "-C", ROOT, "ls-files", "-z", rel_dir], capture_output=True, check=True)
    return [p for p in out.stdout.decode().split("\0") if p]


def copy_tracked(rel_dir, dest, recursive):
    files = [p for p in tracked(rel_dir) if recursive or "/" not in p[len(rel_dir) + 1:]]
    if not files:
        sys.exit("Nada versionado em %s." % rel_dir)
    for rel in files:
        target = os.path.join(dest, *rel[len(rel_dir) + 1:].split("/"))
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copy2(os.path.join(ROOT, *rel.split("/")), target)
    return len(files)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("package", help="pasta do pacote (a que tem AnastacioEngine.exe ou RangeEngine)")
    parser.add_argument("--runtime-dir", default=os.path.join(ROOT, "build-web-release", "bin"),
                        help="saida do preset web-runtime-release")
    args = parser.parse_args()

    missing = [f for f in RUNTIME_FILES if not os.path.isfile(os.path.join(args.runtime_dir, f))]
    if missing:
        sys.exit("Runtime Web incompleto em %s (falta %s). Compile o preset web-runtime-release."
                 % (args.runtime_dir, ", ".join(missing)))

    web = os.path.join(args.package, "web")
    shutil.rmtree(web, ignore_errors=True)
    runtime = os.path.join(web, "runtime")
    os.makedirs(runtime)
    for name in RUNTIME_FILES:
        shutil.copy2(os.path.join(args.runtime_dir, name), runtime)
    n_tools = copy_tracked("tools/web", os.path.join(web, "tools"), recursive=False)
    n_template = copy_tracked("tools/android/webview-template", os.path.join(web, "android-template"), recursive=True)
    if os.name != "nt":
        os.chmod(os.path.join(web, "android-template", "gradlew"), 0o755)
    print("web/: runtime %d, tools %d, android-template %d arquivos" % (len(RUNTIME_FILES), n_tools, n_template))


if __name__ == "__main__":
    main()
