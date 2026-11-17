"""Copy the available AnastacioRuntime installations into a RangeArmor project.

The Panel may run on Windows while a Linux runtime was built through WSL.
Therefore platform selection is independent from the Panel host OS: the
``--all-platforms`` action copies every runtime that can be found.
"""

import os
import platform
import shutil
import sys
import tempfile
import uuid
from pathlib import Path

import common as _common


args = _common.getArgs()
data = _common.getProjectData()

PLATFORMS = {
    "Windows64": "AnastacioRuntime.exe",
    "Linux64": "AnastacioRuntime",
}


def main():
    if not data:
        raise RuntimeError("A valid project config is required (--project)")

    targets = requested_platforms()
    copied = 0
    for target_name in targets:
        source = get_engine_source(target_name)
        if source is None:
            if args.get("--all-platforms"):
                print("! Runtime not available for " + target_name + "; skipping it.")
                continue
            raise RuntimeError("Could not find a " + target_name + " engine installation.")
        copy_runtime(source, target_name)
        copied += 1

    if copied == 0:
        raise RuntimeError("No AnastacioRuntime installation was found. Set RANGEARMOR_ENGINE_DIR_WINDOWS64 and/or RANGEARMOR_ENGINE_DIR_LINUX64.")


def requested_platforms():
    if args.get("--all-platforms"):
        return list(PLATFORMS)
    requested = args.get("--platform")
    if requested:
        if requested not in PLATFORMS:
            raise RuntimeError("Unsupported runtime platform: " + str(requested))
        return [requested]
    return ["Windows64" if platform.system() == "Windows" else "Linux64"]


def copy_runtime(source, target_name):
    source = source.resolve()
    if not _common.resolve_runtime(source / PLATFORMS[target_name]).is_file():
        raise RuntimeError("Source does not contain " + PLATFORMS[target_name])
    project = data["CurPath"].resolve()
    target = (project / "engine" / target_name).resolve()
    if project not in target.parents or target == source or target in source.parents or source in target.parents:
        raise RuntimeError("Unsafe runtime destination: " + str(target))
    target.parent.mkdir(parents=True, exist_ok=True)
    print("> Copying " + target_name + " runtime from:", source.as_posix())
    print("> Copying runtime to:", target.as_posix())
    with tempfile.TemporaryDirectory(prefix=".runtime-copy-", dir=str(target.parent)) as temporary:
        staged = Path(temporary) / target_name
        shutil.copytree(source, staged, ignore=ignore_runtime_tools)
        runtime = _common.resolve_runtime(staged / PLATFORMS[target_name])
        if not runtime.is_file():
            raise RuntimeError("Copied folder does not contain " + runtime.name)
        if target_name == "Linux64":
            runtime.chmod(runtime.stat().st_mode | 0o111)
        previous = target.with_name(target.name + ".previous-" + uuid.uuid4().hex)
        had_previous = target.exists()
        if had_previous:
            _rename(target, previous)
        try:
            _rename(staged, target)
        except Exception:
            if had_previous:
                _rename(previous, target)
            raise
        if had_previous and args.get("--drop-previous"):
            # Export to Desktop recopia a engine quando ela muda; guardar cada cópia velha enche o disco.
            shutil.rmtree(str(previous), ignore_errors=True)
            print("> Previous runtime removed")
        elif had_previous:
            print("> Previous runtime preserved:", previous.as_posix())
    print("> " + target_name + " runtime copied successfully.")


def _rename(source, destination, attempts=20):
    """Path.rename with retries: on Windows the antivirus keeps the freshly copied .exe/.dll open
    for a few seconds and renaming their folder fails with "Access denied" (WinError 5)."""
    import time
    for attempt in range(attempts):
        try:
            return source.rename(destination)
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(1.5)


def get_engine_source(target_name):
    # Explicit per-platform variables work from every host, including a
    # Windows Panel consuming a WSL build exposed through the mounted drive.
    configured = os.environ.get("RANGEARMOR_ENGINE_DIR_" + target_name.upper())
    if configured:
        return valid_runtime_dir(Path(configured), target_name, "environment variable")

    # Preserve the old single-runtime interface for scripts and CI. It only
    # applies to the host platform, so one path cannot accidentally be copied
    # into the other platform's folder.
    host_target = "Windows64" if platform.system() == "Windows" else "Linux64"
    legacy = args.get("--engine-dir") or os.environ.get("RANGEARMOR_ENGINE_DIR")
    if legacy and target_name == host_target:
        return valid_runtime_dir(Path(legacy), target_name, "RANGEARMOR_ENGINE_DIR")

    # Installed engine: these scripts live in <engine>/2.79/scripts/export_desktop/,
    # so the export works after extraction without workspace folders or overrides.
    installed = valid_runtime_dir(_common.ENGINE_DIR, target_name, None)
    if installed:
        return installed

    # In a source checkout the conventional sibling build folders make the
    # button useful without environment setup: build/bin for Windows and
    # build-linux/bin for Linux. This also works when the Linux build was
    # produced in WSL because its files live on the shared project drive.
    build_name = "build" if target_name == "Windows64" else "build-linux"
    for root in search_roots():
        source = valid_runtime_dir(root / build_name / "bin", target_name, None)
        if source:
            print("> Found " + target_name + " runtime in workspace:", source.as_posix())
            return source
    return None


def valid_runtime_dir(candidate, target_name, description):
    candidate = candidate.expanduser().resolve()
    if _common.resolve_runtime(candidate / PLATFORMS[target_name]).is_file():
        return candidate
    if description:
        print("! " + description + " does not contain " + PLATFORMS[target_name] + ":", candidate.as_posix())
    return None


def search_roots():
    roots = []
    for start in (Path.cwd(), Path(__file__).resolve()):
        roots.extend([start, *start.parents])
    seen = set()
    for root in roots:
        if root not in seen:
            seen.add(root)
            yield root


def ignore_runtime_tools(directory, names):
    return _common.ignore_dev_files(directory, names)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("X Could not copy runtime:", error)
        sys.exit(1)
