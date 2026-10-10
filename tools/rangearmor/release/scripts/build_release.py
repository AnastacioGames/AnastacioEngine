"""Build releases in staging, preserving the previous delivery on failure."""
import os
import platform
import shutil
import tarfile
import tempfile
import zipfile
import hashlib
import json
from pathlib import Path
import common
import prepare_cooked


def build(data, args):
    project = data["CurPath"].resolve()
    release = project / "release"
    release.mkdir(exist_ok=True)
    if release.resolve().parent != project:
        raise RuntimeError("Release directory must be inside the project")
    selected = args.get("--target")
    targets = [key for key in ("Windows64", "Linux64")
               if data.get("Export" + key, True) and
               (selected == "All" or selected == key) and key in data["EngineExecutables"]]
    if not targets:
        raise RuntimeError("No available runtime selected for export")
    inputs = []
    version = data['Version']
    if not isinstance(version, str) or not version or any(char in version for char in '/\\:'):
        raise RuntimeError('Invalid release version')
    for target in targets:
        suffix = ".exe" if target == "Windows64" else ""
        launcher = project / "launcher" / ("Launcher" + suffix)
        engine = project / "engine" / target
        if not launcher.is_file() or not engine.is_dir():
            raise RuntimeError("Missing launcher or runtime for " + target)
        templates = Path(__file__).resolve().parents[1] / 'launcher'
        manifest = templates / 'legacy-template-sha256.json'
        if manifest.is_file():
            known = json.loads(manifest.read_text(encoding='utf-8')).get(target, [])
            if hashlib.sha256(launcher.read_bytes()).hexdigest() in known:
                replacement = templates / ('Launcher' + suffix)
                if not replacement.is_file() or hashlib.sha256(replacement.read_bytes()).hexdigest() in known:
                    raise RuntimeError('Known obsolete launcher; install the updated template first')
                launcher = replacement
                print('> Using updated launcher template for', target)
        name = "-".join([common.formatFileName(data["GameName"], spaces=False),
                         data["Version"], target])
        destination = release / name
        if destination.resolve().parent != release.resolve():
            raise RuntimeError("Invalid release name or version")
        inputs.append((target, suffix, launcher, engine, destination))
    use_cooked = not args.get('--no-cook', False)
    if use_cooked:
        prepare_cooked.prepare(data)
    for target, suffix, launcher, engine, destination in inputs:
        with tempfile.TemporaryDirectory(prefix=".rangearmor-stage-", dir=str(release)) as temp:
            stage = Path(temp) / destination.name
            stage.mkdir()
            exclusions = ['*.export-tmp', '*.cooked.tmp']
            if not use_cooked:
                exclusions.append('*.cooked')
            shutil.copytree(str(project / "data"), str(stage / "data"),
                            ignore=shutil.ignore_patterns(*exclusions))
            (stage / "launcher").mkdir()
            shutil.copy2(str(data["ProjectFile"]), str(stage / "launcher/config.json"))
            # Only the delivery adopts the executable actually copied. The
            # author's config and custom paths remain untouched.
            if data.get('Engine' + target):
                delivered_config = stage / 'launcher/config.json'
                config = json.loads(delivered_config.read_text(encoding='utf-8'))
                effective_runtime = data['EngineExecutables'][target]
                if effective_runtime.parent.resolve() != engine.resolve():
                    raise RuntimeError('Runtime executable must be inside engine/' + target)
                config['Engine' + target] = './engine/' + target + '/' + effective_runtime.name
                delivered_config.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding='utf-8')
            game_launcher = stage / (common.formatFileName(data["GameName"]) + suffix)
            shutil.copy2(str(launcher), str(game_launcher))
            if not suffix:
                game_launcher.chmod(game_launcher.stat().st_mode | 0o111)
            shutil.copytree(str(engine), str(stage / "engine" / target))
            archive = None
            if args.get("--compress"):
                extension = ".zip" if target == "Windows64" else ".tar.xz"
                archive = Path(temp) / (destination.name + extension)
                if extension == ".zip":
                    with zipfile.ZipFile(str(archive), "w", zipfile.ZIP_DEFLATED) as output:
                        for file in stage.rglob("*"):
                            if file.is_file():
                                output.write(str(file), file.relative_to(stage.parent).as_posix())
                else:
                    with tarfile.open(str(archive), "w:xz") as output:
                        output.add(str(stage), arcname=destination.name)
            previous = None
            if destination.exists():
                previous = Path(tempfile.mkdtemp(prefix=destination.name + ".previous-", dir=str(release)))
                os.replace(str(destination), str(previous / destination.name))
            try:
                os.replace(str(stage), str(destination))
            except OSError:
                if previous is not None:
                    os.replace(str(previous / destination.name), str(destination))
                raise
            if archive is not None:
                os.replace(str(archive), str(release / archive.name))
            if previous is not None:
                print("> Previous delivery preserved:", previous)
            print("> Build successful:", target, destination)


if __name__ == "__main__":
    try:
        data = common.getProjectData()
        if not data:
            raise RuntimeError("Could not read project configuration")
        build(data, common.getArgs())
    except Exception as error:
        print("X " + str(error))
        raise SystemExit(1)
