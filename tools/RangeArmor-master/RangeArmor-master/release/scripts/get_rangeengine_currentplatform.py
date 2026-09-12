"""Copy the available RangeRuntime installations into a RangeArmor project.

The Panel may run on Windows while a Linux runtime was built through WSL.
Therefore platform selection is independent from the Panel host OS: the
``--all-platforms`` action copies every runtime that can be found.
"""

import os
import platform
import shutil
from pathlib import Path

import common as _common


args = _common.getArgs()
data = _common.getProjectData()

PLATFORMS = {
    "Windows64": "RangeRuntime.exe",
    "Linux64": "RangeRuntime",
}


def main():
    if not data:
        return

    targets = requested_platforms()
    copied = 0
    for target_name in targets:
        source = get_engine_source(target_name)
        if source is None:
            if args.get("--all-platforms"):
                print("! Runtime not available for " + target_name + "; skipping it.")
                continue
            print("X Could not find a " + target_name + " engine installation.")
            return
        copy_runtime(source, target_name)
        copied += 1

    if copied == 0:
        print("X No RangeRuntime installation was found. Set RANGEARMOR_ENGINE_DIR_WINDOWS64 and/or RANGEARMOR_ENGINE_DIR_LINUX64.")


def requested_platforms():
    if args.get("--all-platforms"):
        return list(PLATFORMS)
    requested = args.get("--platform")
    if requested in PLATFORMS:
        return [requested]
    return ["Windows64" if platform.system() == "Windows" else "Linux64"]


def copy_runtime(source, target_name):
    target = data["CurPath"] / "engine" / target_name
    if target.exists():
        print("> Removing previous engine files:", target.as_posix())
        shutil.rmtree(target)

    print("> Copying " + target_name + " runtime from:", source.as_posix())
    print("> Copying runtime to:", target.as_posix())
    shutil.copytree(source.as_posix(), target.as_posix(), ignore=ignore_runtime_tools)

    runtime = target / PLATFORMS[target_name]
    if not runtime.is_file():
        print("X Copied folder does not contain", runtime.name)
        shutil.rmtree(target, ignore_errors=True)
        return

    if target_name == "Linux64":
        runtime.chmod(runtime.stat().st_mode | 0o111)
    print("> " + target_name + " runtime copied successfully.")


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
    if (candidate / PLATFORMS[target_name]).is_file():
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


def ignore_runtime_tools(_directory, names):
    return {name for name in names if name in {"makesdna", "makesrna", "datatoc", "rangearmor", "rangearmor_panel"}}


try:
    main()
except Exception as error:
    print("X Could not copy runtime:", error)
