#!/usr/bin/env python3
"""Check a RangeArmor Universal package on Linux.

Usage: python3 test_universal_linux.py <Game-x.y.z-Universal.zip | folder> [--run]

Extracts the zip keeping the exec bits (plain `unzip` may drop them),
checks the Linux launcher, runtime and Python, then optionally runs ./<Game>.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


def extract(archive):
    target = Path(tempfile.mkdtemp(prefix="universal-test-"))
    with zipfile.ZipFile(str(archive)) as zip_file:
        for info in zip_file.infolist():
            path = zip_file.extract(info, str(target))
            mode = (info.external_attr >> 16) & 0o777
            if mode:
                os.chmod(path, mode)
    roots = [p for p in target.iterdir() if p.is_dir()]
    return roots[0] if len(roots) == 1 else target


def check(root):
    ok = True

    def report(good, text):
        nonlocal ok
        ok = ok and good
        print(("[ OK ] " if good else "[FAIL] ") + text)

    launchers = [p for p in root.iterdir() if p.is_file() and not p.suffix]
    report(bool(launchers), "Linux launcher next to Game.exe: %s" % [p.name for p in launchers])
    for launcher in launchers:
        report(os.access(str(launcher), os.X_OK), "launcher is executable: %s" % launcher.name)
    engine = root / "engine" / "Linux64"
    runtimes = [engine / n for n in ("AnastacioRuntime", "RangeRuntime") if (engine / n).exists()]
    report(bool(runtimes), "runtime in engine/Linux64: %s" % [p.name for p in runtimes])
    for runtime in runtimes:
        report(os.access(str(runtime), os.X_OK), "runtime is executable: %s" % runtime.name)
        if shutil.which("ldd"):
            out = subprocess.run(["ldd", str(runtime)], stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, universal_newlines=True).stdout
            missing = [l.strip() for l in out.splitlines() if "not found" in l]
            report(not missing, "runtime libraries found" + ("" if not missing else ": %s" % missing))
    python = engine / "2.79" / "python" / "bin" / "python3.11"
    report(python.exists(), "Python present: %s" % python.relative_to(root))
    report((root / "engine" / "Windows64").is_dir(), "Windows engine also present")
    return ok, launchers


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    source = Path(sys.argv[1]).resolve()
    root = extract(source) if source.suffix == ".zip" else source
    print("Package:", root)
    ok, launchers = check(root)
    if "--run" in sys.argv and launchers:
        print("Running", launchers[0].name, "...")
        return subprocess.call([str(launchers[0])], cwd=str(root))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
