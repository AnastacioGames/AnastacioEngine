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
        _deliver(release, destination, [(target, suffix, launcher, engine)], data, project,
                 use_cooked, args.get("--compress") and (".zip" if target == "Windows64" else ".tar.xz"))
        print("> Build successful:", target, destination)
    # Universal: one folder with the Windows and Linux players side by side.
    # The launcher picks Engine<platform> from config.json for the OS it runs on.
    if args.get("--universal") and len(inputs) > 1:
        name = "-".join([common.formatFileName(data["GameName"], spaces=False), version, "Universal"])
        destination = release / name
        _deliver(release, destination, [entry[:4] for entry in inputs], data, project,
                 use_cooked, args.get("--compress") and ".zip")
        print("> Build successful: Universal", destination)
    elif args.get("--universal"):
        missing = [key for key in ("Windows64", "Linux64") if key not in [entry[0] for entry in inputs]]
        print("! Universal package skipped: no runtime for " + ", ".join(missing) +
              ". Set both Windows and Linux runtimes in the Paths tab.")


def _drop_protected_sources(data_dir):
    """Tira da entrega o .range/.blend aberto que ja tem o .rasec cifrado ao
    lado. O player troca .range por .rasec sozinho quando o aberto falta
    (KX_PythonInit/KX_Scene), entao o jogo carrega igual. Os .range sem
    .rasec ficam: podem ser LibLoad que o jogo precisa."""
    for pattern in ("*.range", "*.blend"):
        for source in [path for path in data_dir.rglob(pattern) if path.is_file()]:
            if source.with_suffix(".rasec").is_file():
                source.unlink()
                print("> Left out (protected .rasec ships instead):", source.relative_to(data_dir).as_posix())


def _compile_scripts(data_dir):
    """Troca cada .py da entrega por um .pyc ao lado (sem __pycache__), que o
    import do jogo carrega sem o fonte. Roda com o Python do pacote (3.11),
    o mesmo do runtime, entao o .pyc bate com o interpretador do jogo.
    So mexe na copia da entrega; o projeto do autor fica com os .py."""
    import py_compile
    sources = [path for path in data_dir.rglob("*.py") if path.is_file()]
    for source in sources:
        try:
            py_compile.compile(str(source), cfile=str(source.with_suffix(".pyc")),
                               dfile=source.relative_to(data_dir).as_posix(), doraise=True)
        except py_compile.PyCompileError as error:
            raise RuntimeError("Compile Scripts: " + str(error.msg).strip())
    for source in sources:
        source.unlink()
    for cache in [path for path in data_dir.rglob("__pycache__") if path.is_dir()]:
        shutil.rmtree(str(cache))
    print("> Compiled scripts:", len(sources))


def _deliver(release, destination, targets, data, project, use_cooked, archive_ext):
    with tempfile.TemporaryDirectory(prefix=".rangearmor-stage-", dir=str(release)) as temp:
        stage = Path(temp) / destination.name
        stage.mkdir()
        # Backups do editor (.range1, .blend1...) nunca sao lidos pelo jogo e
        # entregariam o arquivo aberto.
        exclusions = ['*.export-tmp', '*.cooked.tmp', '*.range[0-9]*', '*.rasec[0-9]*', '*.blend[0-9]*']
        if not use_cooked:
            exclusions.append('*.cooked')
        asset_source = (project / data.get('PreparedDataSource', 'data')).resolve()
        if project not in asset_source.parents or not asset_source.is_dir():
            raise RuntimeError('Prepared assets must exist inside the project')
        shutil.copytree(str(asset_source), str(stage / "data"),
                        ignore=shutil.ignore_patterns(*exclusions))
        _drop_protected_sources(stage / "data")
        if data.get("CompileScripts", False):
            _compile_scripts(stage / "data")
        (stage / "launcher").mkdir()
        shutil.copy2(str(data["ProjectFile"]), str(stage / "launcher/config.json"))
        delivered_config = stage / 'launcher/config.json'
        config = None
        if data.get('PreparedDataSource'):
            config = json.loads(delivered_config.read_text(encoding='utf-8'))
            config.pop('PreparedDataSource', None)
            config['DataSource'] = './data'
        for target, suffix, launcher, engine in targets:
            # Only the delivery adopts the executable actually copied. The
            # author's config and custom paths remain untouched.
            if data.get('Engine' + target):
                effective_runtime = data['EngineExecutables'][target]
                if effective_runtime.parent.resolve() != engine.resolve():
                    raise RuntimeError('Runtime executable must be inside engine/' + target)
                if config is None:
                    config = json.loads(delivered_config.read_text(encoding='utf-8'))
                config['Engine' + target] = './engine/' + target + '/' + effective_runtime.name
            game_launcher = stage / (common.formatFileName(data["GameName"]) + suffix)
            shutil.copy2(str(launcher), str(game_launcher))
            if not suffix:
                game_launcher.chmod(game_launcher.stat().st_mode | 0o111)
            shutil.copytree(str(engine), str(stage / "engine" / target))
        if config is not None:
            delivered_config.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding='utf-8')
        archive = None
        if archive_ext:
            archive = Path(temp) / (destination.name + archive_ext)
            if archive_ext == ".zip":
                with zipfile.ZipFile(str(archive), "w", zipfile.ZIP_DEFLATED) as output:
                    for file in stage.rglob("*"):
                        if file.is_file():
                            info = zipfile.ZipInfo.from_file(str(file), file.relative_to(stage.parent).as_posix())
                            info.compress_type = zipfile.ZIP_DEFLATED
                            relative = file.relative_to(stage)
                            # Zips made on Windows lose the Linux executable bit;
                            # keep it for the Linux launcher and the Linux runtime folder.
                            if (relative.parts[:2] == ("engine", "Linux64") or
                                    (len(relative.parts) == 1 and not file.suffix)):
                                info.external_attr = (0o100755 << 16)
                            with open(str(file), "rb") as source:
                                output.writestr(info, source.read())
            else:
                with tarfile.open(str(archive), "w:xz", preset=1) as output:  # preset 6 took ~13 min

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

if __name__ == "__main__":
    try:
        data = common.getProjectData()
        if not data:
            raise RuntimeError("Could not read project configuration")
        build(data, common.getArgs())
    except Exception as error:
        print("X " + str(error))
        raise SystemExit(1)
