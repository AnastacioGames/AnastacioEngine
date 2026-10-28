"""A/B test of frame pacing (spin/sleep mix vs. sleep-only), with and without the 1 ms Windows timer.

Usage (Windows, from the repo root, after building RangeRuntime and RangeEngine):
  python tools/timing_ab.py [build\\bin]

Builds the fixed-timestep test scene, runs it 4 ways x 2 loops (fixed/legacy) for FT_SECONDS each,
reads the per-frame trace and prints, per run: mean FPS, frame-time jitter, worst frame,
frames over 1.5x the target and process CPU %. Lower jitter/worst/late is better.
"""
import json, os, statistics, subprocess, sys, tempfile, time

BIN = sys.argv[1] if len(sys.argv) > 1 else os.path.join("build", "bin")
EXE = ".exe" if os.name == "nt" else ""
RUNTIME = os.path.join(BIN, "RangeRuntime" + EXE)
EDITOR = os.path.join(BIN, "RangeEngine" + EXE)
SECONDS = os.environ.get("FT_SECONDS", "15")
WORK = os.environ.get("FT_SLEEP", "0.004")  # simulated game work per frame
TARGET_MS = 1000.0 / 60.0

try:
    import psutil
except ImportError:
    psutil = None

def run(tmp, scene, fixed, pacing, timer_res):
    out = os.path.join(tmp, "trace_%d_%s_%d" % (fixed, pacing, timer_res))
    os.makedirs(out, exist_ok=True)
    env = dict(os.environ, RANGE_TRACE=out, RANGE_TRACE_MODULES="frames", RANGE_PACING=pacing,
               FT_SECONDS=SECONDS, FT_SLEEP=WORK, RANGE_NO_CRASH_DIALOG="1")
    env.pop("RANGE_NO_TIMER_RES", None)
    if not timer_res:
        env["RANGE_NO_TIMER_RES"] = "1"
    proc = subprocess.Popen([RUNTIME, "-g", "fixed_timestep", "=", str(fixed), scene], env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    cpu = None
    if psutil:
        p = psutil.Process(proc.pid)
        try:
            t0 = time.time(); c0 = sum(p.cpu_times()[:2])
            time.sleep(float(SECONDS) * 0.8)
            cpu = 100.0 * (sum(p.cpu_times()[:2]) - c0) / (time.time() - t0)
        except psutil.Error:
            pass
    try:
        proc.wait(timeout=float(SECONDS) + 60)
    except subprocess.TimeoutExpired:
        proc.kill()
    frames = []
    path = os.path.join(out, "trace.jsonl")
    if os.path.exists(path):
        for line in open(path, encoding="utf-8", errors="ignore"):
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            if ev.get("ev", ev.get("event", ev.get("type"))) == "frame" and "ms" in ev:
                frames.append(ev["ms"])
    frames = frames[30:]  # skip load
    return frames, cpu

def main():
    tmp = tempfile.mkdtemp(prefix="timing_ab_")
    scene = os.path.join(tmp, "timing.range")
    subprocess.run([EDITOR, "-b", "--python", "tools/create_fixed_timestep_test.py", "--", scene], check=True,
                   stdout=subprocess.DEVNULL)
    print("%-6s %-5s %-6s | %6s %7s %7s %5s %5s" % ("loop", "pace", "timer", "fps", "jitter", "worst", "late", "cpu"))
    for fixed in (1, 0):
        for timer_res in (1, 0):
            for pacing in ("sleep", "mix"):
                f, cpu = run(tmp, scene, fixed, pacing, timer_res)
                if len(f) < 10:
                    print("%-6s %-5s %-6s | no frames in trace" % ("fixed" if fixed else "legacy", pacing,
                                                                     "1ms" if timer_res else "15ms"))
                    continue
                late = sum(1 for x in f if x > TARGET_MS * 1.5)
                print("%-6s %-5s %-6s | %6.1f %6.2fms %6.1fms %5d %4s%%" % (
                    "fixed" if fixed else "legacy", pacing, "1ms" if timer_res else "15ms",
                    1000.0 / statistics.mean(f), statistics.pstdev(f), max(f), late,
                    "%.0f" % cpu if cpu is not None else "?"))
    print("\nTraces in", tmp)

if __name__ == "__main__":
    main()
