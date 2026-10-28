"""A/B of frame pacing with a driving and turning object (see tools/create_pacing_drive_test.py).

Usage (Windows, from the repo root):  python tools/timing_drive_ab.py [build\\bin]
Runs fixed/legacy x 1ms/15ms timer x sleep/mix for FT_SECONDS each and prints the DRIVE_TEST line.
"""
import os, subprocess, sys, tempfile

BIN = sys.argv[1] if len(sys.argv) > 1 else os.path.join("build", "bin")
EXE = ".exe" if os.name == "nt" else ""
RUNTIME = os.path.join(BIN, "AnastacioRuntime" + EXE)
EDITOR = os.path.join(BIN, "AnastacioEngine" + EXE)
SECONDS = os.environ.get("FT_SECONDS", "10")

def main():
    tmp = tempfile.mkdtemp(prefix="timing_drive_")
    scene = os.path.join(tmp, "drive.range")
    subprocess.run([EDITOR, "-b", "--python", "tools/create_pacing_drive_test.py", "--", scene], check=True,
                   stdout=subprocess.DEVNULL)
    result = os.path.join(tmp, "drive_result.txt")
    for fixed in (1, 0):
        for timer_res in (1, 0):
            for pacing in ("sleep", "mix"):
                env = dict(os.environ, RANGE_PACING=pacing, FT_SECONDS=SECONDS, RANGE_NO_CRASH_DIALOG="1")
                env.pop("RANGE_NO_TIMER_RES", None)
                if not timer_res:
                    env["RANGE_NO_TIMER_RES"] = "1"
                before = open(result).read().count("\n") if os.path.exists(result) else 0
                subprocess.run([RUNTIME, "-g", "fixed_timestep", "=", str(fixed), scene], env=env,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=float(SECONDS) + 60)
                lines = open(result).read().splitlines() if os.path.exists(result) else []
                tag = "%-6s %-5s %-5s" % ("fixed" if fixed else "legacy", pacing, "1ms" if timer_res else "15ms")
                print(tag, "|", lines[-1][11:] if len(lines) > before else "no result")

if __name__ == "__main__":
    main()
