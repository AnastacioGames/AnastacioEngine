from pathlib import Path as _Path
import common as _common


args = _common.getArgs()
data = _common.getProjectData()


def main():
    # type: () -> None

    import subprocess
    import platform
    import stat

    print("Run launcher")

    if data:

        if args.get("--engine"):
            ext = ".exe" if args.get("--engine").lower().startswith("windows") else ""
            currentLauncher = data["CurPath"] / ("launcher/Launcher" + ext)  # type: _Path

            if currentLauncher.exists():
                useWine = platform.system() != "Windows" and args.get("--engine").lower().startswith("windows")

                if platform.system() != "Windows":
                    currentLauncher.chmod(currentLauncher.stat().st_mode | stat.S_IEXEC)

                _args = (["wine"] if useWine else []) + [
                    currentLauncher.as_posix(),
                    "--engine", args.get("--engine"),
                    "--file", args.get("--project"),
                ]
                # Run an updated known template without overwriting a user's
                # existing launcher. Custom launchers retain priority.
                import hashlib
                import json
                templates = _Path(__file__).resolve().parents[1] / 'launcher'
                manifest = templates / 'legacy-template-sha256.json'
                if manifest.is_file():
                    known = json.loads(manifest.read_text(encoding='utf-8')).get(args.get('--engine'), [])
                    if hashlib.sha256(currentLauncher.read_bytes()).hexdigest() in known:
                        replacement = templates / ('Launcher' + ext)
                        if not replacement.is_file():
                            raise RuntimeError('Updated launcher template is missing')
                        _args[1 if useWine else 0] = str(replacement)
                result = subprocess.call(_args)
                if result != 0:
                    raise RuntimeError("Launcher exited with status {}".format(result))

            else:
                print("X Could not find launcher at", currentLauncher.as_posix())

        else:
            print("X Argument --engine must be provided")

try:
    main()
except Exception as e:
    print(e)
